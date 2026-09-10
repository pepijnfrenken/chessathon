"""v9k ship-patch verification (BOX-LIGHT: pure import of engine.eval + numpy).

NO jitted call is made. njit decorators are lazy, so importing engine.board
and engine.eval compiles nothing and warms no numba cache.
"""
import importlib
import sys

import numpy as np

TREES = {"v8ref": "/tmp/chessathon-v8ref", "v9k": "/tmp/chessathon-v9k"}
P = {}

for name, root in TREES.items():
    sys.path.insert(0, root)
    for m in [m for m in list(sys.modules) if m.startswith("engine")]:
        del sys.modules[m]
    E = importlib.import_module("engine.eval")
    P[name] = dict(cfg=E._EVAL_CFG, vec=np.array(E.EVAL_PARAMS, copy=True),
                   idx=dict(mat_mg=E.P_MAT_MG, pst_mg=E.P_PST_MG,
                            pst_eg=E.P_PST_EG, king_eg_slot=5))
    sys.path.remove(root)

a, b = P["v8ref"]["vec"], P["v9k"]["vec"]
print(f"cfg: v8ref={P['v8ref']['cfg']}  v9k={P['v9k']['cfg']}")
print(f"len: v8ref={len(a)}  v9k={len(b)}")

diff = np.nonzero(a != b)[0]
print(f"\n--- 1. cells that differ: {len(diff)} ---")
PST_MG = 12
KING_MG_SLOT = (PST_MG + 5 * 64, PST_MG + 6 * 64)
print(f"king-MG slot range = [{KING_MG_SLOT[0]}, {KING_MG_SLOT[1]})")
print(f"all differing cells inside the king-MG slot: "
      f"{bool(((diff >= KING_MG_SLOT[0]) & (diff < KING_MG_SLOT[1])).all())}")
if len(diff):
    print(f"differing indices: {sorted(diff.tolist())}")
    print(f"min/max |delta|: {int(np.abs(b[diff]-a[diff]).min())} / "
          f"{int(np.abs(b[diff]-a[diff]).max())}")

print("\n--- 2. every OTHER PST slot byte-identical? ---")
labels = ["", "PAWN", "KNIGHT", "BISHOP", "ROOK", "QUEEN", "KING"]
ok = True
for mg_eg, base in (("MG", P["v8ref"]["idx"]["pst_mg"]),
                    ("EG", P["v8ref"]["idx"]["pst_eg"])):
    for t in range(1, 7):
        s = base + (t - 1) * 64
        same = np.array_equal(a[s:s + 64], b[s:s + 64])
        if not same:
            ok = False
        print(f"  {labels[t]:6s}_{mg_eg} [{s:>3}:{s+64:>3}] identical={same}")
print(f"  -> all non-king-MG slots identical: {ok}")
print(f"  clean default cells (12..780): identical="
      f"{np.array_equal(a[:780], b[:780])}")
print(f"  term weights (780..end):       identical="
      f"{np.array_equal(a[780:], b[780:])}")

print("\n--- 3. king-MG as READ (white s=sq64; black s=sq64^56) ---")
SQ = {"e1": 4, "g1": 6, "c1": 2, "e8": 60, "g8": 62, "c8": 58, "e4": 28}
for who in ("v8ref", "v9k"):
    vec = P[who]["vec"][KING_MG_SLOT[0]:KING_MG_SLOT[1]]
    print(f"  {who}: " + "  ".join(f"{k}={int(vec[i]):+d}" for k, i in SQ.items()))

print("\n--- 4. BLACK-side semantics (analytical, s = sq64 ^ 56) ---")
for who in ("v8ref", "v9k"):
    vec = P[who]["vec"][KING_MG_SLOT[0]:KING_MG_SLOT[1]]
    w_home = int(vec[4])          # white K on e1
    w_enemy = int(vec[60])        # white K on e8
    b_home = int(vec[60 ^ 56])    # black K on e8 -> index 4
    b_enemy = int(vec[4 ^ 56])    # black K on e1 -> index 60
    print(f"  {who}: white e1(home)={w_home:+d} e8(enemy)={w_enemy:+d} | "
          f"black e8(home)={b_home:+d} e1(enemy)={b_enemy:+d}")
    print(f"        home>enemy for BOTH colours: "
          f"{w_home > w_enemy and b_home > b_enemy}; "
          f"mirror-symmetric (w_home==b_home, w_enemy==b_enemy): "
          f"{w_home == b_home and w_enemy == b_enemy}")

print("\n--- 5. KING_EG slot and the six literal tables untouched? ---")
eg = P["v8ref"]["idx"]["pst_eg"] + 5 * 64
print(f"  KING_EG [{eg}:{eg+64}] identical: "
      f"{np.array_equal(a[eg:eg+64], b[eg:eg+64])}")
print(f"  KING_EG e1/e4/e8 (v9k): {int(b[eg+4]):+d}/{int(b[eg+28]):+d}/"
      f"{int(b[eg+60]):+d}")

print("\n--- 6. taper sanity (score = (mg*phase + eg*(24-phase))//24) ---")
for ph in (24, 16, 8, 0):
    d = -50
    print(f"  phase {ph:2d}: MG weight {ph/24:.2f} -> king flip worth "
          f"{int(d*ph/24):+d}cp")
print("DONE")
