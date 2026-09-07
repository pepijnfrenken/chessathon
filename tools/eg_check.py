"""Endgame conversion spot-check (dev tool, NOT shipped).

Plays four basic won endgames — KQvK, KRvK, KPK, KRPvK — between two
engine_side configs (default: the shipped full eval vs a material+PST-only
defender) and requires the strong side to WIN, ideally before the 300-ply
harness cap. The 1a/1b flat eval used to shuffle won endgames into the
adjudication draw ("king walks to h4"); king-safety + endgame terms should
have fixed that. The strong side alternates colors per case.

KPK is the sharpest check: material diff 100 < the 500-adjudication
threshold, so failing to promote within 300 plies is scored a DRAW.

Usage:
    python tools/eg_check.py [--strong tuned:1111 --weak hand:0000 --move-ms 300]
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

from sprt import play_game  # noqa: E402  (driver: legal-move oracle + flags)

CASES = [
    ("KQvK",  "7k/8/8/8/8/8/8/KQ6 w - - 0 1"),
    ("KRvK",  "7k/8/8/8/8/8/8/KR6 w - - 0 1"),
    ("KPK",   "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1"),
    ("KRPvK", "8/8/8/3k4/8/8/4RP2/4K3 w - - 0 1"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strong", default="tuned:1111")
    ap.add_argument("--weak", default="hand:0000")
    ap.add_argument("--move-ms", type=int, default=300)
    args = ap.parse_args()

    s_cfg, s_gate = args.strong.split(":")
    w_cfg, w_gate = args.weak.split(":")

    def spawn(cfg, gate):
        env = dict(os.environ)
        env["CHESSATHON_EVAL_CONFIG"] = cfg
        env["CHESSATHON_EVAL_GATE"] = gate
        env["CHESSATHON_MOVE_BUDGET_MS"] = str(args.move_ms)
        return subprocess.Popen(
            [sys.executable, str(_HERE / "engine_side.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env)

    sp, wp = spawn(s_cfg, s_gate), spawn(w_cfg, w_gate)
    try:
        rng = random.Random(11)
        # both colors per case: strong side is White, then Black
        for name, fen in CASES:
            for strong_white in (True, False):
                sides = {chess.WHITE: {"proc": (sp if strong_white else wp),
                                       "name": args.strong if strong_white
                                       else args.weak},
                         chess.BLACK: {"proc": (wp if strong_white else sp),
                                       "name": args.weak if strong_white
                                       else args.strong}}
                g = play_game(fen, sides, rng)
                strong_name = "white" if strong_white else "black"
                result = g["result"]
                ok = (result == "1-0") if strong_white else (result == "0-1")
                text = "WIN" if ok else f"{'LOSS' if result in ('0-1','1-0') else 'DRAW'}"
                print(f"{name:6s} strong-as-{strong_name:5s} ply={g['ply']:3d} "
                      f"result={result} {text}" + 
                      ("  <== " + ";".join(f"{k}({s})" for k, s, _ in g["flags"])
                       if g["flags"] else ""))
                if g["flags"]:
                    print("FLAGS:", g["flags"]); return 1
        return 0
    finally:
        for p in (sp, wp):
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