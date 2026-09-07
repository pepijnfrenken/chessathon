"""Engine side for A/B testing (dev tool, NOT shipped).

Runs ONE engine configuration in a subprocess, warmed up at import
(~35 s JIT), then serves moves over stdin/stdout:

    <fen>\n  ->  <uci>\n

The configuration is fixed by environment variables read at import
(numba bakes global array values at compile time — see engine/eval.py):
    CHESSATHON_EVAL_CONFIG   hand|tuned   (param table)
    CHESSATHON_EVAL_GATE     4 chars 0/1  (which term groups are on)
    CHESSATHON_MOVE_BUDGET_MS  per-move search budget (default 300)

This is how tools/sprt.py (and any A/B harness) gets cleanly separated
engine sides: two subprocesses, no shared TT/history, no recompiles, and
the shipped agent.py is untouched.

Protocol responses:
    <uci>        a legal move
    0000         game over (no legal move)
    ERROR:<msg>  the side's engine crashed (caller logs and loses game)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Long-lived per-side search state (like agent.py).
_TT_KEYS, _TT_VALS = TT.make()
_TT_MASK = np.uint64(len(_TT_KEYS) - 1)
_KILLERS = np.zeros((2, B.MAX_PLY), dtype=np.int32)
_HIST = np.zeros((2, 64, 64), dtype=np.int32)
_REP = np.zeros(B.MAX_PLY + 8, dtype=np.uint64)
_SCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_SSCRATCH = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
_NODES = np.zeros(1, dtype=np.int64)


def _warmup() -> None:
    st = B.parse_fen(chess.STARTING_FEN)
    far = S._NOW() + 3_600_000_000_000
    S.search(st, 2, -S.INF, S.INF, 1, _NODES, far, _TT_KEYS, _TT_VALS,
             _TT_MASK, _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH)
    S.search_root(st, _NODES, far, _TT_KEYS, _TT_VALS, _TT_MASK,
                  _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, 3)


def _move(fen: str) -> str:
    pc_board = chess.Board(fen)
    if pc_board.is_game_over():
        return "0000"
    st = B.parse_fen(fen)
    deadline = S._NOW() + int(_MOVE_BUDGET_MS * 1_000_000)
    _NODES[0] = 0
    mv, score, depth = S.search_root(
        st, _NODES, deadline, _TT_KEYS, _TT_VALS, _TT_MASK,
        _KILLERS, _HIST, _REP, _SCRATCH, _SSCRATCH, _MAX_DEPTH)
    if mv == 0:
        legal = list(pc_board.legal_moves)
        return "0000" if not legal else legal[0].uci()
    uci = B.move_to_uci(mv)
    m = chess.Move.from_uci(uci)
    if m not in pc_board.legal_moves:
        return f"ERROR:illegal {uci}"
    return uci


def main() -> int:
    _warmup()
    print(f"[engine_side] config={os.environ.get('CHESSATHON_EVAL_CONFIG', '?')} "
          f"gate={os.environ.get('CHESSATHON_EVAL_GATE', '?')} "
          f"budget={_MOVE_BUDGET_MS}ms "
          f"lmr={os.environ.get('CHESSATHON_LMR', '1')}", file=sys.stderr)
    sys.stderr.flush()
    for line in sys.stdin:
        fen = line.strip()
        if not fen or fen == "quit":
            break
        try:
            resp = _move(fen)
        except Exception as exc:  # never let the side die silently
            resp = f"ERROR:{exc!r}"
        sys.stdout.write(resp + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())