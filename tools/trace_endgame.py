"""Endgame move-by-move tracer (dev tool, NOT shipped).

Faithful to eg_check: each side runs as its OWN subprocess (numba bakes
the eval config/gate at import), speaking a one-move-per-line protocol
like engine_side.py but replying "uci <root_eval> <completed_depth>".
The parent logs, per move: search depth, side-to-move static eval, king
distance, material edge (mg), phase, halfmove clock, and king squares —
to see WHY the strong side converts or shuffles.

Usage:
    python tools/trace_endgame.py --fen "7k/8/8/8/8/8/8/KR6 w - - 0 1" \
        --strong hand:1111 --weak hand:0000 --move-ms 300 --max-plies 150
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

_SERVER = r"""
import os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from engine import board as B
from engine import search as S
from engine import tt as TT
import engine.eval
from engine.eval import evaluate

budget = int(os.environ["CHESSATHON_MOVE_BUDGET_MS"])
ttk, ttv = TT.make()
mask = np.uint64(len(ttk) - 1)
killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
hist = np.zeros((2, 64, 64), dtype=np.int32)
rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
nodes = np.zeros(1, dtype=np.int64)
# Phase 4: game-history window (one game per process: consecutive FEN
# lines are consecutive game positions; no reset needed).
_game_keys = []

def _ghist():
    arr = np.zeros(S.GAME_HIST, dtype=np.uint64)
    cnt = len(_game_keys) - 1
    if cnt <= 0:
        return arr, 0
    if cnt > S.GAME_HIST - 1:
        start = cnt - (S.GAME_HIST - 1)
        arr[:cnt - start] = np.fromiter(_game_keys[start:cnt], dtype=np.uint64)
        return arr, S.GAME_HIST - 1
    arr[:cnt] = np.fromiter(_game_keys[:cnt], dtype=np.uint64)
    return arr, cnt

def _key_after(st, mv):
    captured = st["squares"][0][B.m_to(mv)]
    fl = B.m_flags(mv)
    me = st["side"][0]
    if fl == B.F_EP:
        captured = st["squares"][0][B.m_to(mv) - 16 if me == B.WHITE else B.m_to(mv) + 16]
    pc_, pe_, ph_, pk_ = st["castle"][0], st["ep"][0], st["halfmove"][0], st["key"][0]
    B.make_move_apply(st, mv)
    key = st["key"][0]
    B.unmake_move(st, mv, captured, pc_, pe_, ph_, pk_)
    return key

# warmup
st = B.parse_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
far = S._NOW() + 3_600_000_000_000
S.search(st, 2, -S.INF, S.INF, 1, nodes, far, ttk, ttv, mask,
         killers, hist, rep, scratch, sscratch)
S.search_root(st, nodes, far, ttk, ttv, mask, killers, hist, rep,
              scratch, sscratch, 3, np.zeros(S.GAME_HIST, dtype=np.uint64), 0)

def root_top(st, deadline, topn):
    # replicate search_root's per-move score loop at the COMPLETED depth
    cnt = B.legal_moves(st, scratch[0], False)
    if cnt == 0:
        return []
    S._order_moves(st, scratch[0], sscratch[0], cnt, 0, killers, hist, 0)
    res = []
    alpha = -S.INF
    me = st["side"][0]
    for i in range(cnt):
        mv = scratch[0][i]
        captured = st["squares"][0][B.m_to(mv)]
        fl = B.m_flags(mv)
        if fl == B.F_EP:
            captured = st["squares"][0][B.m_to(mv) - 16 if me == B.WHITE else B.m_to(mv) + 16]
        pc_, pe_, ph_, pk_ = st["castle"][0], st["ep"][0], st["halfmove"][0], st["key"][0]
        B.make_move_apply(st, mv)
        child = S.search(st, 8, -S.INF, -alpha, 1, nodes, deadline, ttk, ttv,
                         mask, killers, hist, rep, scratch, sscratch)
        B.unmake_move(st, mv, captured, pc_, pe_, ph_, pk_)
        score = -child
        res.append((B.move_to_uci(mv), int(score), int(child)))
        if score > alpha:
            alpha = score
    res.sort(key=lambda x: -x[1])
    return res[:topn]

for line in sys.stdin:
    fen = line.strip()
    if not fen or fen == "quit":
        break
    st = B.parse_fen(fen)
    if not _game_keys or _game_keys[-1] != st["key"][0]:
        _game_keys.append(st["key"][0])
    ghist, gcnt = _ghist()
    ev = evaluate(st)
    deadline = S._NOW() + int(budget * 1_000_000)
    nodes[0] = 0
    mv, score, depth = S.search_root(st, nodes, deadline, ttk, ttv, mask,
                                     killers, hist, rep, scratch, sscratch,
                                     64, ghist, gcnt)
    uci = "0000" if mv == 0 else B.move_to_uci(mv)
    if mv != 0:
        _game_keys.append(_key_after(st, mv))
    top = root_top(st, S._NOW() + 40_000_000_000, 4)
    sys.stdout.write(f"{uci} {ev} {depth} " +
                     " ".join(f"{m}:{s}" for m, s, _ in top) + "\n")
    sys.stdout.flush()
"""

_MAT_MG = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
           chess.ROOK: 500, chess.QUEEN: 900}
_PHASE_W = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 1,
            chess.ROOK: 2, chess.QUEEN: 4, chess.KING: 0}


class Side:
    def __init__(self, spec: str, budget_ms: int):
        cfg, gate = spec.split(":")
        env = dict(os.environ)
        env["CHESSATHON_EVAL_CONFIG"] = cfg
        env["CHESSATHON_EVAL_GATE"] = gate
        env["CHESSATHON_MOVE_BUDGET_MS"] = str(budget_ms)
        env["NUMBA_CACHE_DIR"] = "/tmp/numba_cache_trace"
        env["NUMBA_NUM_THREADS"] = "1"
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env, cwd=os.getcwd())
        self.pending = False

    def ask(self, fen: str):
        self.proc.stdin.write(fen + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            self.last_top = []
            return None
        parts = line.split()
        self.last_top = []
        for tok in parts[3:]:
            m, _, s = tok.partition(":")
            try:
                self.last_top.append((m, int(s)))
            except ValueError:
                pass
        return parts[0], int(parts[1]) if len(parts) > 1 else None, \
            int(parts[2]) if len(parts) > 2 else None

    def quit(self):
        try:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def _metrics(board: chess.Board):
    mat = 0
    phase = 0
    for sq, pc in board.piece_map().items():
        if pc.piece_type == chess.KING:
            continue
        sign = 1 if pc.color == chess.WHITE else -1
        mat += sign * _MAT_MG[pc.piece_type]
        phase += _PHASE_W[pc.piece_type]
    wks = board.king(chess.WHITE)
    bks = board.king(chess.BLACK)
    kdist = max(abs((wks & 7) - (bks & 7)),
                abs((wks >> 3) - (bks >> 3)))
    return mat, phase, kdist


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fen", required=True)
    ap.add_argument("--strong", default="hand:1111")
    ap.add_argument("--weak", default="hand:0000")
    ap.add_argument("--move-ms", type=int, default=300)
    ap.add_argument("--max-plies", type=int, default=150)
    ap.add_argument("--strong-black", action="store_true",
                    help="strong side plays Black (fen must have black to move)")
    args = ap.parse_args()

    strong = Side(args.strong, args.move_ms)
    weak = Side(args.weak, args.move_ms)

    board = chess.Board(args.fen)
    print(f"# {args.strong} vs {args.weak}  {args.move_ms}ms  {args.fen}")
    print(f"# {'ply':>3} {'side':>4} {'move':>6} {'eval':>6} {'dep':>3} "
          f"{'kdist':>5} {'mat':>5} {'ph':>3} {'half':>4}  kings")

    t0 = time.monotonic()
    ply = 0
    result = None
    while ply < args.max_plies and not board.is_game_over():
        side = board.turn
        strong_is_white = not args.strong_black
        proc = strong if (side == chess.WHITE) == strong_is_white else weak
        fen = board.fen()
        mat, phase, kdist = _metrics(board)
        resp = proc.ask(fen)
        if resp is None:
            print(f"no response at ply {ply} (side died)")
            result = "??"
            break
        mv, ev, dep = resp
        top_str = " ".join(f"{m}:{s}" for m, s in
                           (proc.last_top or []))
        if mv == "0000":
            print(f"null move at ply {ply}")
            result = "draw"
            break
        m = chess.Move.from_uci(mv)
        if m not in board.legal_moves:
            print(f"ILLEGAL {mv} at ply {ply}")
            result = "illegal"
            break
        board.push(m)
        wq = chess.square_name(board.king(chess.WHITE))
        bq = chess.square_name(board.king(chess.BLACK))
        print(f"{ply:>3} {'W' if side == chess.WHITE else 'B':>4} {mv:>6} "
              f"{ev:>6} {dep:>3} {kdist:>5} {mat:>5} {phase:>3} "
              f"{board.halfmove_clock:>4}  K {wq}-{bq}  [{top_str}]")
        ply += 1
    if result is None:
        result = board.result(claim_draw=True)
        if board.is_game_over() and "\n" in result:
            result = "mate"
    dt = time.monotonic() - t0
    print(f"# end: ply={ply} result={result} ({dt:.1f}s)")
    strong.quit()
    weak.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())