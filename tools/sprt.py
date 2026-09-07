"""SPRT self-play harness for eval A/B tests (dev tool, NOT shipped).

Plays two engine configurations (tools/engine_side.py subprocesses, one
per side — config chosen at import via env: CHESSATHON_EVAL_CONFIG=hand|tuned,
CHESSATHON_EVAL_GATE=NNNN) against each other from our own varied openings,
alternating colors per pair, fixed per-move budget, and applies the
sequential probability ratio test:

    H0: elo0   (default 0)
    H1: elo1   (default +10)
    alpha=beta=0.05  -> accept when LLR >= ln((1-beta)/alpha),
                        reject when LLR <= ln(beta/(1-alpha))

Only decisive games move the LLR (fixed draw-ratio model, draws -> 0
increment, like cutechess-cli's default). Discipline: accept ONLY SPRT
verdicts; the raw score is informational, the bounds decide.

Usage:
    python tools/sprt.py --side-a hand:1111 --side-b hand:0000 \
        --elo1 20 --max-pairs 300 --move-ms 300 --log results/sprt_...log

Flags recorded like local_game.py: illegal/crash/timeout -> the game is
a loss for the offending side and the run exits non-zero.
"""

import argparse
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import chess

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

from common import (OPENING_FENS, VICTIM, MAX_PLY, adjudicate,  # noqa: E402
                    side_env)


# ---------------------------------------------------------------------------
# SPRT math (standard trinomial model; draws carry a fixed ratio d)
# ---------------------------------------------------------------------------

def _theta(elo: float) -> float:
    return 10.0 ** (elo / 400.0)


def llr_dec(elo0: float, elo1: float, d: float) -> float:
    """LLR added by a WIN (a loss subtracts the same amount; a draw adds
    0 by construction of the fixed-d model)."""
    t0, t1 = _theta(elo0), _theta(elo1)
    w0 = (1.0 - d) * t0 / (t0 + 1.0)
    w1 = (1.0 - d) * t1 / (t1 + 1.0)
    return _ln(w1 / w0)


def _ln(x: float) -> float:
    import math
    return math.log(x)


# ---------------------------------------------------------------------------
# Game driver (fixed per-move budget; honestly flagging bad behavior)
# ---------------------------------------------------------------------------

def play_game(start_fen: str, sides: dict, rng: random.Random,
              timeout_s: float = 600.0) -> dict:
    """sides maps chess.Color -> {'proc': Popen, 'name': str}.
    Returns result from White's POV plus flags."""
    board = chess.Board(start_fen)
    moves_uci = []
    ply = 0
    flags = []
    loser = None
    t0 = time.monotonic()

    def _ask(side_color, fen):
        proc = sides[side_color]["proc"]
        if proc.poll() is not None:
            return "ERROR:side process died"
        try:
            proc.stdin.write(fen + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        except Exception as exc:
            return f"ERROR:{exc!r}"
        if line is None or line == "":
            return "ERROR:no response"
        return line.strip()

    while not board.is_game_over() and ply < MAX_PLY:
        if time.monotonic() - t0 > timeout_s:
            flags.append(("harness-timeout", sides[board.turn]["name"], ""))
            break
        side = board.turn
        name = sides[side]["name"]
        resp = _ask(side, board.fen())
        if resp.startswith("ERROR"):
            flags.append(("crash", name, resp))
            loser = side
            break
        if resp == "0000":
            flags.append(("null-move", name, "0000 mid-game"))
            loser = side
            break
        try:
            mv = chess.Move.from_uci(resp)
        except ValueError:
            flags.append(("illegal", name, f"unparseable {resp!r}"))
            loser = side
            break
        if mv not in board.legal_moves:
            flags.append(("illegal", name, f"{resp} in {board.fen()}"))
            loser = side
            break
        board.push(mv)
        moves_uci.append(resp)
        ply += 1

    if loser is not None:
        result = "0-1" if loser == chess.WHITE else "1-0"
    else:
        result = adjudicate(board, ply)
    return {"result": result, "flags": flags, "ply": ply,
            "moves": " ".join(moves_uci)}


# ---------------------------------------------------------------------------
# Main SPRT loop
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side-a", default="hand:1111", help="config:gate")
    ap.add_argument("--side-b", default="tuned:1111", help="config:gate")
    ap.add_argument("--move-ms", type=int, default=300)
    ap.add_argument("--max-pairs", type=int, default=400)
    ap.add_argument("--elo0", type=float, default=0.0)
    ap.add_argument("--elo1", type=float, default=10.0)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    ap.add_argument("--draw-ratio", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    log_path = args.log or (
        f"results/sprt_{time.strftime('%Y%m%d_%H%M%S')}.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    # launch the two sides
    procs = {}
    for key, spec in [("a", args.side_a), ("b", args.side_b)]:
        procs[key] = subprocess.Popen(
            [sys.executable, str(_HERE / "engine_side.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
            env=side_env(spec, args.move_ms))

    try:
        rng = random.Random(args.seed)
        gating = args.draw_ratio
        llr = 0.0
        wins = losses = draws = 0
        pairs = 0
        a_elo = b_elo = 0.0
        a_bound = +_ln((1 - args.beta) / args.alpha)
        b_bound = _ln(args.beta / (1 - args.alpha))
        dec = llr_dec(args.elo0, args.elo1, gating)

        lines = [f"# sprt {args.side_a} vs {args.side_b} move-ms={args.move_ms} "
                 f"elo0={args.elo0} elo1={args.elo1} alpha={args.alpha} "
                 f"beta={args.beta} draw={args.draw_ratio}"]
        verdict = "inconclusive (max pairs)"
        low_alpha_names = {"a": args.side_a, "b": args.side_b}

        for pair in range(args.max_pairs):
            opening = OPENING_FENS[rng.randrange(len(OPENING_FENS))]
            # game 1: a=white, b=black
            sides1 = {chess.WHITE: {"proc": procs["a"], "name": low_alpha_names["a"]},
                      chess.BLACK: {"proc": procs["b"], "name": low_alpha_names["b"]}}
            g1 = play_game(opening, sides1, rng)
            # game 2: colors swapped, same opening
            sides2 = {chess.WHITE: {"proc": procs["b"], "name": low_alpha_names["b"]},
                      chess.BLACK: {"proc": procs["a"], "name": low_alpha_names["a"]}}
            g2 = play_game(opening, sides2, rng)
            pairs += 1

            for g in (g1, g2):
                if g["flags"]:
                    for kind, side, detail in g["flags"]:
                        print(f"FLAG pair {pair}: {kind} ({side}) {detail}")
                        lines.append(f"FLAG pair {pair}: {kind} ({side}) {detail}")
                    return 1
                # from A's perspective: A=white in g1, A=black in g2
                if g is g1:
                    res_a = {"1-0": 1, "0-1": 0, "1/2-1/2": 0.5}[g["result"]]
                else:
                    res_a = {"1-0": 0, "0-1": 1, "1/2-1/2": 0.5}[g["result"]]
                if res_a == 1.0:
                    wins += 1
                    llr += dec
                elif res_a == 0.0:
                    losses += 1
                    llr -= dec
                else:
                    draws += 1

            score_a = (wins + 0.5 * draws) / (wins + losses + draws)
            est_a_elo = 400.0 * _ln(score_a / max(1e-9, 1 - score_a)) / _ln(10) \
                if 0 < score_a < 1 else 0.0
            line = (f"pair {pairs:3d} score {wins}-{losses}-{draws} "
                    f"({score_a:.3f}) llr {llr:+.3f} "
                    f"[reject {b_bound:+.2f} .. accept {a_bound:+.2f}]")
            print(line)
            lines.append(line)
            # periodic flush so a killed run still leaves audit trail
            if pairs % 5 == 0:
                with open(log_path, "w") as fh:
                    fh.write("\n".join(lines) + "\n")
            if llr >= a_bound:
                verdict = f"ACCEPT (side A >= elo1={args.elo1})"
                break
            if llr <= b_bound:
                verdict = "REJECT (side A <= elo0)"
                break

        total = wins + losses + draws
        summary = (
            f"\n=== VERDICT: {verdict} after {pairs} pairs ({total} games) ==="
            f"\nside A {args.side_a}: {wins}W {losses}L {draws}D "
            f"({score_a:.3f}, est {est_a_elo:+.0f} elo) | "
            f"llr {llr:+.3f} vs bounds [{b_bound:+.2f}, {a_bound:+.2f}]")
        print(summary)
        lines.append(summary)
        with open(log_path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"log: {log_path}")
        return 0
    finally:
        for key in ("a", "b"):
            try:
                procs[key].stdin.write("quit\n")
                procs[key].stdin.flush()
            except Exception:
                pass
            procs[key].terminate()
            try:
                procs[key].wait(timeout=5)
            except Exception:
                procs[key].kill()


if __name__ == "__main__":
    sys.exit(main())