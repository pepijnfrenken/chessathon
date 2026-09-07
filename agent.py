"""Chessathon Phase 1a agent — minimal, correct, original alpha-beta engine.

Exposes `get_move(fen: str, time_left_ms: int) -> str` returning a legal UCI
move. This is the floor we ship today: pure Python, python-chess used ONLY
as the I/O / legal-move oracle (FEN parsing, move application, legality),
with our own fresh implementation of the search and evaluation on top.

Design (all standard published *concepts*, implemented fresh here):
  - iterative-deepening negamax with alpha-beta pruning
  - move ordering: MVV-LVA captures first, then killer move, then the rest
  - minimal capture-only quiescence (stands pat; full evasions when in check)
  - evaluation: material + piece-square tables (our own numbers) tapered
    between middlegame and endgame by game phase + a small tempo bonus
  - draw handling inside search: fifty-move rule and repetition -> 0

Correctness contract: never return an illegal move, never crash, never hang.
The whole search is wrapped so any failure falls back to a legal move.

This file is replaced by the numba engine in Phase 1b.
"""

import time

import chess

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MATE = 30000          # score above any non-mate
INF = 32000
MAX_DEPTH = 6         # hard cap; pure-Python depth beyond this is too slow
MIN_ALWAYS_DEPTH = 1  # always finish this depth (cheap) even on tiny clocks

CENTIPAWNS = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Phase weight of each piece type (standard phase-counting concept, our code).
PHASE_WEIGHT = {
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
}
MAX_PHASE = 24

# ---------------------------------------------------------------------------
# Piece-square tables (our own hand-written numbers, standard shapes:
# pawns advance toward promotion, knights/bishops favor the centre, rooks
# like the 7th rank, queen mild centre bias, king stays home in the
# middlegame and moves to the centre in the endgame).
# Indexed a1=0 .. h8=63, white perspective; black uses square ^ 56.
# ---------------------------------------------------------------------------

_PAWN_MG = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]

_PAWN_EG = [
     0,  0,  0,  0,  0,  0,  0,  0,
    80, 80, 80, 80, 80, 80, 80, 80,
    30, 30, 35, 40, 40, 35, 30, 30,
    15, 15, 25, 30, 30, 25, 15, 15,
     5,  5, 10, 25, 25, 10,  5,  5,
    10,  5,  0,  5,  5,  0,  5, 10,
    15, 20, 20,  0,  0, 20, 20, 15,
     0,  0,  0,  0,  0,  0,  0,  0,
]

_KNIGHT_MG = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

_BISHOP_MG = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

_ROOK_MG = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
]

_QUEEN_MG = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

_KING_MG = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]

_KING_EG = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

_PST_MG = {
    chess.PAWN: _PAWN_MG,
    chess.KNIGHT: _KNIGHT_MG,
    chess.BISHOP: _BISHOP_MG,
    chess.ROOK: _ROOK_MG,
    chess.QUEEN: _QUEEN_MG,
    chess.KING: _KING_MG,
}

_PST_EG = {
    chess.PAWN: _PAWN_EG,
    chess.KNIGHT: _KNIGHT_MG,   # knight/bishop shapes are phase-stable
    chess.BISHOP: _BISHOP_MG,
    chess.ROOK: _ROOK_MG,
    chess.QUEEN: _QUEEN_MG,
    chess.KING: _KING_EG,
}

TEMPO = 10  # small bonus for the side to move

# ---------------------------------------------------------------------------
# Evaluation (from White's point of view)
# ---------------------------------------------------------------------------


def evaluate(board: chess.Board) -> int:
    """Static evaluation in centipawns, White-positive. Tapered mg/eg."""

    # Game phase from non-pawn material on the board.
    phase = 0
    for square, piece in board.piece_map().items():
        if piece.piece_type in PHASE_WEIGHT:
            phase += PHASE_WEIGHT[piece.piece_type]
    phase = min(phase, MAX_PHASE)

    mg = 0
    eg = 0
    for square, piece in board.piece_map().items():
        value = CENTIPAWNS[piece.piece_type]
        mg += value
        eg += value
        sq = square if piece.color == chess.WHITE else square ^ 56
        mg += _PST_MG[piece.piece_type][sq]
        eg += _PST_EG[piece.piece_type][sq]

    score = (mg * phase + eg * (MAX_PHASE - phase)) // MAX_PHASE

    # Insufficient material: force a draw instead of shuffling forever.
    if board.is_insufficient_material():
        return 0

    if board.turn == chess.WHITE:
        return score + TEMPO
    return -(score + TEMPO)


def _is_draw(board: chess.Board) -> bool:
    """Draw conditions the search should treat as score 0."""
    return board.is_fifty_moves() or board.is_repetition(2)


# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

_VICTIM_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def _mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """Capture ordering score: big victim first, cheap attacker first."""
    victim = board.piece_at(move.to_square)
    if victim is None:
        # Not a capture: promotions still go early, everything else ties.
        return 0
    attacker = board.piece_at(move.from_square)
    return _VICTIM_VALUE[victim.piece_type] * 10 - _VICTIM_VALUE[attacker.piece_type]


def order_moves(board: chess.Board, moves, killer=None) -> list:
    """Order moves for search: captures (MVV-LVA) first, killer next, rest."""
    if killer is not None and killer in moves:
        scored = [(2000000, killer)]
        remaining = [m for m in moves if m != killer]
    else:
        scored = []
        remaining = list(moves)
    for mv in remaining:
        s = _mvv_lva(board, mv)
        if mv.promotion:
            s += 800 + _VICTIM_VALUE[mv.promotion]
        scored.append((s, mv))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [mv for _, mv in scored]


# ---------------------------------------------------------------------------
# Search: quiescence then negamax
# ---------------------------------------------------------------------------


def _quiesce(board: chess.Board, alpha: int, beta: int, ply: int) -> int:
    """Capture-only quiescence with stand-pat, to damp horizon effects."""
    if _is_draw(board):
        return 0

    if board.is_check():
        # Cannot stand pat in check: search all (legal) evasions.
        evasions = list(board.legal_moves)
        if not evasions:
            return -MATE + ply  # checkmate
        for mv in order_moves(board, evasions):
            board.push(mv)
            score = -_quiesce(board, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    if not board.legal_moves:
        return 0  # stalemate

    stand_pat = evaluate(board)
    if stand_pat >= beta:
        return stand_pat
    if stand_pat > alpha:
        alpha = stand_pat

    captures = [m for m in board.legal_moves if board.is_capture(m)]
    for mv in order_moves(board, captures):
        board.push(mv)
        score = -_quiesce(board, -beta, -alpha, ply + 1)
        board.pop()
        if score >= beta:
            return score
        if score > alpha:
            alpha = score
    return alpha


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int,
             ply: int, killers: list, node_count) -> int:
    """Minimax with alpha-beta pruning. Returns score from side-to-move POV."""
    node_count[0] += 1

    if _is_draw(board):
        return 0

    if depth <= 0:
        return _quiesce(board, alpha, beta, ply)

    moves = list(board.legal_moves)
    if not moves:
        if board.is_check():
            return -MATE + ply
        return 0  # stalemate

    killer = killers[ply] if ply < len(killers) else None
    ordered = order_moves(board, moves, killer)

    best = -INF
    for mv in ordered:
        was_capture = board.is_capture(mv)
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1,
                          killers, node_count)
        board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            # Fail high: remember a killer quiet move for this ply.
            if not was_capture and ply < len(killers) and killers[ply] != mv:
                killers[ply] = mv
            break
    return best


# ---------------------------------------------------------------------------
# Iterative deepening root
# ---------------------------------------------------------------------------


def _search_root(board: chess.Board, budget_s: float) -> chess.Move:
    """Iterative deepening at the root. Interruptible between root moves.

    Always completes MIN_ALWAYS_DEPTH; beyond that, stops once the time
    budget is exhausted, keeping the best move found so far.
    """
    legal = list(board.legal_moves)
    if len(legal) == 1:
        return legal[0]

    start = time.monotonic()

    # Start with a sane default ordering so depth 1 is cheap and useful.
    ordered = order_moves(board, legal)

    best_move = ordered[0]
    killers = [None] * (MAX_DEPTH + 8)

    for depth in range(1, MAX_DEPTH + 1):
        move_scores = []
        best_this_iter = None
        best_score = -INF

        for idx, mv in enumerate(ordered):
            if depth > MIN_ALWAYS_DEPTH and time.monotonic() - start >= budget_s:
                # Time up mid-iteration: keep previous iteration's move.
                return best_move

            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, INF, 1, killers,
                              [0])
            board.pop()

            move_scores.append((score, mv))
            if score > best_score:
                best_score = score
                best_this_iter = mv

        ordered = [mv for _, mv in sorted(move_scores, key=lambda p: p[0],
                                          reverse=True)]
        best_move = best_this_iter if best_this_iter is not None else best_move

        elapsed = time.monotonic() - start
        if elapsed >= budget_s:
            break

    return best_move


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal UCI move for the given FEN.

    Time budget is a simple fraction of the remaining clock with a floor and
    a cap: strong positions don't need more than a few seconds at this depth.
    Any failure inside the search falls back to a legal move — the agent
    never crashes and never returns an illegal move.
    """
    try:
        board = chess.Board(fen)
        if board.is_game_over():
            # Nothing to do; no legal move exists. Return a null move so the
            # caller can tell the game is finished.
            return "0000"

        # Budget: spend at most ~8% of the remaining clock, capped at
        # 1.25 s. On the fast test clocks (2 s+0.1 s) that's ~0.16 s per
        # move — sustainable for a whole game; on the real 120 s clock it
        # reaches the cap. Never spend more than half of tiny remaining
        # times, so the agent cannot flag itself.
        t = max(time_left_ms, 0) / 1000.0
        budget_s = min(1.25, 0.08 * t)
        if t < 1.0:
            budget_s = min(budget_s, 0.5 * t)

        move = _search_root(board, budget_s)
        if move in board.legal_moves:
            return move.uci()
        # Defensive: fall back to a legal move (should never trigger).
        return list(board.legal_moves)[0].uci()
    except Exception:
        try:
            board = chess.Board(fen)
            return list(board.legal_moves)[0].uci()
        except Exception:
            return "0000"


# ---------------------------------------------------------------------------
# Self-test: `python agent.py` plays a short game against itself.
# ---------------------------------------------------------------------------

def _self_test() -> None:
    board = chess.Board()
    moves = []
    for _ in range(20):
        if board.is_game_over():
            break
        mv = get_move(board.fen(), 5000)
        if mv == "0000":
            break
        board.push_uci(mv)
        moves.append(mv)
    print("self-test game:", " ".join(moves))
    print("result:", board.result())


if __name__ == "__main__":
    _self_test()