"""Fixed-depth root outcome curves (r92 tunnel mechanism test).

Usage: TREE=/path/to/tree /tmp/chessbench/bin/python /tmp/aud6-probe2.py
Prints, for each test FEN and each max_depth 4..10, the ID outcome the
engine would play GIVEN UNLIMITED TIME UP TO THAT DEPTH (fresh TT each
time), plus a shared-TT run (the real ID behaviour) and node counts.
"""
import os, sys, time, json

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = os.environ.get("NC", "/tmp/aud6-np2-" + os.path.basename(TREE))
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

import numpy as np
import chess
from engine import board as B, search as S
import agent as A


def move_at(fen, depth, fresh=True):
    if fresh:
        A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._NODES[0] = 0
    st = B.parse_fen(fen)
    t0 = time.time()
    mv, sc, comp = S.search_root(st, A._NODES, S._NOW() + 3_600_000_000_000,
                                 A._TT_KEYS, A._TT_VALS, A._TT_MASK,
                                 A._KILLERS, A._HIST, A._REP, A._SCRATCH,
                                 A._SSCRATCH, depth,
                                 np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return B.move_to_uci(mv) if mv else "0000", int(sc), int(comp), int(A._NODES[0]), time.time() - t0


FENS = [
    ("m35 Qb3 site", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35"),
    ("m36 Rb5 site", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36"),
]
# r93 m49 (rootorder-class per PROCESS 14): derive from the PGN
pgn = os.path.join(TREE, "results/matches/round-93-vs-brokefish.pgn")
try:
    raw = open(pgn).read()
    game = chess.pgn.read_game(open(pgn))
    b = game.board()
    ply = 0
    for m in game.mainline_moves():
        if ply == 48:
            FENS.append(("r93 m49 site", b.fen()))
            break
        b.push(m); ply += 1
except Exception as e:
    print("pgn-derive failed", repr(e))

print(f"### TREE={TREE}")
for name, fen in FENS:
    print(f"-- {name}: {fen}")
    for d in range(4, 11):
        mv, sc, comp, nodes, dt = move_at(fen, d)
        print(f"   freshTT d={d:2d} -> {mv} score={sc:6d} completed={comp} nodes={nodes:9d} {dt:5.2f}s")
    # shared-TT sweep = the real iterative-deepening behaviour
    A._TT_KEYS.fill(0); A._TT_VALS.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0)
    for d in range(1, 11):
        A._NODES[0] = 0
        st = B.parse_fen(fen)
        mv, sc, comp = S.search_root(st, A._NODES, S._NOW() + 3_600_000_000_000,
                                     A._TT_KEYS, A._TT_VALS, A._TT_MASK,
                                     A._KILLERS, A._HIST, A._REP, A._SCRATCH,
                                     A._SSCRATCH, d,
                                     np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        print(f"   sharedTT d={d:2d} -> {B.move_to_uci(mv) if mv else '0000'} "
              f"score={int(sc):6d} nodes={int(A._NODES[0]):9d}")
print("DONE")
