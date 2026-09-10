#!/usr/bin/env python3
"""q5-v8dp battery: eval_decompose <-> E.evaluate parity check (dev tool).

Runs tools/eval_decompose.py's own decompose() on a FEN sample and asserts
that the decomposition RECONSTRUCTS the jitted engine.eval.evaluate()
exactly, for both colors. Reconstruction (mirroring evaluate()'s tail):

    score = (mg*phase + eg*(MAX_PHASE-phase)) // MAX_PHASE      # taper
    score += sign(mat) * MATE_DRIVE_K * (7 - kdist)             # phase<=16,
                                                                # |mat|>=300
    eval  = score + tempo   (White to move)
    eval  = -(score + tempo) (Black to move)

`mg`/`eg` are the tool's total columns; `groups_mg_eg` carries tropism and
tempo, and `forced_zero` covers the insufficient-material early return.
Per-term display rows for mobility/king-safety are NOT used — the tool
mixes interleaved MG/EG indices in those rows (documented, not in scope).

Usage:  python tools/check_decompose_parity.py [fens.json] [out.json]
Default FEN list = results/leak_suite/fens.json + mate_stratum.json +
four standard positions.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

from engine import board as B  # noqa: E402
from engine import eval as E  # noqa: E402
from eval_decompose import decompose  # noqa: E402

EXTRA = [
    ("startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("r83-p21", "r3k2r/ppq1bppp/2p1p3/2P5/P2P4/2B1P3/4QPPP/R4RK1 b kq - 4 18"),
    ("kq-vs-k", "7k/8/8/8/8/8/8/KQ6 w - - 0 1"),
]


def load(path):
    return json.load(open(path))


def main():
    if len(sys.argv) > 1 and sys.argv[1]:
        rows = load(sys.argv[1])
    else:
        rows = []
        for name in ("results/leak_suite/fens.json",
                     "results/leak_suite/mate_stratum.json"):
            p = os.path.join(ROOT, name)
            if os.path.exists(p):
                tag = os.path.basename(p).split(".")[0]
                for e in load(p):
                    rows.append({"id": f"{tag}/{e.get('game','?')}/p{e.get('ply','?')}",
                                 "fen": e["fen_before"]})
        for n, f in EXTRA:
            rows.append({"id": n, "fen": f})

    out = []
    n_ok = n_bad = 0
    for e in rows:
        st = B.parse_fen(e["fen"])
        d = decompose(st)
        mg, eg = d["mg"], d["eg"]
        ph = min(d["phase"], E.MAX_PHASE)
        score = (mg * ph + eg * (E.MAX_PHASE - ph)) // E.MAX_PHASE
        # mate-drive term (needs raw material, which the decomposition does
        # not expose; recompute from the board the same way evaluate() does)
        sqr = st["squares"][0]
        mat = 0
        for s in range(128):
            if s & 0x88:
                continue
            pc = int(sqr[s])
            if pc == 0:
                continue
            t = abs(pc)
            mat += int(E.EVAL_PARAMS[E.P_MAT_MG + t - 1]) * \
                (1 if pc > 0 else -1)
        drive = 0
        if ph <= 16 and (mat >= 300 or mat <= -300):
            # recompute kdist exactly as evaluate() does (sq64 space)
            wks = B.sq64(int(st["kingsq"][0][B.WHITE]))
            bks = B.sq64(int(st["kingsq"][0][B.BLACK]))
            kdist = max(abs((wks & 7) - (bks & 7)), abs((wks >> 3) - (bks >> 3)))
            drive = (1 if mat > 0 else -1) * E.MATE_DRIVE_K * (7 - kdist)
        score += drive
        tempo = int(E.EVAL_PARAMS[E.P_TEMPO]) * int(E.EVAL_GATE[3])
        if d["forced_zero"]:
            expect = 0
        elif int(st["side"][0]) == B.WHITE:
            expect = score + tempo
        else:
            expect = -(score + tempo)
        got = int(E.evaluate(st))
        ok = got == expect
        n_ok += ok
        n_bad += (not ok)
        out.append({"id": e["id"], "fen": e["fen"], "side":
                    "w" if int(st["side"][0]) == B.WHITE else "b",
                    "decompose_mg": mg, "decompose_eg": eg, "phase": ph,
                    "forced_zero": d["forced_zero"], "mat": mat,
                    "mate_drive": drive, "reconstructed": expect,
                    "jitted_eval": got, "exact": bool(ok)})
        print(f"{'OK ' if ok else 'BAD'} {e['id'][:44]:46} "
              f"mg={mg:7d} eg={eg:7d} ph={ph:2d} drive={drive:4d} "
              f"recon={expect:7d} jitted={got:7d}", flush=True)

    print(f"\nparity: {n_ok}/{n_ok + n_bad} exact"
          f"{'' if n_bad == 0 else ' — MISMATCHES PRESENT'}")
    if len(sys.argv) > 2:
        json.dump(out, open(sys.argv[2], "w"), indent=1)
        print(f"wrote {sys.argv[2]}")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
