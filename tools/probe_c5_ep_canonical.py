#!/usr/bin/env python3
"""q5-c5 probe: EP-square canonicalisation parity (dev tool, NOT shipped).

Audit-6 §C5 (root cause of codex5 F3): `parse_fen` and `make_move_apply` do
NOT agree on when the ep square exists *and is capturable*.

  * `make_move_apply` sets the ep square after a double push whenever an
    enemy pawn merely SITS beside the landing square (pseudo-legal).
  * `parse_fen` keeps whatever ep square the FEN text declares, untested.

python-chess — the legality oracle this project validates against — keeps
an ep square only while `has_legal_en_passant()` holds, i.e. it is
PIN-AWARE. So both engine paths can hash a ZEP term that the canonical
position does not have, and the same board reached by play and by FEN then
gets two different zobrist keys (the audit measured
9490302469568603911 vs 3009738484286385424) — breaking repetition identity
and causing TT misses.

Three families are checked, each against python-chess:

  F3-repetition : `3k4/8/8/8/3p4/8/4P3/K2R4 w - - 0 1` — the black d4 pawn
                  is PINNED by Rd1, so after e2e4 the ep capture d4xe3 is
                  ILLEGAL and python-chess clears the ep square. Our engine
                  must agree (key after e2e4 == key of python-chess's
                  canonical FEN), and the cycle e2e4 d8e8 a1b1 e8d8 b1a1
                  must return to a repeated key.
  no-overcorrect: `3k4/8/8/8/3p4/8/4P3/KR6 w - - 0 1` — d4 is NOT pinned,
                  so after e2e4 the ep capture IS legal and must be kept
                  (both sides), and the ep capture must still be generated.
  raw-fen       : `3k4/8/8/3pP3/8/8/8/K2R4 b - e6 0 1` — the FEN declares
                  ep=e6 while the capture d5xe6 is illegal (pinned): the
                  parsed key must match python-chess's canonical FEN.

Usage:  python tools/probe_c5_ep_canonical.py [out.txt] [--root TREE]
        --root runs the same probe against a control tree (e.g.
        /tmp/chessathon-v9k-base) without touching it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "--root" in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
sys.path.insert(0, ROOT)
os.environ.setdefault("NUMBA_CACHE_DIR", f"/tmp/numba_epc_{os.path.basename(ROOT)}")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import chess  # noqa: E402

from engine import board as B  # noqa: E402

REP_START = "3k4/8/8/8/3p4/8/4P3/K2R4 w - - 0 1"
FREE_START = "3k4/8/8/8/3p4/8/4P3/KR6 w - - 0 1"
RAWFEN = "3k4/8/8/3pP3/8/8/8/K2R4 b - e6 0 1"


def apply_uci(st, uci):
    """Generate legal moves from `st` and apply `uci`; returns the move int."""
    moves = np.zeros(B.MAX_MOVES, dtype=np.int32)
    cnt = B.legal_moves(st, moves, False)
    for i in range(cnt):
        if B.move_to_uci(moves[i]) == uci:
            caps = {k: st[k][0] for k in ("castle", "ep", "halfmove", "key")}
            B.make_move_apply(st, moves[i])
            return moves[i], caps
    raise AssertionError(f"{uci} not legal in {B.to_fen(st)}")


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

    emit(f"q5-c5 EP canonicalisation parity probe — tree: {ROOT}")
    emit(f"{'check':46} {'engine':>22} {'python-chess':>22}  verdict")
    bad = 0

    def row(name, eng, pc, ok):
        nonlocal bad
        bad += (not ok)
        emit(f"{name:46} {str(eng):>22} {str(pc):>22}  {'OK' if ok else 'MISMATCH'}")

    # ---- F3: pinned double push must not keep an ep square -------------
    b = chess.Board(REP_START)
    b.push_uci("e2e4")
    pc_fen = b.fen()
    pc_key = int(B.parse_fen(pc_fen)["key"][0])
    st = B.parse_fen(REP_START)
    apply_uci(st, "e2e4")
    eng_key = int(st["key"][0])
    row("F3: key after pinned e2e4 == canonical FEN", eng_key, pc_key,
        eng_key == pc_key)
    row("F3: engine ep square after pinned e2e4", int(st["ep"][0]),
        "-1" if " - " in pc_fen.split(" ")[3] else "kept",
        int(st["ep"][0]) == -1)

    # ---- F3 cycle: the position must repeat ---------------------------
    st = B.parse_fen(REP_START)
    keys = [int(st["key"][0])]
    for uci in ("e2e4", "d8e8", "a1b1", "e8d8", "b1a1"):
        apply_uci(st, uci)
        keys.append(int(st["key"][0]))
    bc = chess.Board(REP_START)
    for uci in ("e2e4", "d8e8", "a1b1", "e8d8", "b1a1"):
        bc.push_uci(uci)
    pc_rep = bc.is_repetition(2)
    eng_rep = keys[-1] in keys[:-1]
    row("F3 cycle: engine sees the repeat (python-chess is_repetition(2))",
        eng_rep, pc_rep, eng_rep == pc_rep)

    # ---- no over-correction: a LEGAL ep must be kept -------------------
    b = chess.Board(FREE_START)
    b.push_uci("e2e4")
    pc_fen = b.fen()
    pc_ep = pc_fen.split()[3]
    pc_key = int(B.parse_fen(pc_fen)["key"][0])
    st = B.parse_fen(FREE_START)
    apply_uci(st, "e2e4")
    row("free: ep square kept after unpinned e2e4", B.to_fen(st).split()[3],
        pc_ep, B.to_fen(st).split()[3] == pc_ep)
    row("free: key after unpinned e2e4 == canonical FEN",
        int(st["key"][0]), pc_key, int(st["key"][0]) == pc_key)
    moves = np.zeros(B.MAX_MOVES, dtype=np.int32)
    cnt = B.legal_moves(st, moves, False)
    ucis = sorted({B.move_to_uci(moves[i]) for i in range(cnt)})
    row("free: d4xe3 e.p. is still generated", "d4e3" in ucis,
        "d4e3" in {m.uci() for m in b.legal_moves}, "d4e3" in ucis)

    # ---- raw FEN: illegal declared ep must be canonicalised away -------
    bc = chess.Board(RAWFEN)
    pc_fen = bc.fen()
    pc_key = int(B.parse_fen(pc_fen)["key"][0])
    st = B.parse_fen(RAWFEN)
    row("raw FEN: declared illegal ep canonicalised away",
        int(st["ep"][0]), "-1", int(st["ep"][0]) == -1)
    row("raw FEN: key == python-chess canonical FEN",
        int(st["key"][0]), pc_key, int(st["key"][0]) == pc_key)

    emit()
    emit(f"failures: {bad}")
    if out:
        out.close()
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
