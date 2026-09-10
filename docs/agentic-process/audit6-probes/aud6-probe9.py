"""C1 evidence probe — king PST orientation, measured through the jitted path.

Demo shape mirrors tools/probe_doubled_index.py: hold everything constant
except the king square and read the eval.

1. Dump the as-read PST value for a king on each square of the e-file, straight
   from the shipped param vector (no engine call needed).
2. Walk a white king e1->e8 in a fixed position and report evaluate() at each
   step, so the effect is visible through the real jitted eval path.

Usage: TREE=/path NC=<warm numba cache> /tmp/chessbench/bin/python /tmp/aud6-probe9.py
"""
import os, sys, time
from collections import defaultdict

TREE = os.environ["TREE"]
os.environ["NUMBA_CACHE_DIR"] = os.environ.get("NC", "/tmp/aud6-np9")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B, eval as E  # noqa: E402

S = "abcdefgh"
print(f"### TREE={TREE} cfg={E._EVAL_CFG}")

e_squares = [4 + 8 * r for r in range(8)]        # sq64 e1..e8
p = E.EVAL_PARAMS
print("-- as-read PST value, e-file (shipped params)")
for mg, tag in ((0, "MG"), (1, "EG")):
    for t, nm in ((6, "KING"), (4, "ROOK"), (5, "QUEEN"), (3, "BISHOP")):
        base = E.P_PST_MG + mg * 384 + (t - 1) * 64
        print(f"   {nm:6s} {tag} white e1..e8: "
              f"{' '.join(f'{sq}{int(p[base + sq]):+4d}' for sq in e_squares)}")
    base = E.P_PST_MG + mg * 384 + (6 - 1) * 64
    print(f"   KING   {tag} black e8..e1: "
          f"{' '.join(f'{sq}{int(p[base + (sq ^ 56)]):+4d}' for sq in reversed(e_squares))}")


def fen_of(pieces: dict, side: str = "w") -> str:
    ranks = defaultdict(dict)
    for sq, pc in pieces.items():
        ranks[int(sq[1])][sq[0]] = pc
    rows = []
    for rk in range(8, 0, -1):
        row, gap = "", 0
        for fl in S:
            pc = ranks[rk].get(fl)
            if pc:
                if gap:
                    row += str(gap); gap = 0
                row += pc
            else:
                gap += 1
        rows.append(row + (str(gap) if gap else ""))
    return "/".join(rows) + f" {side} - - 0 1"


BASE = {"a8": "p", "h8": "r", "b7": "p", "c7": "p", "f7": "p", "g7": "p",
        "h7": "p", "d6": "p", "f6": "n", "c4": "B", "e4": "P", "c3": "N",
        "f3": "N", "a2": "P", "b2": "P", "c2": "P", "f2": "P", "g2": "P",
        "h2": "P", "a1": "R", "h1": "R"}
print("-- white king walked e1..e8 (all other pieces fixed)")
prev = None
for sq in "e1 e2 e3 e4 e5 e6 e7 e8".split():
    pieces = dict(BASE)
    pieces[sq] = "K"
    fen = fen_of(pieces)
    t0 = time.perf_counter()
    v = int(E.evaluate(B.parse_fen(fen)))
    ms = (time.perf_counter() - t0) * 1000
    d = "" if prev is None else f"  delta={v - prev:+d}"
    print(f"   white K on {sq}: eval={v:+5d} ({ms:.1f}ms)  {fen}{d}")
    prev = v
print("DONE")
