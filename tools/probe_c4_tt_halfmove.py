#!/usr/bin/env python3
"""q5-c4 probe: TT fifty-move context (dev tool, NOT shipped).

Audit-6 §C4 (codex5 F4): a transposition-table entry carries no fifty-move
context, so a WARM entry can override a fifty-move draw that a COLD search
sees. Measured shape: `7k/8/8/8/8/8/8/KR6 w - - 99 1` at depth 2 scores 0
with an empty TT, and 593 once the identical PLACEMENT has been searched at
halfmove 0 in the same process.

The probe runs three readings of the same FEN per tree:

  A. COLD      — fresh TT, search the hm=99 position            (the truth)
  B. WARM-same — search it twice in one process, one TT: the second read
                 is the "identical placement, warm entry" case
  C. WARM-0    — same TT: first search the SAME BOARD at halfmove 0 (which
                 legitimately has a different value), then the hm=99
                 position. This is the hostile ordering.

After the fix B and C must both equal A. Repeat for a second position in a
little more material (`7k/8/8/8/8/8/8/K2R4 w - - 99 1`) so the reading is
not a single-FEN artifact.

Usage:  python tools/probe_c4_tt_halfmove.py [out.txt] [--root TREE]
        --root runs the same probe against a control tree without
        touching it (e.g. /tmp/chessathon-v9k-base).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "--root" in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
sys.path.insert(0, ROOT)
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

DEPTH = 2
# (label, hot FEN at hm 99, the same board at hm 0)
CASES = [
    ("KRvK", "7k/8/8/8/8/8/8/KR6 w - - 99 1", "7k/8/8/8/8/8/8/KR6 w - - 0 1"),
    ("KRvK+", "7k/8/8/8/8/8/8/K2R4 w - - 99 1", "7k/8/8/8/8/8/8/K2R4 w - - 0 1"),
]


def fresh():
    ttk, ttv = TT.make()
    return (ttk, ttv, np.uint64(len(ttk) - 1),
            np.zeros((2, B.MAX_PLY), dtype=np.int32),
            np.zeros((2, 64, 64), dtype=np.int32),
            np.zeros(S.REP_SIZE, dtype=np.uint64),
            np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32),
            np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32),
            np.zeros(1, dtype=np.int64))


def run(fen, tt):
    ttk, ttv, mask, killers, hist, rep, scratch, sscratch, nodes = tt
    st = B.parse_fen(fen)
    return S.search(st, DEPTH, -S.INF, S.INF, 1, nodes, S._NOW() + 10**13,
                    ttk, ttv, mask, killers, hist, rep, scratch, sscratch)


def main():
    out_path = next((a for a in sys.argv[1:]
                     if not a.startswith("--")
                     and a != (sys.argv[sys.argv.index("--root") + 1]
                               if "--root" in sys.argv else None)), None)
    out = open(out_path, "w") if out_path else None

    def emit(line=""):
        print(line, flush=True)
        if out:
            print(line, file=out, flush=True)

    emit(f"q5-c4 TT fifty-move-context probe — tree: {ROOT}")
    emit(f"(depth {DEPTH}; A = cold/fresh TT = the truth; B/C = warm TT)")
    run("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", fresh())
    emit(f"{'case':8} {'A cold':>8} {'B warm-same':>12} {'C warm-hm0':>11} "
         f"{'verdict':>10}")
    bad = 0
    for label, hot, cold0 in CASES:
        a = run(hot, fresh())

        # B: same position twice, one TT
        tt = fresh()
        run(hot, tt)
        b = run(hot, tt)

        # C: the hm-0 placement first, then the hm-99 one, same TT
        tt = fresh()
        run(cold0, tt)
        c = run(hot, tt)

        ok = (a == b == c)
        bad += (not ok)
        emit(f"{label:8} {a:8d} {b:12d} {c:11d} {'OK' if ok else 'MISMATCH':>10}")
    emit()
    emit(f"failures: {bad}  (a failure = a warm TT changing the score of a "
         f"fifty-move-drawn position)")
    if out:
        out.close()
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
