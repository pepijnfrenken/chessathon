"""Budgeted root probe: which move does the tree play at each real budget,
plus completed depth + elapsed + nodes. Warmup call first (discarded).

Usage: TREE=/path /tmp/chessbench/bin/python /tmp/aud6-probe3.py
"""
import os, sys, time, json

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = "/tmp/aud6-np3-" + os.path.basename(TREE)
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, search as S
import agent as A

FENS = [
    ("m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"),
    ("m36", "6k1/p3qpp1/Pp5p/4N3/1R4P1/1Q4KP/2r3P1/2r5 w - - 6 36"),
]
BUDGETS = [1000, 1500, 1938, 2500, 3000, 4000, 6000, 8000]


def run(fen, budget_ms, clear_tt=True):
    st = B.parse_fen(fen)
    if clear_tt:
        A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
    A._NODES[0] = 0
    t0 = time.perf_counter()
    mv, sc, dep = S.search_root(st, A._NODES, S._NOW() + budget_ms * 1_000_000,
                                A._TT_KEYS, A._TT_VALS, A._TT_MASK,
                                A._KILLERS, A._HIST, A._REP, A._SCRATCH,
                                A._SSCRATCH, 64,
                                np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    dt = time.perf_counter() - t0
    return (B.move_to_uci(mv) if mv else "0000"), int(sc), int(dep), \
        int(A._NODES[0]), dt


# warmup get_move (discarded) — the documented first-call budget overrun
A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
print(f"### TREE={TREE}")
for name, fen in FENS:
    for b in BUDGETS:
        mv, sc, dep, nodes, dt = run(fen, b)
        nps = nodes / dt if dt > 0 else 0
        print(f"  {name} budget={b:5d}ms -> {mv} score={sc:5d} depth={dep:2d} "
              f"nodes={nodes:8d} elapsed={dt*1000:7.0f}ms nps={nps/1000:6.0f}k")
print("DONE")
