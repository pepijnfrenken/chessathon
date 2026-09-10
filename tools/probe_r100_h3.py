#!/usr/bin/env python3
"""r100 h3 probe — FRESH-TT fixed-depth protocol (dev tool, NOT shipped).

Tests the position where the game played 50.h3 (White, we are White) — the
move SF (d28) scores -5.29 while Rb8+/f4 hold the draw (0.00). Reported
behavior: v9k plays h3 at in-game budget on the competition box; local
time-budget repro gives b6b7 instead -> sweep fixed depths to find the band.

Sites:
  m49 = after 48...b2 (game played b8b6 = Rb6;   SF: all reasonable = 0.00)
  m50 = after 49...Kf8 (game played h2h3 = h3;   SF: h3 = -5.29, Rb8+/f4 = 0.00)

Run from a tree root to test THAT tree:
    cd <tree> && /tmp/chessbench/bin/python <path>/probe_r100_h3.py
"""
import os
import sys

import numpy as np

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_r100_{os.path.basename(TREE)}"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

SITES = [
    ("m49", "1R6/6k1/p7/6p1/6K1/5P2/rp3P1P/8 w - - 0 49", "b8b6", "Rb6"),
    ("m50", "5k2/8/pR6/6p1/6K1/5P2/rp3P1P/8 w - - 2 50", "h2h3", "h3"),
]
DEPTHS = [6, 7, 8, 9, 10, 11, 12, 13, 14]


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
    mv, score, cd = S.search_root(st, nodes, S._NOW() + 3_600_000_000_000,
                                  ttk, ttv, mask, killers, hist, rep,
                                  scratch, sscratch, depth,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return B.move_to_uci(mv), score, nodes[0]


def main():
    print(f"=== r100 h3 FRESH-TT fixed-depth probe [{TREE}] ===", flush=True)
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 4)  # jit warm
    for name, fen, game_uci, game_san in SITES:
        print(f"\n--- {name} ({fen}) game move: {game_san} ({game_uci})", flush=True)
        for d in DEPTHS:
            uci, score, nodes = one(fen, d)
            flag = "  <<< GAME MOVE" if uci == game_uci else ""
            print(f"  depth {d:>2}: {uci:<6} score={score:>7} nodes={nodes:>9}{flag}",
                  flush=True)


if __name__ == "__main__":
    main()
