"""Fixed-size engine match gate (dev tool, NOT shipped).

Reuses sprt.py's game driver to play N games between two engine_side
configs from our varied openings (colors swapped per pair), reporting the
score and ANY illegal/crash/null/timeout flags. This is the "harness vs
baseline" ship gate: 20+ games, >=60% expected, ZERO flags.

Usage:
    python tools/gate_match.py --side-a tuned:1111 --side-b hand:0000 \
        --games 24 --move-ms 500 --log results/gate_tuned_vs_1b.log
Returns non-zero if any flag occurs (score is informational here).
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

from common import OPENING_FENS, side_env  # noqa: E402
from sprt import play_game  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side-a", default="tuned:1111")
    ap.add_argument("--side-b", default="hand:0000")
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--move-ms", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    log_path = args.log or (
        f"results/gate_{time.strftime('%Y%m%d_%H%M%S')}.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    def spawn(spec, move_ms):
        return subprocess.Popen(
            [sys.executable, str(_HERE / "engine_side.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
            env=side_env(spec, move_ms))

    pa = spawn(args.side_a, args.move_ms)
    pb = spawn(args.side_b, args.move_ms)
    lines = [f"# gate {args.side_a} vs {args.side_b} games={args.games} "
             f"move-ms={args.move_ms} seed={args.seed}"]
    rng = random.Random(args.seed)
    wins = losses = draws = 0
    try:
        for g in range(args.games // 2):
            opening = OPENING_FENS[rng.randrange(len(OPENING_FENS))]
            g1 = play_game(opening,
                           {chess.WHITE: {"proc": pa, "name": args.side_a},
                            chess.BLACK: {"proc": pb, "name": args.side_b}}, rng)
            g2 = play_game(opening,
                           {chess.WHITE: {"proc": pb, "name": args.side_b},
                            chess.BLACK: {"proc": pa, "name": args.side_a}}, rng)
            for gi, gv in ((1, g1), (2, g2)):
                res_a = gv["result"]
                if gv["flags"]:
                    print(f"FLAG pair {g} game {gi}: {gv['flags']}")
                    lines.append(f"FLAG pair {g} game {gi}: {gv['flags']}")
                    return 1
                # from A's perspective (A is white in g1, black in g2)
                if gi == 1:
                    ares = {"1-0": "win", "0-1": "loss"}.get(res_a, "draw")
                else:
                    ares = {"0-1": "win", "1-0": "loss"}.get(res_a, "draw")
                wins += ares == "win"
                losses += ares == "loss"
                draws += ares == "draw"
                print(f"pair {g:2d} game {gi}: {res_a} (A {ares}) "
                      f"ply={gv['ply']}")
                lines.append(f"pair {g:2d} game {gi}: {res_a} (A {ares}) "
                             f"ply={gv['ply']}")
        total = wins + losses + draws
        score = (wins + 0.5 * draws) / total
        summary = (f"\n=== {args.side_a} vs {args.side_b}: {wins}W {losses}L "
                   f"{draws}D ({score:.3f}) over {total} games, ZERO flags ===")
        print(summary)
        lines.append(summary)
        with open(log_path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"log: {log_path}")
        return 1 if total < 20 else 0
    finally:
        for p in (pa, pb):
            try:
                p.stdin.write("quit\n"); p.stdin.flush()
            except Exception:
                pass
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())