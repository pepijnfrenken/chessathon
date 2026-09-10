#!/usr/bin/env python3
"""q5-v8dp: doubled-pawn file-indexing probe (dev tool, NOT shipped).

Isolates the doubled-pawn term THROUGH THE JITTED eval path. numba freezes
module-level numpy globals at compile time, so the parameter array cannot
be mutated at runtime; the isolation instead uses the committed eval's own
pawn-group gate (`CHESSATHON_EVAL_GATE=0111` disables the whole pawn
group: doubled + isolated + blocked + passed). Two child processes are
spawned with gate `1111` and `0111`; per FEN the difference

    jit_delta = evaluate_gate1111(st) - evaluate_gate0111(st)

is exactly the tapered pawn-group contribution.

The probe builds, for each file a-h, a position that is the same startpos
except that file f carries a DOUBLED white pawn pair (pawns on f2 and f3)
with material held constant (the (f+1)%8 rank-2 pawn is removed). Across
those eight positions the only pawn-structure feature that varies is the
doubled count: isolated = 0 everywhere, passed = 0 everywhere (rank-3
pawns are below the passed-rank window), blocked = 0 everywhere. Hence `jit_delta` differing between files is
exactly the doubled term differing.

Buggy indexing (`FILE_SQ[f * 8]`, f=0..7 -> a1..a8, i.e. the a-file eight
times) => the a-file delta carries 8 doubled pawns and b-h carry zero.
Fixed indexing (`FILE_SQ[f]`) => all eight deltas identical.

The mirror feature count (tools/texel_tune.py feature_vector, asserted
bit-parity with evaluate() by the tuner) is printed as a cross-check.

Usage:  python tools/probe_doubled_index.py [out.txt]
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

FILES = "abcdefgh"


def _rank(cells):
    """Compress an 8-cell rank ('', 'P', ...) to FEN form."""
    out, run = "", 0
    for c in cells:
        if c == "":
            run += 1
        else:
            if run:
                out += str(run)
                run = 0
            out += c
    if run:
        out += str(run)
    return out


def _donor(f):
    """A donor file whose rank-2 pawn can be removed without isolating any
    surviving pawn: never the doubled file, never one of its neighbours
    (and never the a/h edge, whose sole neighbour could be the donor)."""
    for j in (2, 3, 4, 5):
        if j not in (f - 1, f, f + 1):
            return j
    raise AssertionError(f)


def fen_white(f):
    """White doubled pair on file f (f2+f3); the donor file's rank-2 pawn
    is removed to hold material constant."""
    donor = _donor(f)
    r2 = _rank(["P" if i != donor else "" for i in range(8)])
    r3 = _rank(["P" if i == f else "" for i in range(8)])
    return f"rnbqkbnr/pppppppp/8/8/8/{r3}/{r2}/RNBQKBNR w - - 0 1"


def fen_black(f):
    """Mirror for the black loop (black doubled pair on rank 7+6)."""
    donor = _donor(f)
    r7 = _rank(["p" if i != donor else "" for i in range(8)])
    r6 = _rank(["p" if i == f else "" for i in range(8)])
    return f"rnbqkbnr/{r7}/{r6}/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"


def child(gate):
    """Child mode: print one JSON row per FEN under the given EVAL_GATE."""
    from engine import board as B
    from engine import eval as E
    import texel_tune as TT

    rows = []
    for side, builder in (("white", fen_white), ("black", fen_black)):
        for f in range(8):
            fen = builder(f)
            st = B.parse_fen(fen)
            feat, phase, forced_zero = TT.feature_vector(st)
            rows.append({
                "gate": gate, "side": side, "file": FILES[f], "fen": fen,
                "eval": int(E.evaluate(st)),
                "mirror_doubled": int(feat[E.P_DOUBLED_MG]),
                "phase": int(phase), "forced_zero": bool(forced_zero),
            })
    for r in rows:
        print(json.dumps(r), flush=True)


def main():
    out = open(sys.argv[1], "w") if len(sys.argv) > 1 else None

    def emit(line=""):
        print(line, flush=True)
        if out:
            print(line, file=out, flush=True)

    data = {}
    for gate in ("1111", "0111"):
        env = dict(os.environ, CHESSATHON_EVAL_GATE=gate)
        raw = subprocess.run([sys.executable, os.path.abspath(__file__),
                              "--child", gate], env=env, cwd=ROOT,
                             capture_output=True, text=True, check=True)
        for line in raw.stdout.splitlines():
            if line.startswith("{"):
                r = json.loads(line)
                data[(r["side"], r["file"], gate)] = r

    p = None
    from engine import eval as E
    p = E.EVAL_PARAMS
    emit("q5-v8dp doubled-pawn file-indexing probe (jitted path)")
    emit(f"params: P_DOUBLED_MG={int(p[E.P_DOUBLED_MG])} "
         f"P_DOUBLED_EG={int(p[E.P_DOUBLED_EG])} EVAL_CONFIG={E._EVAL_CFG}")
    emit("jit_delta = evaluate(gate=1111) - evaluate(gate=0111) = tapered "
         "pawn-group contribution")
    emit("all eight positions: isolated=0, passed=0, blocked=0 -> only the "
         "doubled count varies across files")
    verdict = {}
    for side in ("white", "black"):
        emit()
        emit(f"--- {side} doubled pawns (f2+f3 / f7+f6, material constant)")
        emit(f"{'file':4} {'eval_1111':>9} {'eval_0111':>9} "
             f"{'jit_delta':>9} {'mirror_dbl':>10} {'phase':>6}")
        deltas = []
        for f in FILES:
            a = data[(side, f, "1111")]
            b = data[(side, f, "0111")]
            d = a["eval"] - b["eval"]
            deltas.append(d)
            emit(f"{f:4} {a['eval']:9d} {b['eval']:9d} {d:9d} "
                 f"{a['mirror_doubled']:10d} {a['phase']:6d}")
        uniform = len(set(deltas)) == 1
        verdict[side] = uniform
        emit(f"verdict[{side}]: jit_delta identical on all eight files = "
             f"{'YES (fixed)' if uniform else 'NO (buggy: per-file counts differ)'}"
             f"  min={min(deltas)} max={max(deltas)}")
    emit()
    emit("FIXED iff both verdicts are YES (each file carries exactly one "
         "doubled pawn penalty).")
    emit(f"OVERALL: {'FIXED' if all(verdict.values()) else 'BUGGY'}")
    if out:
        out.close()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()
