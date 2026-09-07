"""Chessathon Phase 1b gate #2 — nps benchmarks (dev tool, NOT shipped).

Run: /tmp/chessbench/bin/python tools/bench_nps.py

Reports:
  1. perft nodes/s (movegen alone), startpos + kiwipete.
  2. search nodes/s and achieved depth for a fixed 5 s search on several
     positions (startpos, a middlegame, a sharp position).
Comparisons: research 01 measured pure-Python (python-chess board + our
1a-style search) at 18-34 knps; our phase-1a agent searched depth 3-5 in
~1.25 s. This benchmark shows the numba engine's numbers.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np  # noqa: E402

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

POSITIONS = [
    ("startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("middlegame", "r2q1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 8"),
    ("sharp", "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"),
]


def main() -> int:
    print("== perft nodes/s (our movegen) ==")
    for fen, depth in [("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 5),
                       ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 4)]:
        st = B.parse_fen(fen)
        t0 = time.perf_counter()
        n = B.perft(st, depth, B.MOVES, 0)
        dt = time.perf_counter() - t0
        print(f"  perft({depth}) {n} nodes in {dt:.2f}s -> "
              f"{n / dt / 1e6:.2f} Mnps")

    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)

    print("== search nps (5 s budget per position) ==")
    # warm the whole chain first so timing rows are JIT-free
    st0 = B.parse_fen(POSITIONS[0][1])
    S.search_root(st0, nodes, S._NOW() + 3_600_000_000_000, ttk, ttv, mask,
                  killers, hist, rep, scratch, sscratch, 3,
                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    for name, fen in POSITIONS:
        st = B.parse_fen(fen)
        nodes[:] = 0
        t0 = time.perf_counter()
        mv, score, depth = S.search_root(st, nodes, S._NOW() + 5_000_000_000,
                                         ttk, ttv, mask, killers, hist, rep,
                                         scratch, sscratch, 64,
                                         np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        dt = time.perf_counter() - t0
        print(f"  {name:10s} depth {depth:2d} nodes {nodes[0]:>9d} in "
              f"{dt:.2f}s -> {nodes[0] / dt / 1e3:.0f} knps (best "
              f"{B.move_to_uci(mv)}, score {score})")

    print("== reference: research-01 pure-Python search was 18-34 knps;"
          " 1a agent depth 3-5 in 1.25 s ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())