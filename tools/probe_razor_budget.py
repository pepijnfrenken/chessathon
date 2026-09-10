#!/usr/bin/env python3
"""Budget -> pick sweep at the r92/r100 razor sites (dev tool).

For each site and each time budget: fresh TT/state, deadline-bound root
search (exactly how the game plays a move), repeat N reps. Tells us at what
budget the pick flips from the losing family to the drawing family.

Run from a tree root:  cd <tree> && /tmp/chessbench/bin/python <this>
"""
import os
import sys

import numpy as np

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_tmsweep_{os.path.basename(TREE)}"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

SITES = [
    ("r92-m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", "d5b3"),
    ("r92-m36", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36", "b4b5"),
    ("r100-m49", "1R6/6k1/p7/6p1/6K1/5P2/rp3P1P/8 w - - 0 49", "b8b6"),
    ("r100-m50", "5k2/8/pR6/6p1/6K1/5P2/rp3P1P/8 w - - 2 50", "h2h3"),
]
BUDGETS = [800, 1200, 1600, 2000, 2500, 3000, 4000, 6000]
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


def main():
    # JIT warm + discard the first two calls (first-call-after-warmup overrun)
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 300)
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 300)
    print("site,budget_ms,rep,uci,score,depth,nodes,elapsed_ms,game_flag", flush=True)
    for name, fen, game_uci in SITES:
        for budget in BUDGETS:
            for rep in range(1, REPS + 1):
                uci, score, cd, nodes, ms = one(fen, budget)
                flag = "GAME" if uci == game_uci else ""
                print(f"{name},{budget},{rep},{uci},{score},{cd},{nodes},{ms:.0f},{flag}",
                      flush=True)


if __name__ == "__main__":
    main()
