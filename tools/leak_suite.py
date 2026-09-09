#!/usr/bin/env python3
"""P1 leak-suite runner (dev tool). Probes the r64/r68/r74 loss-family
FENs (extracted at the leak plies) at a ~2.6s per-move budget on BOTH
trees (HEAD snapshot vs CURRENT tree with CHESSATHON_SEE/SEEPRUNE on)
and reports searched scores, so the report can assert whether the SEE
build sees the transition loss earlier than V5 HEAD.

Usage:  python tools/leak_suite.py <tag> <json_path> <tree_root>
        tag: head | see   (config: see => CHESSATHON_SEE=SEEPRUNE=1)
Prints one line per FEN:  fam ply nodes score best.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[3] or os.getcwd())
sys.path.insert(0, os.getcwd())

from engine import board as B
from engine import search as S
from engine import tt as TT

BUDGET_NS = 2_600_000_000


def one(fen):
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
    S.search(st, 2, -S.INF, S.INF, 1, nodes, far, ttk, ttv, mask,
             killers, hist, rep, scratch, sscratch)
    nodes[0] = 0
    mv, score, cd = S.search_root(st, nodes, S._NOW() + BUDGET_NS, ttk,
                                  ttv, mask, killers, hist, rep, scratch,
                                  sscratch, 64,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return nodes[0], score, mv


def main():
    tag = sys.argv[1]
    fens = json.load(open(sys.argv[2]))
    for fam in sorted(fens):
        for ply in sorted(fens[fam]):
            n, sc, mv = one(fens[fam][ply])
            print(f"{tag} {fam} ply={ply} nodes={n} score={sc} best={mv}",
                  flush=True)


if __name__ == "__main__":
    main()