"""Fixed-depth node/time comparison for the rootorder A/B (fresh TT each run).

For a list of FENs and depths, run search_root from a cleared TT and report
(bestmove, score, nodes, seconds). Node counts are the ordering-change signal;
seconds include the same compile-free steady state on both trees.

Usage: TREE=/path DEPTHS=7,8 /tmp/chessbench/bin/python /tmp/aud6-probe6.py
"""
import os, sys, time

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = "/tmp/aud6-np6-" + os.path.basename(TREE)
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, search as S
import agent as A

DEPTHS = [int(x) for x in os.environ.get("DEPTHS", "7,8").split(",")]
BIG = S._NOW() + 3_600_000_000_000
FENS = [
    ("r92m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"),
    ("r92m36", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36"),
    ("r83p21", "1r3qk1/4bpp1/p2ppn1p/P1p5/2P1P3/1P1P1N1P/3B1PP1/2RQ1RK1 w - - 2 21"),
    ("start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("mid1", "r2q1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1"),
    ("mid2", "2r2rk1/1pq1npp1/2b2n2/p3p1Np/1b6/1QNBP2P/PP1B1PP1/3RK2R w K - 8 23"),
    ("eg1", "8/4k3/6Q1/8/4PP1P/p6K/P5P1/2r1q3 w - - 1 72"),
]
A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
print(f"### TREE={TREE}")
tot = {}
for name, fen in FENS:
    for d in DEPTHS:
        A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
        A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
        A._NODES[0] = 0
        st = B.parse_fen(fen)
        t0 = time.perf_counter()
        mv, sc, comp = S.search_root(st, A._NODES, BIG, A._TT_KEYS,
                                     A._TT_VALS, A._TT_MASK, A._KILLERS,
                                     A._HIST, A._REP, A._SCRATCH, A._SSCRATCH,
                                     d, np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        dt = time.perf_counter() - t0
        nd = int(A._NODES[0])
        tot[d] = tot.get(d, 0) + nd
        print(f"  {name:8s} d={d} -> {B.move_to_uci(mv) if mv else '0000':6s} "
              f"score={int(sc):6d} nodes={nd:9d} {dt:6.2f}s")
print("TOTALS", {d: tot[d] for d in sorted(tot)})
print("DONE")
