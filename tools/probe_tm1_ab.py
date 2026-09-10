#!/usr/bin/env python3
"""tm1 unit test: run the razor sites at game-clock budgets on THIS tree.

Cases carry an explicit budget (ms) so the same script runs on the shipped
tree and the tm1 tree for contrast:
  m35@1939  = shipped formula budget at R=64754 (flip-guard isolation test)
  m35@3000  = tm1 formula budget at R=64754
  m49@3000  = tm1 formula budget at R~48300
  m50@3000  = tm1 formula budget at R~47200
  m50@1549  = shipped formula budget at R=47200 (baseline)

Run from a tree root:  cd <tree> && /tmp/chessbench/bin/python <this>
"""
import os
import sys

import numpy as np

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_tm1unit_{os.path.basename(TREE)}"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

CASES = [
    ("m35@1939 (guard test)", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", 1939),
    ("m35@3000 (tm1 formula)", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", 3000),
    ("m49@3000 (tm1 formula)", "1R6/6k1/p7/6p1/6K1/5P2/rp3P1P/8 w - - 0 49", 3000),
    ("m50@3000 (tm1 formula)", "5k2/8/pR6/6p1/6K1/5P2/rp3P1P/8 w - - 2 50", 3000),
    ("m50@1549 (shipped budget)", "5k2/8/pR6/6p1/6K1/5P2/rp3P1P/8 w - - 2 50", 1549),
]


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
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 300)
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 300)
    print(f"=== {TREE} ===", flush=True)
    for name, fen, budget in CASES:
        for rep in (1, 2):
            uci, score, cd, nodes, ms = one(fen, budget)
            print(f"{name} rep{rep}: {uci} score={score} depth={cd} "
                  f"nodes={nodes} elapsed={ms:.0f}ms", flush=True)


if __name__ == "__main__":
    main()
