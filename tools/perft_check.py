"""Chessathon Phase 1b gate #1 — perft parity vs python-chess + published
values. Dev tool, NOT shipped in agent.zip.

Run: /tmp/chessbench/bin/python tools/perft_check.py

Checks:
  1. Our perft(1..5) matches published reference values on 6 positions
     (startpos, Kiwipete, and 4 varied FENs).
  2. Our perft counts match python-chess (the legal-move oracle) on the
     same positions at depths small enough for python-chess (~100 knps).
  3. Move-type breakdowns (captures/ep/castles/promotions/checks) match
     python-chess at depth 2-3 — this catches legality-class bugs that
     node totals can hide.
Exit code 0 iff everything matches.
"""
import sys
import time
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import board as B  # noqa: E402

# ---------------------------------------------------------------------------
# Reference positions + published perft values (standard chess-programming
# test suite numbers). The values are *data* used for verification only.
# ---------------------------------------------------------------------------
POSITIONS = [
    ("startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
     {1: 20, 2: 400, 3: 8902, 4: 197281, 5: 4865609}),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     {1: 48, 2: 2039, 3: 97862, 4: 4085603, 5: 193690690}),
    ("pos3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
     {1: 14, 2: 191, 3: 2812, 4: 43238, 5: 674624}),
    ("pos4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     {1: 6, 2: 264, 3: 9467, 4: 422333}),
    ("pos5", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
     {1: 44, 2: 1486, 3: 62379, 4: 2103487}),
    ("pos6", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
     {1: 46, 2: 2079, 3: 89890, 4: 3894594}),
]


def pc_perft(board, depth):
    """python-chess perft (slow oracle; use small depths only)."""
    if depth == 0:
        return 1
    n = 0
    for mv in board.legal_moves:
        board.push(mv)
        n += pc_perft(board, depth - 1)
        board.pop()
    return n


def pc_breakdown(board, depth):
    """python-chess perft with move-type breakdown:
    (nodes, captures, ep, castles, promos, checks)."""
    c = [0, 0, 0, 0, 0, 0]

    def rec(b, d):
        if d == 0:
            c[0] += 1
            if b.is_check():
                c[5] += 1
            return
        for mv in b.legal_moves:
            # classify before push: these all depend on the pre-move board
            cap = b.is_capture(mv)
            ep = b.is_en_passant(mv)
            castle = b.is_castling(mv)
            promo = mv.promotion
            b.push(mv)
            if cap:
                c[1] += 1
            if ep:
                c[2] += 1
            if castle:
                c[3] += 1
            if promo:
                c[4] += 1
            rec(b, d - 1)
            b.pop()

    rec(board, depth)
    return tuple(c)


def main() -> int:
    fails = 0

    print("== 1. our perft vs published reference values ==")
    for name, fen, ref in POSITIONS:
        st = B.parse_fen(fen)
        row = []
        for d, want in sorted(ref.items()):
            t0 = time.perf_counter()
            got = B.perft(st, d, B.MOVES, 0)
            dt = time.perf_counter() - t0
            nps = got / dt / 1e6 if dt else 0.0
            ok = got == want
            fails += (not ok)
            row.append(f"d{d}={got}{' OK' if ok else ' FAIL(want %d)' % want}"
                       f" [{nps:.2f} Mnps]")
        print(f"  {name:10s} " + "  ".join(row))

    print("== 2. our perft vs python-chess oracle (small depths) ==")
    for name, fen, ref in POSITIONS:
        st = B.parse_fen(fen)
        depth = min(3, max(ref))
        t0 = time.perf_counter()
        ours = B.perft(st, depth, B.MOVES, 0)
        pc = pc_perft(chess.Board(fen), depth)
        dt = time.perf_counter() - t0
        ok = ours == pc
        fails += (not ok)
        print(f"  {name:10s} depth {depth}: ours={ours} python-chess={pc}"
              f" {'OK' if ok else 'FAIL'} [{dt:.1f}s]")

    print("== 3. move-type breakdown vs python-chess (depth 2-3) ==")
    for name, fen, ref in POSITIONS:
        st = B.parse_fen(fen)
        depth = 2 if name == "pos5" else 3
        ours = B.perft_breakdown(st, depth, B.MOVES)
        theirs = pc_breakdown(chess.Board(fen), depth)
        ok = ours == theirs
        fails += (not ok)
        print(f"  {name:10s} d{depth}: ours={ours}")
        print(f"  {' ' * 11} pc  ={theirs}  {'OK' if ok else 'FAIL'}")

    print("== result:", "ALL PASS" if fails == 0 else f"{fails} FAILURES")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())