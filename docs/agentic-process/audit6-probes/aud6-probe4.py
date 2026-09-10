"""Root-move score table at fixed depth (one root, all legal moves).

For each legal root move: apply it, search the child to depth-1 with a FULL
window (-INF, INF) from the child's perspective, negate -> the root move's
score at that depth under a perfect root ordering (no PVS/LMR ordering
effects, no rootorder). TT/killers/history cleared per move for isolation.

Usage: TREE=/path DEPTHS=6,7 /tmp/chessbench/bin/python /tmp/aud6-probe4.py
"""
import os, sys, time

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = "/tmp/aud6-np4-" + os.path.basename(TREE)
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, search as S
import agent as A

DEPTHS = [int(x) for x in os.environ.get("DEPTHS", "6,7").split(",")]
M35 = "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"
M36 = "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36"
FENS = [("m35", M35), ("m36", M36)]

BIG = S._NOW() + 3_600_000_000_000


def root_scores(fen, depth):
    out = []
    n = B.legal_moves(B.parse_fen(fen), np.zeros(B.MAX_MOVES, dtype=np.int32), False)
    buf = np.zeros(B.MAX_MOVES, dtype=np.int32)
    st = B.parse_fen(fen)
    n = B.legal_moves(st, buf, False)
    for i in range(n):
        mv = int(buf[i])
        A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
        A._KILLERS.fill(0); A._HIST.fill(0); A._NODES[0] = 0
        s2 = B.parse_fen(fen)
        mv2 = None
        bb = np.zeros(B.MAX_MOVES, dtype=np.int32)
        k = B.legal_moves(s2, bb, False)
        for j in range(k):
            if int(bb[j]) == mv:
                mv2 = int(bb[j]); break
        if mv2 is None:
            continue
        cap = int(s2['squares'][0][B.m_to(mv2)])
        if B.m_flags(mv2) == B.F_EP:
            cap = int(s2['squares'][0][B.m_to(mv2) - 16])
        pc = (int(s2['castle'][0]), int(s2['ep'][0]), int(s2['halfmove'][0]),
              int(s2['key'][0]))
        B.make_move_apply(s2, mv2)
        sc = S.search(s2, depth - 1, -S.INF, S.INF, 1, A._NODES, BIG,
                      A._TT_KEYS, A._TT_VALS, A._TT_MASK, A._KILLERS,
                      A._HIST, A._REP, A._SCRATCH, A._SSCRATCH)
        out.append((-int(sc), B.move_to_uci(mv2), int(A._NODES[0])))
    out.sort(key=lambda r: -r[0])
    return out


A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
print(f"### TREE={TREE}")
for name, fen in FENS:
    for d in DEPTHS:
        t0 = time.time()
        rows = root_scores(fen, d)
        print(f"-- {name} depth={d} ({time.time()-t0:.1f}s) top 8 of {len(rows)}:")
        for sc, u, nd in rows[:8]:
            print(f"     {u}  score={sc:6d}  nodes={nd}")
print("DONE")
