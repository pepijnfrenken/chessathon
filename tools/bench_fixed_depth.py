"""Fixed-depth NPS A/B (dev tool): deterministic node counts across
variants; elapsed wall time is the only noisy input. Usage:
  python tools/bench_fixed_depth.py startpos 10 [runs]
"""

import os
import sys
import time

import numpy as np
import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import board as B
from engine import search as S
from engine import tt as TT
import engine.eval  # noqa: F401


def one(fen: str, depth: int):
    st = B.parse_fen(fen)
    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    far = S._NOW() + 3_600_000_000_000
    # warmup both chains
    S.search(st, 2, -S.INF, S.INF, 1, nodes, far, ttk, ttv, mask,
             killers, hist, rep, scratch, sscratch)
    S.search_root(st, nodes, far, ttk, ttv, mask, killers, hist, rep,
                  scratch, sscratch, 3, np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    nodes[0] = 0
    t0 = time.perf_counter()
    mv, score, cd = S.search_root(st, nodes, far, ttk, ttv, mask, killers,
                                  hist, rep, scratch, sscratch, depth,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    dt = time.perf_counter() - t0
    return nodes[0], dt, mv, score, cd


if __name__ == "__main__":
    fen = chess.STARTING_FEN if sys.argv[1] == "startpos" else sys.argv[1]
    depth = int(sys.argv[2])
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for r in range(runs):
        n, dt, mv, score, cd = one(fen, depth)
        print(f"run {r}: nodes={n} {n/dt/1e3:.0f} knps depth={cd} best={mv} "
              f"score={score}")