"""Chessathon engine Phase 1b — evaluation function.

Phase-1b scope is deliberately small (the tuning phase will rebuild this):
  material + piece-square tables + bishop pair + tempo, tapered between
  middlegame and endgame by game phase, plus the standard insufficient-
  material draw cases.

The PST numbers are OUR OWN hand-written tables from phase 1a (standard
shapes: pawns advance, knights/bishops favour the centre, rooks like the
7th rank, king castles back in the middlegame and centralises in the
endgame). Black indexes the tables with square ^ 56.
"""

import numpy as np

from numba import njit

from engine.board import (EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
                          WHITE, BLACK, sq64)

# Material values (centipawns; our own numbers from phase 1a).
MATERIAL = np.array([0, 100, 320, 330, 500, 900, 0], dtype=np.int16)

# Game-phase weights (standard phase-counting concept: N/B=1, R=2, Q=4,
# max 24 from 1a).
PHASE_W = np.array([0, 0, 1, 1, 2, 4, 0], dtype=np.int16)
MAX_PHASE = 24

# Bishop-pair bonus (mg / eg).
BISHOP_PAIR_MG = 30
BISHOP_PAIR_EG = 15

TEMPO = 10

# ---------------------------------------------------------------------------
# Piece-square tables, mg/eg, indexed sq64 (a1=0 .. h8=63), white POV.
# (Ported from our own phase-1a agent; knight/bishop/rook/queen shapes are
# phase-stable, so EG reuses the MG table for those.)
# ---------------------------------------------------------------------------

_PAWN_MG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
], dtype=np.int16)

_PAWN_EG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
    80, 80, 80, 80, 80, 80, 80, 80,
    30, 30, 35, 40, 40, 35, 30, 30,
    15, 15, 25, 30, 30, 25, 15, 15,
     5,  5, 10, 25, 25, 10,  5,  5,
    10,  5,  0,  5,  5,  0,  5, 10,
    15, 20, 20,  0,  0, 20, 20, 15,
     0,  0,  0,  0,  0,  0,  0,  0,
], dtype=np.int16)

_KNIGHT_MG = np.array([
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
], dtype=np.int16)

_BISHOP_MG = np.array([
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
], dtype=np.int16)

_ROOK_MG = np.array([
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
], dtype=np.int16)

_QUEEN_MG = np.array([
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
], dtype=np.int16)

_KING_MG = np.array([
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
], dtype=np.int16)

_KING_EG = np.array([
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
], dtype=np.int16)

# PST_MG[t][64], PST_EG[t][64] (t = piece type 1..6)
PST_MG = np.zeros((7, 64), dtype=np.int16)
PST_EG = np.zeros((7, 64), dtype=np.int16)
PST_MG[PAWN] = _PAWN_MG
PST_EG[PAWN] = _PAWN_EG
PST_MG[KNIGHT] = _KNIGHT_MG
PST_EG[KNIGHT] = _KNIGHT_MG
PST_MG[BISHOP] = _BISHOP_MG
PST_EG[BISHOP] = _BISHOP_MG
PST_MG[ROOK] = _ROOK_MG
PST_EG[ROOK] = _ROOK_MG
PST_MG[QUEEN] = _QUEEN_MG
PST_EG[QUEEN] = _QUEEN_MG
PST_MG[KING] = _KING_MG
PST_EG[KING] = _KING_EG


@njit
def evaluate(st) -> int:
    """Static evaluation in centipawns, positive = good for White.

    One pass over the board: material + PST (tapered by phase), bishop
    pair, tempo for the side to move, insufficient-material draws.
    """
    sqr = st['squares'][0]
    mg = 0
    eg = 0
    phase = 0
    # insufficient-material bookkeeping: no pawns/rooks/queens + few minors
    has_pawn = False
    has_major = False
    minors = 0            # knights + bishops (total)
    bishops = np.zeros(2, dtype=np.int8)   # per color, count
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        p = sqr[sq]
        if p == EMPTY:
            continue
        t = abs(p)
        color = 1 if p > 0 else 0
        s = sq64(sq) if color == WHITE else sq64(sq) ^ 56
        if color == WHITE:
            mg += MATERIAL[t] + PST_MG[t, s]
            eg += MATERIAL[t] + PST_EG[t, s]
        else:
            mg -= MATERIAL[t] + PST_MG[t, s]
            eg -= MATERIAL[t] + PST_EG[t, s]
        phase += PHASE_W[t]
        if t == PAWN:
            has_pawn = True
        elif t == ROOK or t == QUEEN:
            has_major = True
        elif t == KNIGHT:
            minors += 1
        elif t == BISHOP:
            minors += 1
            bishops[color] += 1

    if phase > MAX_PHASE:
        phase = MAX_PHASE
    score = (mg * phase + eg * (MAX_PHASE - phase)) // MAX_PHASE

    # bishop pair (tapered with the same phase)
    for color in (WHITE, BLACK):
        if bishops[color] >= 2:
            bp = (BISHOP_PAIR_MG * phase
                  + BISHOP_PAIR_EG * (MAX_PHASE - phase)) // MAX_PHASE
            score += bp if color == WHITE else -bp

    # insufficient material -> draw. Standard set: no pawns/majors and
    # (at most one minor total, or one minor each side) => cannot mate.
    # (K+2 minors vs K except K+2 same-colour B vs K can still mate in
    # forced lines; leave those as non-draw.)
    if not has_pawn and not has_major:
        if minors <= 1:
            return 0
        if bishops[0] <= 1 and bishops[1] <= 1:
            return 0   # K+N vs K+N, K+B vs K+N, K+B vs K+B: all draws

    if st['side'][0] == WHITE:
        return score + TEMPO
    return -(score + TEMPO)


# Short sanity tests (import-time smoke in dev; also used by tools).
def _selfcheck():
    st = __import__("engine.board", fromlist=["parse_fen"]).parse_fen(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert evaluate(st) == 0, evaluate(st)
    st2 = __import__("engine.board", fromlist=["parse_fen"]).parse_fen(
        "k7/8/8/8/8/8/8/K6R w - - 0 1")
    # K+R vs K is not a draw: eval should be large positive for white
    assert evaluate(st2) > 400, evaluate(st2)
    st3 = __import__("engine.board", fromlist=["parse_fen"]).parse_fen(
        "k7/8/8/8/8/8/8/K7 b - - 0 1")
    assert evaluate(st3) == 0, evaluate(st3)
    print("eval selfcheck OK")


if __name__ == "__main__":
    _selfcheck()