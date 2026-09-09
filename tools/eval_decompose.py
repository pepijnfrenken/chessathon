#!/usr/bin/env python3
"""q5-fix1 Mission B: static-eval term decomposition on pre-leak FENs
(dev tool, NOT shipped).

For each FEN, derives the eval's feature vector (the Texel tuner's
bit-parity-verified numpy mirror of evaluate()) and decomposes the
White-POV score into: material, per-piece-class PST (mg/eg separately),
pawn structure, mobility, king safety, king tropism, bishop pair,
tempo — plus per-side PST sub-totals (mover/opponent POV) and a raw
coordinate dump of the pawn/king PST entries each side actually reads.

Usage:
  python tools/eval_decompose.py <fens.json> [out.json]

fens.json format: list of {"id": ..., "fen": ...} (extra keys ignored).
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "tools"))
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

from engine import board as B  # noqa: E402
from engine import eval as E  # noqa: E402
import texel_tune as TT  # noqa: E402

P = E.EVAL_PARAMS  # hand config (default import)
assert len(P) == E.N_PARAMS

PIECES = ["PAWN", "KNIGHT", "BISHOP", "ROOK", "QUEEN", "KING"]


def decompose(st):
    f, phase, forced_zero = TT.feature_vector(st)
    mg_total = int(f[TT.MG_IDXS] @ P[TT.MG_IDXS])
    eg_total = int(f[TT.EG_IDXS] @ P[TT.EG_IDXS])
    if phase > E.MAX_PHASE:
        ph = E.MAX_PHASE
    else:
        ph = phase
    tapered = (mg_total * ph + eg_total * (E.MAX_PHASE - ph)) // E.MAX_PHASE

    out = {"phase": int(phase), "forced_zero": bool(forced_zero),
           "mg": mg_total, "eg": eg_total, "tapered_pretampo": tapered}

    groups = {}
    # material
    mat_mg = mat_eg = 0
    for t in range(1, 7):
        mat_mg += int(f[E.P_MAT_MG + t - 1]) * int(P[E.P_MAT_MG + t - 1])
        mat_eg += int(f[E.P_MAT_EG + t - 1]) * int(P[E.P_MAT_EG + t - 1])
    groups["material"] = (mat_mg, mat_eg)
    # per-piece PST
    pst = {}
    for t in range(1, 7):
        sl = slice(E.P_PST_MG + (t - 1) * 64, E.P_PST_MG + t * 64)
        mgv = int(f[sl] @ P[sl])
        sl = slice(E.P_PST_EG + (t - 1) * 64, E.P_PST_EG + t * 64)
        egv = int(f[sl] @ P[sl])
        pst[PIECES[t - 1]] = (mgv, egv)
    groups["pst"] = pst
    # positional groups
    for name, (im, ie) in {
        "pawn_struct": (E.P_DOUBLED_MG, E.P_DOUBLED_EG),
        "mobility": (E.P_MOB_N_MG, E.P_MOB_N_EG),
        "king_safety": (E.P_SHELTER_NEAR_MG, E.P_SHELTER_NEAR_EG),
    }.items():
        if name == "pawn_struct":
            idxs_m = list(range(E.P_DOUBLED_MG, E.P_DOUBLED_MG + 2)) + \
                list(range(E.P_PASSED_MG, E.P_PASSED_MG + 4))
            idxs_e = list(range(E.P_DOUBLED_EG, E.P_DOUBLED_EG + 2)) + \
                list(range(E.P_PASSED_EG, E.P_PASSED_EG + 4))
        elif name == "mobility":
            idxs_m = list(range(E.P_MOB_N_MG, E.P_MOB_N_MG + 4))
            idxs_e = list(range(E.P_MOB_N_EG, E.P_MOB_N_EG + 4))
        else:
            idxs_m = list(range(E.P_SHELTER_NEAR_MG, E.P_SHELTER_NEAR_MG + 4))
            idxs_e = list(range(E.P_SHELTER_NEAR_EG, E.P_SHELTER_NEAR_EG + 4))
        groups[name] = (
            int(f[idxs_m] @ P[idxs_m]), int(f[idxs_e] @ P[idxs_e]))
    groups["bishop_pair"] = (
        int(f[E.P_BISHOP_PAIR_MG]) * int(P[E.P_BISHOP_PAIR_MG]),
        int(f[E.P_BISHOP_PAIR_EG]) * int(P[E.P_BISHOP_PAIR_EG]))
    groups["tropism"] = (int(f[E.P_KDIST_MG]) * int(P[E.P_KDIST_MG]),
                         int(f[E.P_KDIST_EG]) * int(P[E.P_KDIST_EG]))
    groups["tempo"] = (int(P[E.P_TEMPO]), int(P[E.P_TEMPO]))
    out["groups_mg_eg"] = groups

    # ---- raw PST coordinate tables per side (what each color reads) ----
    # White reads s = sq64(sq); Black reads s = sq64(sq) ^ 56.
    # Report each side's king square and the raw table value it receives.
    sqr = st['squares'][0]
    ksq = {B.WHITE: int(st['kingsq'][0][B.WHITE]),
           B.BLACK: int(st['kingsq'][0][B.BLACK])}
    kings = {}
    for color, sq in ksq.items():
        s = B.sq64(sq)
        if color == B.BLACK:
            s ^= 56
        kings["white" if color == B.WHITE else "black"] = {
            "sq64": s,
            "algebraic_from": B.sq64(sq),
            "king_mg_raw": int(P[E.P_PST_MG + 5 * 64 + s]),
            "king_eg_raw": int(P[E.P_PST_EG + 5 * 64 + s]),
        }
    out["kings"] = kings
    return out


def main():
    fens_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    rows = json.load(open(fens_path))
    results = []
    for e in rows:
        st = B.parse_fen(e["fen"])
        d = decompose(st)
        d["id"] = e.get("id", "")
        d["fen"] = e["fen"]
        d["side"] = e.get("side", "?")
        # engine's actual returned static eval (mover POV), for parity
        d["eval_mover_pov"] = int(E.evaluate(st))
        results.append(d)
    blob = json.dumps(results, indent=1)
    if out_path:
        with open(out_path, "w") as fh:
            fh.write(blob)
        print(f"wrote {out_path} ({len(results)} rows)")
    else:
        print(blob)


if __name__ == "__main__":
    main()
