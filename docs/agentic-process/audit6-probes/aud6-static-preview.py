"""C1 static preview — pure python-chess + raw table literals (NO numba, NO engine).

Parses the PST literals straight out of engine/eval.py source (regex on the
np.array([...]) blocks) so nothing imports numba, computes, for each leak-suite
FEN, the middlegame PST contribution of each non-pawn piece class as-read vs
after a row flip, and reports per-row deltas plus material sign-flip risks.

Run anywhere; costs milliseconds and no engine process.
"""
import json
import re
import sys
from collections import defaultdict

import numpy as np
import chess

SRC = "/tmp/chessathon-aud6/engine/eval.py"
FENS = "/tmp/chessathon-aud6/results/leak_suite/fens.json"


def parse_table(name: str) -> np.ndarray:
    txt = open(SRC).read()
    m = re.search(rf"^{name} = np\.array\(\[(.*?)\], dtype=np\.int16\)",
                  txt, re.S | re.M)
    if not m:
        raise SystemExit(f"table {name} not found")
    nums = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
    assert len(nums) == 64, (name, len(nums))
    return np.array(nums, dtype=np.int64)


T = {n: parse_table(f"_{n}") for n in
     ("PAWN_MG", "KNIGHT_MG", "BISHOP_MG", "ROOK_MG", "QUEEN_MG", "KING_MG")}
FLIP = {n: t.reshape(8, 8)[::-1].ravel() for n, t in T.items()}

# sq64 from python-chess square index (a1=0 .. h8=63) — same convention.
PIECE_TBL = {chess.PAWN: "PAWN_MG", chess.KNIGHT: "KNIGHT_MG",
             chess.BISHOP: "BISHOP_MG", chess.ROOK: "ROOK_MG",
             chess.QUEEN: "QUEEN_MG", chess.KING: "KING_MG"}
NONPAWN = ("KNIGHT_MG", "BISHOP_MG", "ROOK_MG", "QUEEN_MG", "KING_MG")


def pst_delta(board: chess.Board, tables) -> dict:
    """White-minus-black PST total per piece class, using `tables`."""
    out = defaultdict(int)
    for sq, pc in board.piece_map().items():
        name = PIECE_TBL[pc.piece_type]
        s = sq if pc.color == chess.WHITE else (sq ^ 56)
        v = int(tables[name][s])
        out[name] += v if pc.color == chess.WHITE else -v
    return out


rows = json.loads(open(FENS).read())
print(f"# leak-suite rows: {len(rows)}")
print("# per-row: total MG non-pawn PST delta (as-read -> flipped), mover POV")
print(f"{'idx':>4} {'game':16s} {'ply':>4} {'side':5s} "
      f"{'as_read':>8} {'flipped':>8} {'delta':>7}  dominant class")

moved = []
class_tot = defaultdict(int)
for i, r in enumerate(rows):
    fen = r.get("fen") or r.get("fen_before")
    if not fen:
        continue
    b = chess.Board(fen)
    mover_white = b.turn == chess.WHITE
    a = pst_delta(b, T)
    f = pst_delta(b, FLIP)
    # mover POV sign
    sgn = 1 if mover_white else -1
    a_tot = sgn * sum(a[n] for n in NONPAWN)
    f_tot = sgn * sum(f[n] for n in NONPAWN)
    d = f_tot - a_tot
    # which class dominates this row's delta
    per_class = {n: sgn * (f[n] - a[n]) for n in NONPAWN}
    dom = max(per_class, key=lambda n: abs(per_class[n]))
    for n in NONPAWN:
        class_tot[n] += abs(per_class[n])
    if abs(d) >= 10:
        moved.append((i, r.get("game", "?"), r.get("ply"), r.get("side"),
                      a_tot, f_tot, d, dom, per_class[dom]))
    print(f"{i:4d} {r.get('game','?')[-16:]:16s} {str(r.get('ply','?')):>4} "
          f"{str(r.get('side','?')):5s} {a_tot:8d} {f_tot:8d} {d:7d}  "
          f"{dom}={per_class[dom]:+d}")

print()
print(f"# rows with |delta| >= 10 cp: {len(moved)}/{len(rows)}")
if moved:
    ds = np.array([m[6] for m in moved])
    print(f"#   delta min/mean/max (mover POV): {ds.min()} / {ds.mean():.1f} / {ds.max()}")
    print(f"#   rows where flip IMPROVES the mover: {int((ds > 0).sum())}, "
          f"worsens: {int((ds < 0).sum())}")
print("# absolute per-class contribution to those deltas (sign-agnostic):")
for n in NONPAWN:
    print(f"#   {n:10s} {class_tot[n]:7d}")
print("DONE")
