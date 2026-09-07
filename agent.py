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
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402
from engine import time as TM  # noqa: E402

# Competition clock increment (120s + 0.5s). The harness advertises its own
# clock shape via CHESSATHON_INC_MS so the budget can be increment-aware.
def _inc_ms() -> int:
    """Increment the caller's clock adds per move (competition: 500 ms;
    harness advertises its own via CHESSATHON_INC_MS)."""
    return int(os.environ.get("CHESSATHON_INC_MS", "500"))
_MAX_DEPTH = 64               # ID hard cap (time-limited in practice)

# Shared, long-lived search state (persists across get_move calls: the TT
# and history heuristics carry real value between moves).
_TT_KEYS, _TT_VALS = TT.make()
_TT_MASK = np.uint64(len(_TT_KEYS) - 1)
_KILLERS = np.zeros((2, B.MAX_PLY), dtype=np.int32)
_HIST = np.zeros((2, 64, 64), dtype=np.int32)
_REP = np.zeros(S.REP_SIZE, dtype=np.uint64)
_SCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_SSCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_NODES = np.zeros(1, dtype=np.int64)

# Phase 4 — GAME HISTORY (the stateless-agent fix). The competition
# harness calls get_move(fen, t) once per OWN move, so the engine only
# saw one position at a time and could never notice that a move would
# repeat a position from earlier in the game — it shuffled won endgames
# into threefold draws (ladder r54/r55). _GAME_KEYS keeps the rolling
# zobrist-key history of the REAL game (BOTH parities: the incoming
# position and the position after our own move, appended at the end of
# get_move), oldest first, capped at S.GAME_HIST entries. The current
# root position is appended at the START of each get_move and excluded
# from the window passed to the search (it is the search's own root).
_GAME_KEYS = []


def _ghist() -> tuple:
    """np.int64 window of game keys strictly before the root + count.
    get_move appends the current root position first, so the search
    window is everything except the last entry; the cap keeps the
    newest GAME_HIST positions (the root included)."""
    arr = np.zeros(S.GAME_HIST, dtype=np.uint64)
    cnt = len(_GAME_KEYS) - 1
    if cnt <= 0:
        return arr, 0
    if cnt > S.GAME_HIST - 1:
        start = cnt - (S.GAME_HIST - 1)
        arr[:cnt - start] = np.fromiter(_GAME_KEYS[start:cnt],
                                        dtype=np.uint64)
        return arr, S.GAME_HIST - 1
    arr[:cnt] = np.fromiter(_GAME_KEYS[:cnt], dtype=np.uint64)
    return arr, cnt


def _state_key_after(st, mv) -> int:
    """Zobrist key of the position after applying mv (state restored)."""
    captured = st['squares'][0][B.m_to(mv)]
    fl = B.m_flags(mv)
    me = st['side'][0]
    if fl == B.F_EP:
        captured = st['squares'][0][B.m_to(mv) - 16 if me == B.WHITE
                                    else B.m_to(mv) + 16]
    prev_castle = st['castle'][0]
    prev_ep = st['ep'][0]
    prev_half = st['halfmove'][0]
    prev_key = st['key'][0]
    B.make_move_apply(st, mv)
    key = st['key'][0]
    B.unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                  prev_key)
    return key


def reset_game() -> None:
    """Clear the game-history window (dev harness: one engine_side
    process serves many games; the harness sends `reset` between
    games). Also called at import for cleanliness."""
    _GAME_KEYS.clear()

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
                  _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 3,
                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return time.perf_counter() - t0


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal UCI move for the given FEN."""
    t0 = time.perf_counter()
    try:
        pc_board = chess.Board(fen)
        if pc_board.is_game_over():
            return "0000"

        st = B.parse_fen(fen)
        # Phase 4 game history: append the current position (unless it
        # is exactly the previous one — guards harness retries), search
        # with everything before it as repetition context, then record
        # the position after our move so the NEXT call sees it.
        if not _GAME_KEYS or _GAME_KEYS[-1] != st['key'][0]:
            _GAME_KEYS.append(st['key'][0])
        ghist, gcnt = _ghist()
        budget_ms = TM.budget_ms(int(time_left_ms), _inc_ms())
        deadline = S._NOW() + int(budget_ms * 1_000_000)
        _NODES[0] = 0
        mv, score, depth = S.search_root(
            st, _NODES, deadline, _TT_KEYS, _TT_VALS, _TT_MASK,
            _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, _MAX_DEPTH,
            ghist, gcnt)

        if mv == 0:
            # no legal move from our side: game-over position
            legal = list(pc_board.legal_moves)
            return "0000" if not legal else legal[0].uci()

        _GAME_KEYS.append(_state_key_after(st, mv))
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
# Import-time JIT warmup: the competition gives 60 s init BEFORE any clock
# runs, so compilation belongs here, never inside a timed get_move (the
# harness proved a first-move compile flags the clock instantly).
# ---------------------------------------------------------------------------

try:
    _WARMUP_S = _warmup()
    print(f"[chessathon] numba warmup {_WARMUP_S:.1f}s (init budget ok)",
          file=sys.stderr)
except Exception as exc:  # pragma: no cover - degraded but functional
    print(f"[chessathon] warmup failed ({exc!r}); first move will JIT",
          file=sys.stderr)

reset_game()   # Phase 4: start with an empty game-history window


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