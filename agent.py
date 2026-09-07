"""Chessathon Phase 1b agent — numba-jitted engine front end.

Exposes `get_move(fen: str, time_left_ms: int) -> str` returning a legal
UCI move, replacing the Phase-1a pure-Python engine's internals with
`engine/` (our own board, eval, TT and search cores, all fresh code in
this repo — see ORIGINALITY.md + BUILD.md).

Import-time contract:
  - NUMBA_CACHE_DIR pinned to /tmp scratch (the repo is read-only at
    runtime on the competition box) before numba compiles anything.
  - The jitted search chain is WARMED UP here so compilation happens
    inside the 60 s init budget, not on the first move.
  - No torch import (saves ~1 s and hundreds of MB of RSS).

Per-call contract:
  - Parse FEN into our board once, search with a time budget from
    engine/time.py (competition clock 120 s + 0.5 s/move; the caller
    only reports total remaining time, so we assume +500 ms increment),
    convert our move to UCI, and verify it with python-chess as oracle.
  - Any failure falls back to a legal python-chess move: never illegal,
    never crash, never hang. Returns "0000" when the game is over.
"""

import os
import sys
import time

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import chess  # noqa: E402

from engine import board as B  # noqa: E402
from engine import eval as E  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402
from engine import time as TM  # noqa: E402

_INC_MS = 500                 # competition clock increment (120s + 0.5s)
_MAX_DEPTH = 64               # ID hard cap (time-limited in practice)

# Shared, long-lived search state (persists across get_move calls: the TT
# and history heuristics carry real value between moves).
_TT_KEYS, _TT_VALS = TT.make()
_TT_MASK = np.uint64(len(_TT_KEYS) - 1)
_KILLERS = np.zeros((2, B.MAX_PLY), dtype=np.int32)
_HIST = np.zeros((2, 64, 64), dtype=np.int32)
_REP = np.zeros(B.MAX_PLY + 8, dtype=np.uint64)
_SCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_SSCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_NODES = np.zeros(1, dtype=np.int64)

_WARMED = False


def _warmup() -> float:
    """Compile the jitted chain on a trivial position; returns seconds.
    Must cover the full recursion: a search_root call with an expired
    deadline would break before ever touching search(), leaving the real
    compile cost in the first move."""
    t0 = time.perf_counter()
    st = B.parse_fen(chess.STARTING_FEN)
    far = S._NOW() + 3_600_000_000_000
    # moves + legality + eval + search/qsearch recursion
    S.search(st, 2, -S.INF, S.INF, 1, _NODES, far, _TT_KEYS, _TT_VALS,
             _TT_MASK, _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH)
    # iterative root loop on top
    S.search_root(st, _NODES, far, _TT_KEYS, _TT_VALS, _TT_MASK,
                  _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 3)
    return time.perf_counter() - t0


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal UCI move for the given FEN."""
    global _WARMED
    if not _WARMED:
        w = _warmup()
        _WARMED = True
        print(f"[chessathon] numba warmup {w:.1f}s (init budget ok)",
              file=sys.stderr)
    t0 = time.perf_counter()
    try:
        pc_board = chess.Board(fen)
        if pc_board.is_game_over():
            return "0000"

        st = B.parse_fen(fen)
        budget_ms = TM.budget_ms(int(time_left_ms), _INC_MS)
        deadline = S._NOW() + int(budget_ms * 1_000_000)
        _NODES[0] = 0
        mv, score, depth = S.search_root(
            st, _NODES, deadline, _TT_KEYS, _TT_VALS, _TT_MASK,
            _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, _MAX_DEPTH)

        if mv == 0:
            # no legal move from our side: game-over position
            legal = list(pc_board.legal_moves)
            return "0000" if not legal else legal[0].uci()

        uci = B.move_to_uci(mv)
        m = chess.Move.from_uci(uci)
        if m not in pc_board.legal_moves:
            # belt-and-braces: our move must always be legal
            print(f"[chessathon] WARNING illegal move {uci}, falling back",
                  file=sys.stderr)
            legal = list(pc_board.legal_moves)
            return legal[0].uci()
        elapsed = (time.perf_counter() - t0) * 1000
        if elapsed > budget_ms * 1.5 + 100:
            print(f"[chessathon] slow move: {elapsed:.0f}ms (budget "
                  f"{budget_ms}ms), depth {depth}", file=sys.stderr)
        return uci
    except Exception as exc:  # never crash: always play a legal move
        print(f"[chessathon] engine error {exc!r}; fallback legal move",
              file=sys.stderr)
        try:
            return list(chess.Board(fen).legal_moves)[0].uci()
        except Exception:
            return "0000"


# ---------------------------------------------------------------------------
# Self-test: `python agent.py` plays a short game against itself.
# ---------------------------------------------------------------------------

def _self_test() -> None:
    board = chess.Board()
    t0 = time.time()
    for _ in range(40):
        if board.is_game_over():
            break
        m = get_move(board.fen(), 120000)
        if m == "0000":
            break
        mv = chess.Move.from_uci(m)
        assert mv in board.legal_moves, m
        board.push(mv)
    print("self-test moves:", board.fullmove_number - 1,
          "result:", board.result() or "ongoing", f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    _self_test()