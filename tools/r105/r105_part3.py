#!/usr/bin/env python3
"""r105 post-mortem — part 3: our engine on the *consequence* positions.

A) the queenless pawn endgame after 47...Qxf2+ 48.Kxf2 (SF: won for us, +6.2)
B) #46 pre-g6 (SF: dead draw 0.00; the move chosen tells us if we can hold)
"""
import os
import sys

import numpy as np

TREE = "/home/pino/projects/chessathon"
os.environ["NUMBA_CACHE_DIR"] = "/tmp/numba_r105_pm3"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)
os.chdir(TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

A = ("pawn endgame after Qxf2+ Kxf2",
     "6k1/5ppp/p7/3P4/6P1/8/5K2/8 b - - 0 48")
B_ = ("#46 pre-g6 (SF: 0.00 draw)",
      "4q1k1/2Q2ppp/p7/3P4/6P1/8/5K2/8 b - - 7 51")


def one(fen, budget_ms):
    st = B.parse_fen(fen)
    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    t0 = S._NOW()
    mv, score, cd = S.search_root(st, nodes, t0 + budget_ms * 1_000_000,
                                  ttk, ttv, mask, killers, hist, rep,
                                  scratch, sscratch, 64,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    ms = (S._NOW() - t0) / 1e6
    return B.move_to_uci(mv), score, cd, nodes[0], ms


one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 300)  # warmup
for name, fen in (A, B_):
    print(f"=== {name} ===")
    print(f"    FEN {fen}")
    for budget in (1000, 3000, 5000):
        for r in (1, 2):
            uci, score, cd, nodes, ms = one(fen, budget)
            print(f"    {budget}ms rep{r}: {uci} score={score} depth={cd} nodes={nodes} elapsed={ms:.0f}",
                  flush=True)
print("PART3-DONE")
