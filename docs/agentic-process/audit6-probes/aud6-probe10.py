"""C1 validation battery — PST rank-orientation flip (aud6, read-only).

Run per variant (own process; numba bakes EVAL_PARAMS at import):
    TREE=/tmp/aud6-scratch-pstfix CHESSATHON_PSTFLIP=   ... /tmp/aud6-probe10.py
    TREE=/tmp/aud6-scratch-pstfix CHESSATHON_PSTFLIP=K  ...
    TREE=/tmp/aud6-scratch-pstfix CHESSATHON_PSTFLIP=KBR ...

Outputs (one diffable line per row):
  1. PST table read: as-read value of the king/rook/bishop tables on the
     e-file and the own-vs-enemy back rank. Proves the flip did what the
     report claims (pure array read, no engine call).
  2. Static eval on the r92 FENs + controls.
  3. r92 exact-budget picks (must stay e5d3-class, not d5b3).
  4. Fixed-depth outcome on 7 FENs (d6/d7/d8) — move + nodes.
  5. Leak corpus (98 FENs) at 1900ms: move + score, for an A/B diff.

Usage: TREE=... CHESSATHON_PSTFLIP=K NC=<fresh cache> /tmp/chessbench/bin/python /tmp/aud6-probe10.py
"""
import os, sys, json, time

TREE = os.environ["TREE"]
VARIANT = os.environ.get("CHESSATHON_PSTFLIP", "")
os.environ["NUMBA_CACHE_DIR"] = os.environ.get(
    "NC", "/tmp/aud6-np10-" + (VARIANT or "off"))
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
from engine import board as B, eval as E, search as S
import agent as A

TAG = VARIANT or "shipped"
print(f"### TREE={TREE} PSTFLIP='{VARIANT}' (tag={TAG})")

# ---- 1. table read (no engine call) --------------------------------------
p = E.EVAL_PARAMS
e_sq = [4 + 8 * r for r in range(8)]
for nm, idx in (("KING", 5), ("ROOK", 3), ("BISHOP", 2)):
    row = [int(p[E.P_PST_MG + idx * 64 + s]) for s in e_sq]
    print(f"TABLE {nm:6s} MG white e1..e8 = {row}")
for nm, idx in (("KING", 5), ("ROOK", 3)):
    own = [int(p[E.P_PST_MG + idx * 64 + s]) for s in (2, 4, 6)]      # c1,e1,g1
    en = [int(p[E.P_PST_MG + idx * 64 + s]) for s in (58, 60, 62)]    # c8,e8,g8
    print(f"TABLE {nm:6s} own-back={own} enemy-back={en} "
          f"own>enemy={sum(own) > sum(en)}")

FENS = [
    ("r92m35", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"),
    ("r92m36", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36"),
    ("r83p21", "1r3qk1/4bpp1/p2ppn1p/P1p5/2P1P3/1P1P1N1P/3B1PP1/2RQ1RK1 w - - 2 21"),
    ("start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("mid1", "r2q1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1"),
    ("mid2", "2r2rk1/1pq1npp1/2b2n2/p3p1Np/1b6/1QNBP2P/PP1B1PP1/3RK2R w K - 8 23"),
    ("eg1", "8/4k3/6Q1/8/4PP1P/p6K/P5P1/2r1q3 w - - 1 72"),
]

# ---- 2. static eval -------------------------------------------------------
for name, fen in FENS:
    print(f"STATIC {name:8s} {int(E.evaluate(B.parse_fen(fen))):+6d}")

# ---- 3/4. search regressions --------------------------------------------
A.get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 400)
BIG = S._NOW() + 3_600_000_000_000


def run(fen, budget_ms=None, depth=None):
    A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._REP.fill(0)
    A._NODES[0] = 0
    st = B.parse_fen(fen)
    dl = S._NOW() + budget_ms * 1_000_000 if budget_ms else BIG
    mv, sc, comp = S.search_root(st, A._NODES, dl, A._TT_KEYS, A._TT_VALS,
                                 A._TT_MASK, A._KILLERS, A._HIST, A._REP,
                                 A._SCRATCH, A._SSCRATCH, depth or 64,
                                 np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return (B.move_to_uci(mv) if mv else "0000"), int(sc), int(comp), int(A._NODES[0])


for name, fen, tl in (("m35", FENS[0][1], 64754), ("m36", FENS[1][1], 63313)):
    for rep in range(2):
        A._GAME_KEYS = []
        mv = A.get_move(fen, tl)
        print(f"R92 {TAG} {name} rep{rep} -> {mv}")

for name, fen in FENS:
    for d in (6, 7, 8):
        mv, sc, comp, nd = run(fen, depth=d)
        print(f"FIXDEPTH {TAG} {name:8s} d={d} -> {mv} score={sc:6d} nodes={nd:9d}")

# ---- 5. leak corpus A/B --------------------------------------------------
CORPUS_MS = int(os.environ.get("CORPUS_MS", "1200"))
rows = json.loads(open(os.path.join(TREE, "results/leak_suite/fens.json")).read())
t0 = time.perf_counter()
for i, r in enumerate(rows):
    fen = r.get("fen") or r.get("fen_before")
    mv, sc, comp, nd = run(fen, budget_ms=CORPUS_MS)
    print(f"CORPUS {TAG} {i:3d} {r.get('game','?')[-14:]:14s} "
          f"p{r.get('ply','?'):>3} -> {mv} score={sc:6d} depth={comp} nodes={nd}")
print(f"# corpus {time.perf_counter()-t0:.0f}s")
print("DONE")
