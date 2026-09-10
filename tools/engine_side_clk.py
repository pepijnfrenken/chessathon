"""engine_side with a PER-MOVE budget protocol (dev tool, NOT shipped).

Same as tools/engine_side_tree.py (fixed import root from argv[1], works
for old trees — stateless fallback included), except the search budget is
set per move over stdin, so a driver can emulate the real competition
clock (120 s + 0.5 s) instead of a fixed ms/move:

    budget <ms>\\n   -> set the budget for the NEXT fen line (no reply)
    <fen>\\n         -> <uci>\\n  (or 0000 / ERROR:<msg>)
    reset\\n         -> new game: clears game-history window + TT (no reply)
    quit\\n          -> exit

Warmup (from the q5-fix1 bout copy): covers the REAL move shape — deep
root iteration with non-empty game history — so the first clocked move
does not pay late-JIT compile cost (real-clock flagging found this; the
500 ms gates never did).

Used by tools/bout_ladder.py. Usage:
    python tools/engine_side_clk.py <engine-root>
"""

import os
import sys

_ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import chess  # noqa: E402

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402

# Import engine.eval to trigger config selection + compile of the eval.
import engine.eval  # noqa: E402,F401

_MOVE_BUDGET_MS = int(os.environ.get("CHESSATHON_MOVE_BUDGET_MS", "300"))

_MAX_DEPTH = 64

_TT_KEYS, _TT_VALS = TT.make()
_TT_MASK = np.uint64(len(_TT_KEYS) - 1)
_KILLERS = np.zeros((2, B.MAX_PLY), dtype=np.int32)
_HIST = np.zeros((2, 64, 64), dtype=np.int32)
_REP = np.zeros(B.MAX_PLY + 8, dtype=np.uint64)
_SCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_SSCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_NODES = np.zeros(1, dtype=np.int64)

# Old trees (pre Phase-4) have no game-history search: detect by feature
# and keep the legacy stateless call so the OLD side plays exactly as it
# shipped (same policy as tools/engine_side_tree.py).
_HAS_HIST = hasattr(S, "GAME_HIST")
if _HAS_HIST:
    _REP = np.zeros(S.REP_SIZE, dtype=np.uint64)
    _GAME_KEYS = []


def _ghist() -> tuple:
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


def _warmup() -> None:
    st = B.parse_fen(chess.STARTING_FEN)
    far = S._NOW() + 3_600_000_000_000
    S.search(st, 2, -S.INF, S.INF, 1, _NODES, far, _TT_KEYS, _TT_VALS,
             _TT_MASK, _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH)
    if _HAS_HIST:
        ghist = np.zeros(S.GAME_HIST, dtype=np.uint64)
        S.search_root(st, _NODES, far, _TT_KEYS, _TT_VALS, _TT_MASK,
                      _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 3,
                      ghist, 0)
        # q5-fix1: one DEEP root iteration with non-empty history — the
        # shape the first real-clock move actually has.
        st2 = B.parse_fen(
            "r3k2r/ppq1bppp/2p1p3/2P5/P2P4/2B1P3/4QPPP/R4RK1 b kq - 4 18")
        S.search_root(st2, _NODES, far, _TT_KEYS, _TT_VALS, _TT_MASK,
                      _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 6,
                      ghist, 1)
    else:
        S.search_root(st, _NODES, far, _TT_KEYS, _TT_VALS, _TT_MASK,
                      _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 3)


_PENDING_BUDGET_MS = None


def _move(fen: str) -> str:
    global _PENDING_BUDGET_MS
    pc_board = chess.Board(fen)
    if pc_board.is_game_over():
        return "0000"
    st = B.parse_fen(fen)
    if _HAS_HIST:
        if not _GAME_KEYS or _GAME_KEYS[-1] != st['key'][0]:
            _GAME_KEYS.append(st['key'][0])
        ghist, gcnt = _ghist()
    budget_ms = _PENDING_BUDGET_MS if _PENDING_BUDGET_MS else _MOVE_BUDGET_MS
    _PENDING_BUDGET_MS = None
    deadline = S._NOW() + int(budget_ms * 1_000_000)
    _NODES[0] = 0
    if _HAS_HIST:
        mv, score, depth = S.search_root(
            st, _NODES, deadline, _TT_KEYS, _TT_VALS, _TT_MASK,
            _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, _MAX_DEPTH,
            ghist, gcnt)
    else:
        mv, score, depth = S.search_root(
            st, _NODES, deadline, _TT_KEYS, _TT_VALS, _TT_MASK,
            _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, _MAX_DEPTH)
    if mv == 0:
        legal = list(pc_board.legal_moves)
        return "0000" if not legal else legal[0].uci()
    if _HAS_HIST:
        _GAME_KEYS.append(_state_key_after(st, mv))
    uci = B.move_to_uci(mv)
    m = chess.Move.from_uci(uci)
    if m not in pc_board.legal_moves:
        return f"ERROR:illegal {uci}"
    return uci


def main() -> int:
    global _PENDING_BUDGET_MS
    _warmup()
    print(f"[engine_side_clk] root={_ROOT} "
          f"config={os.environ.get('CHESSATHON_EVAL_CONFIG', '?')} "
          f"gate={os.environ.get('CHESSATHON_EVAL_GATE', '?')} "
          f"default-budget={_MOVE_BUDGET_MS}ms "
          f"stateful={'yes' if _HAS_HIST else 'no'}", file=sys.stderr)
    sys.stderr.flush()
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd or cmd == "quit":
            break
        if cmd.startswith("budget "):
            _PENDING_BUDGET_MS = int(cmd.split()[1])
            continue
        if cmd == "reset":
            if _HAS_HIST:
                _GAME_KEYS.clear()
                TT.tt_clear(_TT_KEYS)
                # C0 hygiene (audit-6 A12): clear stale repetition keys and
                # history heuristics between games.
                _REP.fill(0)
                _KILLERS.fill(0)
                _HIST.fill(0)
            continue
        try:
            resp = _move(cmd)
        except Exception as exc:  # never let the side die silently
            resp = f"ERROR:{exc!r}"
        sys.stdout.write(resp + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
