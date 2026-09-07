"""Reproduce one eg_check case with the full move list (dev tool).

Usage: python tools/repro_case.py KQvK black [--strong tuned:1111]
Prints the move list + result + flags for one case/color via sprt.play_game.
"""

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/pino/projects/chessathon/tools")

import chess  # noqa: E402
from sprt import play_game  # noqa: E402

CASES = {
    "KQvK": "7k/8/8/8/8/8/8/KQ6 w - - 0 1",
    "KRvK": "7k/8/8/8/8/8/8/KR6 w - - 0 1",
    "KPK": "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1",
    "KRPvK": "8/8/8/3k4/8/8/4RP2/4K3 w - - 0 1",
}


def _mirror_fen(fen: str) -> str:
    parts = fen.split()
    rows = parts[0].split("/")[::-1]
    flipped = []
    for row in rows:
        out = ""
        for ch in row:
            if ch.isalpha():
                out += ch.swapcase()
            else:
                out += ch
        flipped.append(out)
    new_side = "b" if parts[1] == "w" else "w"
    return "/".join(flipped) + " " + new_side + " " + " ".join(parts[2:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=list(CASES))
    ap.add_argument("color", choices=["white", "black"])
    ap.add_argument("--strong", default="hand:1111")
    ap.add_argument("--weak", default="hand:0000")
    ap.add_argument("--move-ms", type=int, default=300)
    args = ap.parse_args()

    fen = CASES[args.case]
    if args.color == "black":
        fen = _mirror_fen(fen)
    s_cfg, s_gate = args.strong.split(":")
    w_cfg, w_gate = args.weak.split(":")

    def spawn(cfg, gate):
        env = dict(os.environ)
        env["CHESSATHON_EVAL_CONFIG"] = cfg
        env["CHESSATHON_EVAL_GATE"] = gate
        env["CHESSATHON_MOVE_BUDGET_MS"] = str(args.move_ms)
        return subprocess.Popen(
            [sys.executable, "/home/pino/projects/chessathon/tools/engine_side.py"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env)

    sp, wp = spawn(s_cfg, s_gate), spawn(w_cfg, w_gate)
    strong_white = args.color == "white"
    board = chess.Board(fen)
    try:
        sides = {chess.WHITE: {"proc": sp if strong_white else wp,
                               "name": args.strong if strong_white else args.weak},
                 chess.BLACK: {"proc": wp if strong_white else sp,
                               "name": args.weak if strong_white else args.strong}}
        rng = random.Random(11)
        g = play_game(fen, sides, rng)
        print(f"{args.case} strong-as-{args.color} result={g['result']} "
              f"ply={g['ply']} flags={g['flags']}")
        moves = g["moves"].split()
        for i in range(0, len(moves), 2):
            print(f"{i//2:3d}. {' '.join(moves[i:i+2]):12s}")
        return 0
    finally:
        for p in (sp, wp):
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