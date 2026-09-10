#!/usr/bin/env python3
"""r92 tunnel probe — FRESH-TT fixed-depth protocol (dev tool, NOT shipped).

Why this exists: `tools/probe_r92_collapse.py`'s SWEEP loop reuses one warm
transposition table across its budget sequence and across the two sites, so
the "blunder band" it reports is a warm-TT artifact (audit-6 §B1). This
probe instead measures the *depth-granular* behaviour the tunnel actually
depends on: for each site, each depth 6..10 is searched with a FRESH TT and
a fixed (unlimited) deadline, so the only variable is which depth completed.

Run from a tree root to test THAT tree:
    cd <tree> && /tmp/chessbench/bin/python <path>/probe_r92_depth.py

Prints one line per (site, depth): chosen move, score, nodes.
m35 = position before the game's 35...Qb3?? (game move d5b3, SF-correct e5d3)
m36 = position before the game's 36...Rb5?? (game move b4b5, SF-correct g3h2)
"""
import os
import sys

import numpy as np

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_r92d_{os.path.basename(TREE)}"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

SITES = [
    ("m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", "d5b3"),
    ("m36", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36", "b4b5"),
]
DEPTHS = [6, 7, 8, 9, 10]


def one(fen, depth):
    """Fresh TT, fresh scratch, fixed depth, unlimited deadline."""
    st = B.parse_fen(fen)
    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    mv, score, cd = S.search_root(st, nodes, S._NOW() + 3_600_000_000_000,
                                  ttk, ttv, mask, killers, hist, rep,
                                  scratch, sscratch, depth,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return B.move_to_uci(mv), score, nodes[0]


def main():
    print(f"=== r92 FRESH-TT fixed-depth probe [{TREE}] ===", flush=True)
    # warm the jit on a throwaway position so depth 6 is not the compile
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 4)
    for name, fen, game_mv in SITES:
        print(f"\n{name} (game move {game_mv})", flush=True)
        for d in DEPTHS:
            mv, sc, n = one(fen, d)
            tag = ""
            if mv == game_mv:
                tag = "  <-- GAME-as-played"
            print(f"  depth {d:2d}: {mv} score={sc:6d} nodes={n:9d}{tag}",
                  flush=True)


if __name__ == "__main__":
    main()
