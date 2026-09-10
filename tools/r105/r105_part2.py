#!/usr/bin/env python3
"""r105 post-mortem — part 2: OUR engine on the pre-blunder (#42) FEN at several budgets.

Runs the exact v10 tree (live repo == tm1b) at budgets 1.0 / 1.35 / 2.0 / 3.0 / 5.0 s
and reports chosen UCI + depth + score, 3 reps each (fresh TT/state per rep)."""
import os
import sys

import numpy as np

TREE = "/home/pino/projects/chessathon"
os.environ["NUMBA_CACHE_DIR"] = "/tmp/numba_r105_pm2"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)
os.chdir(TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

FEN = "6k1/5ppp/p7/3P4/6P1/4q2P/5Q2/6K1 b - - 0 47"  # r105 pre-#42 (Qxh3) position

BUDGETS = [1000, 1350, 2000, 3000, 5000]
REPS = 3


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
print(f"=== r105 #42 pre-blunder, our engine | FEN {FEN}")
print("budget_ms,rep,uci,score,depth,nodes,elapsed_ms")
for budget in BUDGETS:
    for r in range(1, REPS + 1):
        uci, score, cd, nodes, ms = one(FEN, budget)
        print(f"{budget},{r},{uci},{score},{cd},{nodes},{ms:.0f}", flush=True)
print("PART2-DONE")
