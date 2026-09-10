#!/usr/bin/env python3
"""q5-c3 probe: mate-vs-fifty-move rule inversion (dev tool, NOT shipped).

Audit-6 §C3: `_draw_score` declares the fifty-move draw (halfmove >= 100)
BEFORE any mate test, so a position that is literally checkmate at
halfmove >= 100 scores 0 instead of a mate score — and a mating move that
LANDS on the 100th halfmove is scored as a draw.

Cases (all verified against python-chess, the legality oracle, first):

  | FEN                                    | truth                        |
  |----------------------------------------|------------------------------|
  | 7k/6Q1/5K2/8/8/8/8/8 b - - 100 1       | checkmate (hm already 100)   |
  | 7k/6Q1/5K2/8/8/8/8/8 b - -  99 1       | checkmate (control, hm 99)   |
  | 7k/6Q1/6K1/8/8/8/8/8 b - - 100 1       | checkmate (queen adjacent)   |
  | 7k/8/6Q1/8/8/8/8/K7 b - - 100 1        | STALEMATE — stays 0          |
  | 7k/8/6Q1/8/8/8/8/K7 b - -  99 1        | stalemate control            |
  | 7k/8/5KQ1/8/8/8/8/8 w - -  99 1        | white mates in 1 (Qg7#, the  |
  |                                        | mating move lands on hm 100) |
  | 8/8/8/8/8/8/8/K6k w - - 100 1          | bare kings — dead draw       |

Expected scores at ply 1: mated side => -MATE + 1 = -29999; the mating
side => +(MATE - 2) = 29998 (mate in 1 move = 2 plies); draws => 0.

Usage:  python tools/probe_c3_mate_fifty.py [out.txt] [--root TREE]
        --root lets the same probe run against a control tree
        (e.g. /tmp/chessathon-v9k-base) without touching it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "--root" in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
sys.path.insert(0, ROOT)
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

MATE = 30000
LOSING = -29999          # -MATE + ply(1)
WINNING = 29998          # +(MATE - 2): mate in one move

# (name, fen, kind)  kind: "lose" | "win" | "draw"
CASES = [
    ("mate on board @ hm100", "7k/6Q1/5K2/8/8/8/8/8 b - - 100 1", "lose"),
    ("mate on board @ hm99 (control)", "7k/6Q1/5K2/8/8/8/8/8 b - - 99 1", "lose"),
    ("mate adj-queen @ hm100", "7k/6Q1/6K1/8/8/8/8/8 b - - 100 1", "lose"),
    ("stalemate @ hm100 (stays 0)", "7k/8/6Q1/8/8/8/8/K7 b - - 100 1", "draw"),
    ("stalemate @ hm99 (control)", "7k/8/6Q1/8/8/8/8/K7 b - - 99 1", "draw"),
    ("mate-in-1 landing on hm100", "7k/8/5KQ1/8/8/8/8/8 w - - 99 1", "win"),
    ("bare kings @ hm100 (dead draw)", "8/8/8/8/8/8/8/K6k w - - 100 1", "draw"),
]


def one(fen, depth):
    st = B.parse_fen(fen)
    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    # warmup call is separate (main); this is the measured search
    score = S.search(st, depth, -S.INF, S.INF, 1, nodes, S._NOW() + 10**13,
                     ttk, ttv, mask, killers, hist, rep, scratch, sscratch)
    return score, nodes[0]


def main():
    out_path = next((a for a in sys.argv[1:]
                     if not a.startswith("--")
                     and a != (sys.argv[sys.argv.index("--root") + 1]
                               if "--root" in sys.argv else None)), None)
    out = open(out_path, "w") if out_path else None

    def emit(line=""):
        print(line, flush=True)
        if out:
            print(line, file=out, flush=True)

    emit(f"q5-c3 mate-vs-fifty probe — tree: {ROOT}")
    emit("(fixed depth 3, fresh TT per case; expected = the CORRECT score)")
    emit(f"{'case':34} {'score':>7} {'expected':>9} {'verdict':>8}")
    # warm the jitted path once (so no case pays the compile)
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 2)
    bad = 0
    for name, fen, kind in CASES:
        sc, _n = one(fen, 3)
        if kind == "lose":
            exp, ok = str(LOSING), sc == LOSING
        elif kind == "win":
            exp, ok = str(WINNING), sc == WINNING
        else:
            exp, ok = "0", sc == 0
        bad += (not ok)
        emit(f"{name:34} {sc:7d} {exp:>9} {'OK' if ok else 'BAD':>8}")
    emit()
    emit(f"failures: {bad}")
    if out:
        out.close()
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
