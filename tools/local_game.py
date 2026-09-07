"""Local self-play harness for the Chessathon agent (dev tool, NOT shipped).

Plays any two engines against each other under the real clock shape
(base_ms + inc_ms per side) with a genuine time_left_ms decrement +
increment. Available sides: `agent` (current engine), `ref1a` (phase-1a
reference, archived in tools/ref_1a_agent.py), `material` (greedy bot).

This is the correctness gate: ZERO illegal moves / crashes / timeouts /
slow moves across a batch of games from varied starting positions.

Usage:
    python tools/local_game.py                          # agent vs material, 2s+0.1s
    python tools/local_game.py --sides agent:agent --games 6 --base-ms 5000 --inc-ms 50
    python tools/local_game.py --sides agent:ref1a --games 24 --base-ms 5000 --inc-ms 50
    python tools/local_game.py --sides agent:material --games 1 --base-ms 120000 --inc-ms 500

Flags recorded per game: illegal move, crash (exception from get_move),
timeout (moved longer than the clock allowed), slow move (>50 s). The
harness exits non-zero if any flag occurs anywhere.
"""

import argparse
import os
import random
import sys
import time
from pathlib import Path

import chess

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

import agent as our_agent  # noqa: E402

try:
    import ref_1a_agent  # archived phase-1a reference engine
except ImportError:  # pragma: no cover
    ref_1a_agent = None

SLOW_MOVE_MS = 50_000   # anything slower is a flag, regardless of clock
MAX_PLY = 300           # hard game length cap; long shuffles become draws

# ---------------------------------------------------------------------------
# Opening positions (our own small list, written by hand — not a book file).
# ---------------------------------------------------------------------------

_VICTIM = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
           chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}


def _ply(fen: str, moves: list[str]) -> str:
    board = chess.Board(fen)
    for uci in moves:
        board.push_uci(uci)
    return board.fen()


_START = _ply(chess.STARTING_FEN, [])
_RUY = _ply(chess.STARTING_FEN, ["e2e4", "e7e5", "g1f3", "b8c6"])
_QGD = _ply(chess.STARTING_FEN, ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6"])
_ITALIAN = _ply(chess.STARTING_FEN, ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"])
_SICILIAN = _ply(chess.STARTING_FEN, ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4",
                                      "c5d4", "f3d4", "g8f6"])

STARTING_FENS = [_START, _RUY, _QGD, _ITALIAN, _SICILIAN]


# ---------------------------------------------------------------------------
# Material bot: greedily take the most valuable victim, else move at random.
# Our own tiny bot — used only to test against a non-self opponent.
# ---------------------------------------------------------------------------

def material_move(board: chess.Board, rng: random.Random) -> str:
    best = None
    best_score = -1
    for mv in board.legal_moves:
        if board.is_capture(mv):
            if board.is_en_passant(mv):
                score = _VICTIM[chess.PAWN] * 10  # victim not on to_square
            else:
                victim = board.piece_at(mv.to_square)
                score = _VICTIM[victim.piece_type] * 10
            if best is None or score > best_score:
                best, best_score = mv, score
    if best is not None:
        return best.uci()
    return rng.choice(list(board.legal_moves)).uci()


def _move_fn(side: str, rng: random.Random):
    """Return get_move(fen, remaining_ms) for a named side."""
    if side == "agent":
        return our_agent.get_move
    if side == "ref1a":
        if ref_1a_agent is None:
            raise RuntimeError("tools/ref_1a_agent.py not importable")
        return ref_1a_agent.get_move
    if side == "material":
        return lambda fen, remaining_ms: material_move(chess.Board(fen), rng)
    raise ValueError(f"unknown side {side!r}")


# ---------------------------------------------------------------------------
# Game driver
# ---------------------------------------------------------------------------

class GameStats:
    def __init__(self, side_names: dict):
        self.flags = []
        self.side_names = dict(side_names)  # {True: name, False: name}

    def flag(self, kind: str, side: str, detail: str = "") -> None:
        self.flags.append((kind, side, detail))

    def ok(self) -> bool:
        return not self.flags


def play_game(start_fen: str, base_ms: int, inc_ms: int,
              sides: dict, rng: random.Random) -> dict:
    """Play one game under the real clock shape.
    sides maps chess.Color -> side name ('agent'/'ref1a'/'material')."""
    board = chess.Board(start_fen)
    get_move = {c: _move_fn(sides[c], rng) for c in (chess.WHITE, chess.BLACK)}
    clock = {chess.WHITE: base_ms, chess.BLACK: base_ms}
    stats = GameStats(sides)
    moves_uci = []
    ply = 0
    loser = None  # set when a hard flag (illegal/crash/null) ends the game

    while not board.is_game_over() and ply < MAX_PLY:
        side = board.turn
        side_name = sides[side]
        remaining = clock[side]
        start = time.monotonic()

        try:
            uci = get_move[side](board.fen(), remaining)
        except Exception as exc:  # an engine crash is a harness-side flag
            stats.flag("crash", side_name, f"{exc!r}")
            loser = side
            break
        used_ms = int((time.monotonic() - start) * 1000)

        # --- flag checks (correctness gate) ---
        if uci == "0000":
            stats.flag("null-move", side_name, "get_move returned 0000 mid-game")
            loser = side
            break
        try:
            mv = chess.Move.from_uci(uci)
        except ValueError:
            stats.flag("illegal", side_name, f"unparseable uci {uci!r}")
            loser = side
            break
        if mv not in board.legal_moves:
            stats.flag("illegal", side_name, f"{uci} not legal in {board.fen()}")
            loser = side
            break
        if used_ms > remaining + 50:
            stats.flag("timeout", side_name,
                       f"{uci}: used {used_ms}ms of {remaining}ms")
            # move still executed to keep the game going; loss assessed below
        if used_ms > SLOW_MOVE_MS:
            stats.flag("slow", side_name, f"{uci}: {used_ms}ms")

        board.push(mv)
        moves_uci.append(uci)
        clock[side] = remaining - used_ms + inc_ms
        ply += 1

    if loser is not None:
        result = "0-1" if loser == chess.WHITE else "1-0"
    elif board.is_game_over():
        result = board.result(claim_draw=True)
    elif ply >= MAX_PLY:
        # Cap reached: adjudicate by material. A lead of a rook or more
        # with mating potential is a win; otherwise a draw.
        mat_white = sum(_VICTIM[p.piece_type]
                        for p in board.piece_map().values()
                        if p.color == chess.WHITE)
        mat_black = sum(_VICTIM[p.piece_type]
                        for p in board.piece_map().values()
                        if p.color == chess.BLACK)
        diff = mat_white - mat_black
        result = "1-0" if diff >= 500 else ("0-1" if diff <= -500
                                            else "1/2-1/2")
    else:  # game over but not adjudicated path; keep it simple
        result = board.result(claim_draw=True)

    return {
        "start": start_fen,
        "moves": " ".join(moves_uci),
        "result": result,
        "flags": stats.flags,
        "ply": ply,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--base-ms", type=int, default=2000)
    ap.add_argument("--inc-ms", type=int, default=100)
    ap.add_argument("--sides", default="agent:material",
                    help="white:black side names (agent/ref1a/material)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--log", default=None, help="output log path")
    args = ap.parse_args()

    os.environ["CHESSATHON_INC_MS"] = str(args.inc_ms)
    try:
        wname, bname = args.sides.split(":")
        sides = {chess.WHITE: wname, chess.BLACK: bname}
        _move_fn(wname, random.Random(0))
        _move_fn(bname, random.Random(0))
    except (ValueError, KeyError, RuntimeError, AttributeError) as exc:
        print(f"bad --sides: {exc}")
        return 2

    log_path = args.log or (
        f"results/local_games_{time.strftime('%Y%m%d_%H%M%S')}.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    tally = {wname: 0, bname: 0}
    draws = 0
    all_flags = []
    total_elapsed = 0.0

    lines = [f"# local_game --games={args.games} --base-ms={args.base_ms} "
             f"--inc-ms={args.inc_ms} --sides={args.sides} --seed={args.seed}"]
    for g in range(args.games):
        start_fen = STARTING_FENS[g % len(STARTING_FENS)]
        t0 = time.monotonic()
        game = play_game(start_fen, args.base_ms, args.inc_ms, sides, rng)
        d = time.monotonic() - t0
        total_elapsed += d

        if game["result"] == "1-0":
            tally[wname] += 1
        elif game["result"] == "0-1":
            tally[bname] += 1
        else:
            draws += 1
        if not game["flags"]:
            game["flags"] = [(None, None, "")]

        for kind, side, detail in game["flags"]:
            if kind is not None:
                all_flags.append((g, kind, side, detail))

        line = (f"game {g:02d} ply={game['ply']:3d} result={game['result']} "
                f"time={d:6.1f}s flags={len([f for f in game['flags'] if f[0]])} "
                f"start={game['start'].split()[0]}")
        if any(f[0] for f in game["flags"]):
            flags_txt = "; ".join(
                f"{k}({s}: {dt})" for k, s, dt in game["flags"] if k)
            line += f"  <== {flags_txt}"
        print(line)
        lines.append(line + f"\n  moves: {game['moves']}")

    summary = (f"\n=== SUMMARY: {args.games} games, {args.base_ms}ms+{args.inc_ms}ms, "
               f"{args.sides}, {total_elapsed:.0f}s wall ===")
    detail = (f"{wname} wins {tally[wname]}, {bname} wins {tally[bname]}, "
              f"draws {draws}")
    print(summary)
    print(detail)
    lines += [summary, detail]

    if all_flags:
        print(f"!!! {len(all_flags)} FLAG(S):")
        lines.append(f"!!! {len(all_flags)} FLAG(S):")
        for g, kind, side, dt in all_flags:
            msg = f"  game {g:02d} {kind} ({side}): {dt}"
            print(msg)
            lines.append(msg)
        with open(log_path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return 1

    print("OK: zero illegal moves, zero crashes, zero timeouts, zero slow moves")
    lines.append("OK: zero illegal moves, zero crashes, zero timeouts, zero slow moves")
    with open(log_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())