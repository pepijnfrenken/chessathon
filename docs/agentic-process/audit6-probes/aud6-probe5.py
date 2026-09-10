"""Venue-style warm-TT probes (one process per tree).

A. Warm sweep: sequential get_move at 1/2/3/5s budgets on the two r92 FENs
   (TT *not* cleared between calls = the venue's state; this is also the
   order tools/probe_r92_collapse.py's SWEEP=1 uses).
B. TT-vs-fifty-move: search the SAME placement at halfmove 0 (populating the
   TT) then at halfmove 99 with the TT left warm.
C. Warm root score table at depth 7: for each root move, apply it and search
   the child (depth-1) with the SHARED warm TT, in the real ID order
   (previous-iteration best first) -- i.e. exactly what _root_iter does.

Usage: TREE=/path /tmp/chessbench/bin/python /tmp/aud6-probe5.py
"""
import os, sys, time

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = "/tmp/aud6-np5-" + os.path.basename(TREE)
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, search as S
import agent as A

M35 = "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"
M36 = "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36"
BIG = S._NOW() + 3_600_000_000_000


def tl_for(budget_ms):
    return (budget_ms - 500) * 45


def id_search(fen, max_depth, ttk, ttv, clear=False):
    if clear:
        ttk.fill(0); ttv.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
    A._NODES[0] = 0
    st = B.parse_fen(fen)
    t0 = time.perf_counter()
    mv, sc, dep = S.search_root(st, A._NODES, BIG, ttk, ttv, A._TT_MASK,
                                A._KILLERS, A._HIST, A._REP, A._SCRATCH,
                                A._SSCRATCH, max_depth,
                                np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return (B.move_to_uci(mv) if mv else "0000"), int(sc), int(dep), \
        int(A._NODES[0]), time.perf_counter() - t0


A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
print(f"### TREE={TREE}")

# ---- A: venue-style warm sweep (TT + killers/history carried across calls)
print("-- A: warm sweep via get_move (no TT clear between calls)")
for name, fen in (("m35", M35), ("m36", M36)):
    A._GAME_KEYS = []
    for b in (1000, 2000, 3000, 5000):
        A._GAME_KEYS = []
        t0 = time.perf_counter()
        mv = A.get_move(fen, tl_for(b))
        print(f"   {name} warm {b}ms -> {mv} ({time.perf_counter()-t0:.2f}s)")

# ---- B: TT vs fifty-move, warm
f0 = '7k/8/8/8/8/8/8/KR6 w - - 0 1'
f99 = f0.replace('0 1', '99 1')
A._TT_KEYS.fill(0); A._TT_VALS.fill(0); A._REP.fill(0)


def plain(fen, depth=2):
    A._NODES[0] = 0
    st = B.parse_fen(fen)
    return int(S.search(st, depth, -S.INF, S.INF, 1, A._NODES, BIG,
                        A._TT_KEYS, A._TT_VALS, A._TT_MASK, A._KILLERS,
                        A._HIST, A._REP, A._SCRATCH, A._SSCRATCH))


print(f"-- B: TT/fifty-move  cold99={plain(f99)} (empty TT)  "
      f"then hm0={plain(f0)} (warm)  then hm99_warm={plain(f99)}")

# ---- C: warm root score table at depth 7 (real ID order, shared TT)
print("-- C: warm root scores at depth 7 (previous-best first)")


def warm_root_table(fen, depth):
    A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
    best = 0
    for d in range(1, depth):          # warm the table like the ID loop does
        st = B.parse_fen(fen)
        m, sc, c = S.search_root(st, A._NODES, BIG, A._TT_KEYS, A._TT_VALS,
                                 A._TT_MASK, A._KILLERS, A._HIST, A._REP,
                                 A._SCRATCH, A._SSCRATCH, d,
                                 np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        best = m
    rows = []
    st = B.parse_fen(fen)
    buf = np.zeros(B.MAX_MOVES, dtype=np.int32)
    n = B.legal_moves(st, buf, False)
    moves = [int(buf[i]) for i in range(n)]
    scr = np.zeros(B.MAX_MOVES, dtype=np.int32)
    S._order_moves(st, buf, scr, n, best, A._KILLERS, A._HIST, 0)
    ordered = [int(buf[i]) for i in range(n)]
    for mv in ordered:
        s2 = B.parse_fen(fen)
        bb = np.zeros(B.MAX_MOVES, dtype=np.int32)
        k = B.legal_moves(s2, bb, False)
        tgt = None
        for j in range(k):
            if int(bb[j]) == mv:
                tgt = int(bb[j]); break
        cap = int(s2['squares'][0][B.m_to(tgt)])
        if B.m_flags(tgt) == B.F_EP:
            cap = int(s2['squares'][0][B.m_to(tgt) - 16])
        sv = (int(s2['castle'][0]), int(s2['ep'][0]),
              int(s2['halfmove'][0]), int(s2['key'][0]))
        B.make_move_apply(s2, tgt)
        sc = S.search(s2, depth - 1, -S.INF, S.INF, 1, A._NODES, BIG,
                      A._TT_KEYS, A._TT_VALS, A._TT_MASK, A._KILLERS,
                      A._HIST, A._REP, A._SCRATCH, A._SSCRATCH)
        rows.append((-int(sc), B.move_to_uci(mv)))
    rows.sort(key=lambda r: -r[0])
    return B.move_to_uci(best), rows


for name, fen in (("m35", M35), ("m36", M36)):
    prev, rows = warm_root_table(fen, 7)
    print(f"   {name}: ID-to-6 best (ordering seed) = {prev}")
    for sc, u in rows[:6]:
        print(f"      warm d7 {u} score={sc}")
print("DONE")
