"""Fast tunnel test for a mitigation tree: r92 exact-budget picks + fixed
budget sweeps. Deterministic-ish (fresh TT per call, but wall-clock budget).

Usage: TREE=/path /tmp/chessbench/bin/python /tmp/aud6-probe8.py
"""
import os, sys, time

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = os.environ.get("NC", "/tmp/aud6-np8-" + os.path.basename(TREE))
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, search as S
import agent as A

M35 = ("m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", 64754)
M36 = ("m36", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36", 63313)
A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
print(f"### TREE={TREE}")
for name, fen, tl in (M35, M36):
    for rep in range(3):
        A._GAME_KEYS = []
        mv = A.get_move(fen, tl)
        print(f"R92 {name} rep{rep} -> {mv}")
for name, fen, _ in (M35, M36):
    for b in (1500, 3000, 5000, 8000):
        A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
        A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
        A._NODES[0] = 0
        st = B.parse_fen(fen)
        t0 = time.perf_counter()
        mv, sc, dep = S.search_root(st, A._NODES, S._NOW() + b * 1_000_000,
                                    A._TT_KEYS, A._TT_VALS, A._TT_MASK,
                                    A._KILLERS, A._HIST, A._REP, A._SCRATCH,
                                    A._SSCRATCH, 64,
                                    np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        print(f"SWEEP {name} {b}ms -> {B.move_to_uci(mv) if mv else '0000'} "
              f"score={int(sc)} depth={int(dep)} nodes={int(A._NODES[0])} "
              f"{time.perf_counter()-t0:.2f}s")
print("DONE")
