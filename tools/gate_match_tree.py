"""Fixed-size cross-tree engine match gate (dev tool, NOT shipped).

Same as gate_match.py but side B runs engine_side_tree.py against an OLD
code tree — for A/B'ing the current engine against a previous commit
(e.g. HEAD 05d0101) with identical eval configs and search flags.

Usage:
    python tools/gate_match_tree.py --side-a hand:1111 --side-b hand:1111 \
        --side-b-root /tmp/chessathon_head --games 24 --move-ms 500 \
        --log results/gate_new_vs_head.log
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
    ap.add_argument("--side-a", default="hand:1111")
    ap.add_argument("--side-b", default="hand:1111")
    ap.add_argument("--side-b-root", required=True)
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--move-ms", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    log_path = args.log or (
        f"results/gate_{time.strftime('%Y%m%d_%H%M%S')}.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    def spawn_tree(spec, move_ms, root):
        return subprocess.Popen(
            [sys.executable, str(_HERE / "engine_side_tree.py"), root],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
            env=side_env(spec, move_ms))

    pa = spawn_tree(args.side_a, args.move_ms, os.getcwd())
    pb = spawn_tree(args.side_b, args.move_ms, args.side_b_root)
    lines = [f"# gate {args.side_a} (new, {os.getcwd()}) vs "
             f"{args.side_b} (old, {args.side_b_root}) games={args.games} "
             f"move-ms={args.move_ms} seed={args.seed}"]
    rng = random.Random(args.seed)
    wins = losses = draws = 0
    try:
        for g in range(args.games // 2):
            for order in (0, 1):
                if order == 0:
                    sides = {chess.WHITE: {"proc": pa, "name": "a"},
                             chess.BLACK: {"proc": pb, "name": "b"}}
                else:
                    sides = {chess.WHITE: {"proc": pb, "name": "b"},
                             chess.BLACK: {"proc": pa, "name": "a"}}
                fen = rng.choice(OPENING_FENS)
                gd = play_game(fen, sides, rng)
                res = gd["result"]
                line = (f"{g*2+order+1:3d}. {res:6s} ply={gd['ply']:3d} "
                        f"flags={gd['flags']}")
                lines.append(line)
                print(line)
                if gd["flags"]:
                    lines.append("FLAGS: " + " ".join(str(f) for f in gd["flags"]))
                    return 1
                if res == "1/2-1/2":
                    draws += 1
                elif (res == "1-0") == (order == 0):
                    wins += 1
                else:
                    losses += 1
        score = (wins + 0.5 * draws) / (wins + losses + draws)
        tail = f"score: {wins}W-{losses}L-{draws}D ({score:.3f})"
        lines.append(tail)
        print(tail)
        with open(log_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return 1 if (wins + losses + draws) < 20 else 0
    finally:
        for p in (pa, pb):
            try:
                p.stdin.write("quit\n")
                p.stdin.flush()
            except Exception:
                pass
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())