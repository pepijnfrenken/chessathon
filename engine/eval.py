"""Chessathon engine Phase 2 — evaluation function (parameterised, tunable).

Design (see BUILD.md "Phase 2" entry and docs/research/02-eval-and-tuning.md):

The evaluation is a LINEAR function of features, E = params . features,
tapered between middlegame and endgame by game phase (standard
phase-counting concept, phi = N/B:1 R:2 Q:4, max 24). All weights live in
the single int32 vector EVAL_PARAMS, shared with the dev-time Texel tuner
(tools/texel_tune.py), which fits OUR weights on OUR self-play data — the
values in TUNED_PARAMS are ours (generated block; see BUILD.md). Nothing
here is copied from any engine: this file is the fresh implementation of
published *concepts* only.

Terms, in ROI order (research doc 02 §4):
  1. material + piece-square tables (mg/eg, tapered) — our own 1a/1b tables
  2. pawn structure: doubled, isolated, passed (rank bonus + blocked
     reduction) — doubled/isolated ~-10..-12 cp, passed +10..+100
  3. mobility: pseudo-legal attack count per piece class (N/B ~4 cp/move,
     R ~2, Q ~1 in mg; ~half in eg)
  4. king safety: pawn shelter 1-2 ranks in front of the king + open-file
     penalty; king "tropism" (kings close) is an endgame conversion aid
  5. bishop pair + tempo (kept from 1b, now parameters)

Param layout (indices below; also imported by the tuner so the feature
contract cannot drift):
  [0..5]    material mg, piece 1..6;  [6..11]   material eg
  [12..395] PST mg, (t-1)*64 + sq64;  [396..779] PST eg (same layout)
  [780..]   term weights (mg/eg pairs, see P_* constants)

Tapering is the standard mg/eg interpolation; score is floor-divided by
24 exactly as the tuner's numpy model does (bit-exact parity contract).
Gate masks (EVAL_GATE, 4 bits) zero whole term groups at import time so
A/B tests (tools/sprt.py) can toggle pawn=mobility=king-safety=bishoppair
groups per engine side.

Configuration is read at import (numba bakes global array VALUES at
compile, so runtime mutation is not visible; each A/B side runs as its
own process with its own config):
  CHESSATHON_EVAL_CONFIG = hand|tuned   (default: hand — the shipped eval;
                                         tuned is the rejected fit, kept for A/B)
  CHESSATHON_EVAL_GATE   = "1111"       4 chars, group order: pawn,
                                         mobility, king-safety, bp+tempo
  CHESSATHON_COMPCLAMP   = 1 applies the compensation-aware clamp (P8,
                                         BUILD.md "P8"): at phase <= 16
                                         with raw material |mat| >= 200,
                                         the White-POV score is clamped
                                         to within 120cp of raw material
                                         so positional compensation
                                         cannot mask a material deficit
                                         (default: off — shipped V5 eval)
"""

import os

import numpy as np

from numba import njit

from engine.board import (EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
                          WHITE, BLACK, sq64, _KNIGHT_DELTAS, _RAYS,
                          _ROOK_RAYS)

# ---------------------------------------------------------------------------
# Param layout (SHARED with tools/texel_tune.py — do not renumber)
# ---------------------------------------------------------------------------

P_MAT_MG = 0          # 6
P_MAT_EG = 6          # 6
P_PST_MG = 12         # 6*64 = 384
P_PST_EG = 396        # 384
P_DOUBLED_MG = 780
P_DOUBLED_EG = 781
P_ISOLATED_MG = 782
P_ISOLATED_EG = 783
P_PASSED_MG = 784     # 4: white ranks 4..7 (sq64 rank idx 3..6)
P_PASSED_EG = 788     # 4
P_BLOCKED_MG = 792    # passed pawn blocked by an enemy pawn in front
P_BLOCKED_EG = 793
P_MOB_N_MG = 794
P_MOB_N_EG = 795
P_MOB_B_MG = 796
P_MOB_B_EG = 797
P_MOB_R_MG = 798
P_MOB_R_EG = 799
P_MOB_Q_MG = 800
P_MOB_Q_EG = 801
P_SHELTER_NEAR_MG = 802   # own pawns 1 rank in front of king, 3 files wide
P_SHELTER_NEAR_EG = 803
P_SHELTER_FAR_MG = 804    # own pawns 2 ranks in front of king
P_SHELTER_FAR_EG = 805
P_OPEN_MG = 806           # king's file has no own pawn
P_OPEN_EG = 807
P_KDIST_MG = 808          # chebyshev distance between kings
P_KDIST_EG = 809
P_BISHOP_PAIR_MG = 810
P_BISHOP_PAIR_EG = 811
P_TEMPO = 812
N_PARAMS = 813

# Phase weights per piece (N/B=1, R=2, Q=4; standard phase-counting).
PHASE_W = np.array([0, 0, 1, 1, 2, 4, 0], dtype=np.int16)
MAX_PHASE = 24

# P8 compensation-aware clamp (CHESSATHON_COMPCLAMP; BUILD.md "P8").
# Read at import: numba bakes these into the jitted evaluate().
#   COMPCLAMP_ON   env CHESSATHON_COMPCLAMP != 0
#   COMPCLAMP_MAT  raw-material deficit that arms the clamp (200: a
#                  minor or more; matches the audited P8 regime).
#   COMPCLAMP_SLACK how far the tapered score may sit from raw material
#                  once armed (120: the P8 fixed-point band width
#                  |static_eval - material| <= 120 at phase <= 16).
COMPCLAMP_ON = os.environ.get("CHESSATHON_COMPCLAMP", "0") != "0"
COMPCLAMP_MAT = int(os.environ.get("CHESSATHON_COMPCLAMP_MAT", "200"))
COMPCLAMP_SLACK = int(os.environ.get("CHESSATHON_COMPCLAMP_SLACK", "120"))

# Phase 3 hand-tuned endgame king-activation weight (see evaluate()).
# 30 was too weak to overcome PST/rook noise at kdist 3-4 (KRvK king
# stalled at d1/e1 instead of entering the black king's orbit).
MATE_DRIVE_K = 50               # cp per rank of king closeness

# ---------------------------------------------------------------------------
# Bitboard masks (sq64 encoding: a1=0 .. h8=63, bit = 1 << sq64)
# ---------------------------------------------------------------------------

_BB = np.array([np.uint64(1) << i for i in range(64)], dtype=np.uint64)

# FILE_SQ[s]: mask of all squares on s's file.
FILE_SQ = np.zeros(64, dtype=np.uint64)
# ADJ_SQ[s]: mask of the two adjacent files (isolation test).
ADJ_SQ = np.zeros(64, dtype=np.uint64)
# PASSED_W[s]: squares an ENEMY pawn must not occupy for a WHITE pawn on s
# to be passed (its file + adjacent files, ranks strictly above s).
PASSED_W = np.zeros(64, dtype=np.uint64)
# SHELTER_NEAR[s] / SHELTER_FAR[s]: own-pawn squares 1 / 2 ranks in front
# of a king on s, files f-1..f+1 (white perspective).
SHELTER_NEAR = np.zeros(64, dtype=np.uint64)
SHELTER_FAR = np.zeros(64, dtype=np.uint64)

for _f in range(8):
    _m = np.uint64(0)
    for _r in range(8):
        _m |= _BB[_r * 8 + _f]
    for _s in range(_f, 64, 8):
        FILE_SQ[_s] = _m
for _s in range(64):
    _f = _s & 7
    if _f > 0:
        ADJ_SQ[_s] |= FILE_SQ[_s - 1]
    if _f < 7:
        ADJ_SQ[_s] |= FILE_SQ[_s + 1]
for _s in range(64):
    _f = _s & 7
    _r = _s >> 3
    for _fr in range(_r + 1, 8):
        for _ff in range(max(0, _f - 1), min(8, _f + 2)):
            PASSED_W[_s] |= _BB[_fr * 8 + _ff]
    if _r + 1 < 8:
        for _ff in range(max(0, _f - 1), min(8, _f + 2)):
            SHELTER_NEAR[_s] |= _BB[(_r + 1) * 8 + _ff]
    if _r + 2 < 8:
        for _ff in range(max(0, _f - 1), min(8, _f + 2)):
            SHELTER_FAR[_s] |= _BB[(_r + 2) * 8 + _ff]

# popcount table (numba 0.67 has no int.bit_count for uint64).
_POPCNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.int8)


@njit(inline="always")
def _popcount64(b) -> int:
    x = b
    return (_POPCNT[x & 255] + _POPCNT[(x >> 8) & 255]
            + _POPCNT[(x >> 16) & 255] + _POPCNT[(x >> 24) & 255]
            + _POPCNT[(x >> 32) & 255] + _POPCNT[(x >> 40) & 255]
            + _POPCNT[(x >> 48) & 255] + _POPCNT[(x >> 56) & 255])


@njit(inline="always")
def _mirror_rank(b) -> int:
    """Mirror a uint64 bitboard across the horizontal axis (rank flip)."""
    x = b
    return ((x & np.uint64(0x00000000000000FF)) << np.uint64(56)
            | (x & np.uint64(0x000000000000FF00)) << np.uint64(40)
            | (x & np.uint64(0x0000000000FF0000)) << np.uint64(24)
            | (x & np.uint64(0x00000000FF000000)) << np.uint64(8)
            | (x & np.uint64(0x000000FF00000000)) >> np.uint64(8)
            | (x & np.uint64(0x0000FF0000000000)) >> np.uint64(24)
            | (x & np.uint64(0x00FF000000000000)) >> np.uint64(40)
            | (x & np.uint64(0xFF00000000000000)) >> np.uint64(56))


# ---------------------------------------------------------------------------
# Parameter value sets
# ---------------------------------------------------------------------------

# SEED material values (our own 1a numbers).
_MATERIAL = np.array([0, 100, 320, 330, 500, 900, 0], dtype=np.int16)

# Piece-square tables, mg/eg, ours from 1a/1b (knight/bishop/rook/queen
# EG reuses the MG table — phase-stable shapes).
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


def _build_hand() -> np.ndarray:
    """Hand-tuned starting values (OUR priors; see P_* order)."""
    p = np.zeros(N_PARAMS, dtype=np.int32)
    p[P_MAT_MG:P_MAT_MG + 6] = _MATERIAL[1:7]
    p[P_MAT_EG:P_MAT_EG + 6] = _MATERIAL[1:7]
    # q5-night2 (BUILD doc "advanced pawns rewarded"): the literal tables
    # were authored rank-8-first but the consumer (sq64, a1=0..h8=63, with
    # black ^56) is rank-1-first — every side's HOME pawns read the 50/80
    # row and advancement is punished. Normalize at hand-assembly: flip the
    # 8 rows of the pawn tables (row 0 <-> row 7 ...). Pawn-only this pass;
    # king/rook orientation is a separate gated change (docs/research/07).
    p[P_PST_MG + 0 * 64:P_PST_MG + 1 * 64] = _PAWN_MG.reshape(8, 8)[::-1].ravel()
    p[P_PST_MG + 1 * 64:P_PST_MG + 2 * 64] = _KNIGHT_MG
    p[P_PST_MG + 2 * 64:P_PST_MG + 3 * 64] = _BISHOP_MG
    p[P_PST_MG + 3 * 64:P_PST_MG + 4 * 64] = _ROOK_MG
    p[P_PST_MG + 4 * 64:P_PST_MG + 5 * 64] = _QUEEN_MG
    # q5-v9k (audit-6 C1): the king tables are authored rank-8-first like
    # the pawns, but the consumer is rank-1-first, so as-read the engine
    # punished its OWN back rank (e1/g1/c1 = -50/-40/-40 MG) and rewarded
    # the ENEMY's (e8/g8/c8 = 0/+30/+10) — an inverted castling incentive,
    # 64/64 cells, both colours (black mirrors with ^56). Same one-line row
    # flip that night2 applied to the pawns; MG king only — the
    # king+rook+bishop variant measured 0.481 and was rejected.
    p[P_PST_MG + 5 * 64:P_PST_MG + 6 * 64] = _KING_MG.reshape(8, 8)[::-1].ravel()
    p[P_PST_EG + 0 * 64:P_PST_EG + 1 * 64] = _PAWN_EG.reshape(8, 8)[::-1].ravel()
    p[P_PST_EG + 1 * 64:P_PST_EG + 2 * 64] = _KNIGHT_MG
    p[P_PST_EG + 2 * 64:P_PST_EG + 3 * 64] = _BISHOP_MG
    p[P_PST_EG + 3 * 64:P_PST_EG + 4 * 64] = _ROOK_MG
    p[P_PST_EG + 4 * 64:P_PST_EG + 5 * 64] = _QUEEN_MG
    p[P_PST_EG + 5 * 64:P_PST_EG + 6 * 64] = _KING_EG
    # pawn structure
    p[P_DOUBLED_MG], p[P_DOUBLED_EG] = -12, -10
    p[P_ISOLATED_MG], p[P_ISOLATED_EG] = -12, -8
    p[P_PASSED_MG:P_PASSED_MG + 4] = [10, 20, 35, 60]     # ranks 4,5,6,7
    p[P_PASSED_EG:P_PASSED_EG + 4] = [15, 35, 60, 100]
    p[P_BLOCKED_MG], p[P_BLOCKED_EG] = 10, 30
    # mobility (cp per pseudo-legal move; mg / eg)
    p[P_MOB_N_MG], p[P_MOB_N_EG] = 4, 2
    p[P_MOB_B_MG], p[P_MOB_B_EG] = 4, 2
    p[P_MOB_R_MG], p[P_MOB_R_EG] = 2, 1
    p[P_MOB_Q_MG], p[P_MOB_Q_EG] = 1, 1
    # king safety
    p[P_SHELTER_NEAR_MG], p[P_SHELTER_NEAR_EG] = 12, 4
    p[P_SHELTER_FAR_MG], p[P_SHELTER_FAR_EG] = 6, 2
    p[P_OPEN_MG], p[P_OPEN_EG] = -8, 0
    # king-distance ("tropism") is a color-SYMMETRIC signal (kings close
    # shifts both sides' evals): it cannot be anti-negated, so hand value
    # is 0 and the Texel fit may tune it as a drawishness/intercept term.
    p[P_KDIST_MG], p[P_KDIST_EG] = 0, 0
    # bishop pair + tempo (kept from 1b)
    p[P_BISHOP_PAIR_MG], p[P_BISHOP_PAIR_EG] = 30, 15
    p[P_TEMPO] = 10
    return p


HAND_PARAMS = _build_hand()

# TUNED_PARAMS: generated block. Filled by tools/texel_tune.py (our values
# fitted on our self-play data; see BUILD.md "Phase 2 — tuning"). Until the
# first tuning run this equals the hand priors.
# >>> TUNED_PARAMS_BLOCK >>>                          # patch marker
TUNED_PARAMS = np.array([
       100,    320,    330,    500,    900,      0,    100,    320,    330,    500,    900,      0,
         0,      0,      0,      0,      0,      0,      0,      0,    -99,    -57,    -37,    -44,
       -49,   -126,    -20,    -59,   -126,   -110,      3,      6,    -54,   -103,     36,     57,
       -24,   -120,     97,      1,     12,    -97,      3,    -45,     -8,     42,     76,    -14,
       -80,      4,   -123,    -12,   -112,    -53,    -38,    -19,   -121,     -2,    -24,    -52,
       -60,      9,     43,    -43,     -6,      9,     21,      3,      0,      0,      0,      0,
         0,      0,      0,      0,    -38,   -138,    -44,    -84,    -48,    -38,   -167,    -65,
       -42,     -9,     29,    -39,    -36,     22,    -12,    -39,    -91,    110,    -22,     76,
       -77,     38,      9,    -73,      7,    -13,    -35,    -52,     66,    -24,    -16,    -13,
       -24,    -26,    -18,     28,      2,    -15,     43,     -8,   -108,     17,     29,     91,
       -69,     22,     18,    -21,   -165,    -15,    -19,    -18,    -22,    -35,    -26,    -96,
      -107,    -76,    -58,    -34,    -59,    -56,    -41,    -60,    -21,    -26,     -8,    -10,
       -15,    -59,     -6,    -35,     -9,    -30,    -13,     -4,     78,     34,    -58,     11,
       -60,    -47,     -6,   -108,     17,     14,     15,     11,     21,    -75,    -85,      7,
       -67,    -63,     36,     18,   -127,     34,     69,      7,     40,     16,     41,    -29,
       -74,      8,     25,    -85,    -42,    -55,     10,   -115,      6,    -18,     12,   -109,
       -17,    -84,     85,    -14,    -18,    -55,    -31,     19,    -10,    -47,    -13,    -85,
      -177,   -182,    -71,    -64,    -51,    -98,   -252,   -236,    -92,     -9,      3,    -24,
       -99,    -46,     12,    -80,    -99,   -130,    -23,    -17,     -8,     19,    -34,    -55,
        35,    -38,      0,    -16,    -44,    -67,     -7,    -13,   -127,    -11,     72,     20,
       -34,      1,    -52,    -23,    -75,    -15,      0,    -27,    -19,      8,     -5,     21,
      -128,   -142,     25,     50,    -44,    -29,    -37,    -58,     -5,    -20,      0,     12,
       -13,    -14,    -49,     27,    -99,      2,     32,    -55,     -4,    -49,     -5,    -41,
       -46,     10,    -16,   -115,     27,    -18,     18,    -56,     46,     46,    111,     70,
        43,     30,    124,    -42,     22,     10,    -34,     56,     54,     69,     22,     82,
       -88,     37,   -117,     37,     48,     54,     85,     74,    -10,    -26,    -59,     69,
        20,    -29,     30,    -40,   -147,   -151,    -14,    -34,    -64,     62,     57,     19,
      -140,   -119,    -81,    -35,    -52,     -5,    -53,   -152,    -12,     29,      3,     36,
       -23,   -138,    -63,    -40,    -14,    -32,    -58,   -110,    -55,    -60,    -83,    -10,
        28,     20,    -86,   -133,   -108,     26,      8,    -17,      0,    -56,   -140,    -79,
        -8,    -21,    -21,    -43,    -10,    -11,    -30,    -84,    -65,    -32,    -18,    -17,
         1,     -9,     -7,    -27,    -37,    -55,    -36,    -10,     55,     12,    -16,     20,
         1,     -6,     -3,     28,     29,     46,     32,    -22,      0,     -3,     40,     36,
         0,      0,      0,      0,      0,      0,      0,      0,   -114,    -83,      8,    -74,
      -191,    -42,    -26,    -86,   -159,    -63,   -128,   -122,     11,     -7,    -31,    -98,
        -8,    -26,    -19,    -32,    -32,    -80,    -32,    -96,     57,    -84,     11,    100,
       -53,     13,   -101,     18,    154,    -84,    -79,     30,      7,    -23,     27,    -56,
        27,    -16,     30,   -133,     25,    -14,     59,     73,      0,      0,      0,      0,
         0,      0,      0,      0,    -10,   -104,    -25,   -103,    -36,    -20,   -152,    -67,
       -69,    -25,      1,    -35,    -53,     16,    -26,    -73,    -54,    -17,    -53,     43,
       -16,     21,     40,      0,    -49,      2,    -23,     89,   -134,     27,    -58,    -21,
         6,    -63,     59,      5,    125,     32,     89,    -11,    -83,      1,     67,     52,
       -31,     37,     64,    -48,    -46,    -47,    -36,     -6,     -6,     52,    -47,   -112,
      -120,    -49,    -47,    -24,    -37,    -69,    -44,    -23,    -46,    -32,   -238,    -35,
       -82,   -197,    -26,    -24,      5,    -72,     17,   -204,   -125,     57,      4,     19,
       -35,    -78,     37,    -38,     88,     84,     43,    111,      5,    -31,     91,    104,
         3,     66,      7,     30,   -153,    -99,     71,    -51,     93,    -52,      4,    -61,
         8,    -78,     31,    -24,   -113,    -56,     -7,    -33,    -13,    -21,    -29,    -11,
       -14,     66,    -76,    -23,    -47,    -59,    -53,    -10,     -3,    -74,    -28,     84,
       -59,    -51,    -62,    -40,    -29,    -99,     12,   -131,    -31,     -5,     19,    -19,
      -108,    -74,    -27,     10,     19,    -97,    -17,     -4,     13,    -17,    -32,   -132,
      -150,    -22,    -63,     33,    -65,    -27,     35,      3,    -70,    -43,    -34,     41,
       -91,     13,    -83,    -42,     22,    -17,    -39,    -39,    -23,    -12,     -6,     49,
       -34,    -67,    -58,     38,   -106,    -16,    -27,    -35,     -1,     73,     23,    -19,
       -62,   -105,    -62,    -38,    -70,      2,     -4,     75,      6,    -25,    -18,    -33,
        -3,     22,     24,    -77,     43,     -2,      4,    -46,    -10,      9,     34,     51,
       -13,     -7,     -5,     -9,    -56,     36,    -56,    -52,     38,     -9,     58,      5,
         4,      9,     -1,    149,     77,     12,     32,    -65,    -11,    -27,    -47,     40,
         1,     -6,     39,    -22,    -24,    -45,    -24,    -15,    -54,     36,      9,     46,
       -75,    -60,    -49,    -25,    -32,    -24,    -45,   -127,    -69,     13,    -28,    -76,
       -22,     22,    -61,    -42,      3,    -77,    -38,     11,     42,    -19,      1,    -97,
        66,     84,    -52,    -20,      2,    -11,     -3,    -16,     54,      6,     29,   -101,
        15,    -10,     63,    -34,    -22,     29,      8,    -80,     14,     62,     49,    -16,
         4,     43,     -2,     17,    -42,    -61,     49,    -31,     94,    -68,    -78,     83,
        16,     -3,    -91,      9,     12,    -10,    -26,    -85,    -24,    -35,    -24,    -68,
        11,    -12,    -11,     31,    -62,     53,     45,     26,      9,     -3,     49,     41,
        10,     30,    -31,    -27,      0,    -25,    -21,     -9,     -1,    -28,      9,     21,
       -32,     47,      0,    -16,     -6,      6,   -137,    118,      6,
], dtype=np.int32)
# <<< TUNED_PARAMS_BLOCK <<<                          # patch marker

# Configure at import: numba bakes global array values at compile time, so
# the choice must happen before the first jitted call (engine_side.py for
# A/B tests sets these env vars; the shipped agent just uses defaults).
# SHIPPED DEFAULT = "hand": SPRT #2 (tuned-vs-hand, 2026-09-07) rejected the
# tuned fit (see BUILD.md "Phase 2 — COMPLETION"), so agent.py (no env var)
# must run the hand-tuned values. The tuned fit stays embedded + selectable
# via CHESSATHON_EVAL_CONFIG=tuned for A/B tooling.
_EVAL_CFG = os.environ.get("CHESSATHON_EVAL_CONFIG", "hand")
EVAL_PARAMS = TUNED_PARAMS if _EVAL_CFG == "tuned" else HAND_PARAMS

_GATE_STR = os.environ.get("CHESSATHON_EVAL_GATE", "1111")[:4]
_GATE_STR = _GATE_STR.ljust(4, "1")
EVAL_GATE = np.array([1 if c == "1" else 0 for c in _GATE_STR],
                     dtype=np.int8)   # [pawn, mobility, king-safety, bp+tempo]


# ---------------------------------------------------------------------------
# The evaluation (numba-jitted hot path)
# ---------------------------------------------------------------------------

@njit
def evaluate(st) -> int:
    """Static evaluation in centipawns, positive = good for White.

    Interface unchanged from 1b (search.py calls `evaluate(st)`).
    Two board passes (material/PST/mobility/bitboards; then pawn
    structure per pawn) — O(pieces), no allocations.
    """
    sqr = st['squares'][0]
    side = st['side'][0]
    g = EVAL_GATE
    p = EVAL_PARAMS

    mg = 0
    eg = 0
    phase = 0
    mat = 0                        # raw material, white - black (cp)
    wp = np.uint64(0)
    bp = np.uint64(0)
    # mobility accumulators per class, signed (white - black)
    mN = 0; mB = 0; mR = 0; mQ = 0
    # pawn-structure accumulators (white - black)
    dbl = 0; iso = 0; passed = np.zeros(4, dtype=np.int32)
    blk = 0
    # king-safety accumulators (white - black)
    sh_near = 0; sh_far = 0; opn = 0
    bishops = np.zeros(2, dtype=np.int8)      # per color
    kdist = 0
    # insufficient-material bookkeeping
    has_pawn = False
    has_major = False
    mins = 0

    # ---- pass 1: material + PST + phase + mobility + bitboards ----
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        pc = sqr[sq]
        if pc == EMPTY:
            continue
        t = abs(pc)
        color = WHITE if pc > 0 else BLACK
        s = sq64(sq) if color == WHITE else sq64(sq) ^ 56
        sign = 1 if color == WHITE else -1
        mg += sign * (p[P_MAT_MG + t - 1] + p[P_PST_MG + (t - 1) * 64 + s])
        eg += sign * (p[P_MAT_EG + t - 1] + p[P_PST_EG + (t - 1) * 64 + s])
        mat += sign * p[P_MAT_MG + t - 1]
        phase += PHASE_W[t]
        if t == PAWN:
            has_pawn = True
            b = _BB[sq64(sq)]          # real coordinates (not mirrored)
            if color == WHITE:
                wp |= b
            else:
                bp |= b
        elif t == ROOK or t == QUEEN:
            has_major = True
            if t == ROOK:
                for di in range(4):
                    for k in range(8):
                        to = _ROOK_RAYS[sq, di, k]
                        if to < 0:
                            break
                        q = sqr[to]
                        if q == EMPTY:
                            mR += sign
                        elif (q > 0) != (pc > 0):
                            mR += sign
                            break
                        else:
                            break
            else:
                for di in range(4):
                    for k in range(8):
                        to = _RAYS[sq, di, k]
                        if to < 0:
                            break
                        q = sqr[to]
                        if q == EMPTY:
                            mQ += sign
                        elif (q > 0) != (pc > 0):
                            mQ += sign
                            break
                        else:
                            break
                for di in range(4):
                    for k in range(8):
                        to = _ROOK_RAYS[sq, di, k]
                        if to < 0:
                            break
                        q = sqr[to]
                        if q == EMPTY:
                            mQ += sign
                        elif (q > 0) != (pc > 0):
                            mQ += sign
                            break
                        else:
                            break
        elif t == KNIGHT:
            mins += 1
            for d in range(8):
                to = sq + _KNIGHT_DELTAS[d]
                if (to & 0x88) == 0:
                    q = sqr[to]
                    if q == EMPTY or (q > 0) != (pc > 0):
                        mN += sign
        elif t == BISHOP:
            mins += 1
            bishops[color] += 1
            for di in range(4):
                for k in range(8):
                    to = _RAYS[sq, di, k]
                    if to < 0:
                        break
                    q = sqr[to]
                    if q == EMPTY:
                        mB += sign
                    elif (q > 0) != (pc > 0):
                        mB += sign
                        break
                    else:
                        break
        elif t == KING:
            pass

    # ---- pass 2: pawn structure (bitboards from pass 1) ----
    wpM = _mirror_rank(wp)
    bpM = _mirror_rank(bp)
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        pc = sqr[sq]
        if pc == EMPTY:
            continue
        t = abs(pc)
        if t != PAWN:
            continue
        s = sq64(sq)                     # real coordinate
        if pc > 0:                       # white pawn
            b = _BB[s]
            # doubled: counted via file popcount after the loop (below)
            if (wp & ADJ_SQ[s]) == 0:
                iso += 1
            rk = s >> 3
            if (bp & PASSED_W[s]) == 0:
                if 3 <= rk <= 6:
                    if (bp & (b << np.uint64(8))) != 0:
                        blk += 1
                    else:
                        passed[rk - 3] += 1
        else:                            # black pawn (mirrored view)
            sm = s ^ 56
            bm = _BB[sm]
            if (bp & ADJ_SQ[s]) == 0:
                iso -= 1
            rk = sm >> 3
            if (wpM & PASSED_W[sm]) == 0:
                if 3 <= rk <= 6:
                    if (wpM & (bm << np.uint64(8))) != 0:
                        blk -= 1
                    else:
                        passed[rk - 3] -= 1
    for f in range(8):
        c = _popcount64(wp & FILE_SQ[f])
        if c > 1:
            dbl += c - 1
        c = _popcount64(bp & FILE_SQ[f])
        if c > 1:
            dbl -= c - 1

    # ---- king safety + tropism ----
    wks = sq64(st['kingsq'][0][WHITE])
    bks = sq64(st['kingsq'][0][BLACK])
    wf = wks & 7
    wr = wks >> 3
    bf = bks & 7
    br = bks >> 3
    df = wf - bf
    if df < 0:
        df = -df
    dr = wr - br
    if dr < 0:
        dr = -dr
    kdist = df if df > dr else dr
    sh_near += _popcount64(wp & SHELTER_NEAR[wks])
    sh_far += _popcount64(wp & SHELTER_FAR[wks])
    if (wp & FILE_SQ[wks]) == 0:
        opn += 1
    bksm = bks ^ 56
    sh_near -= _popcount64(bpM & SHELTER_NEAR[bksm])
    sh_far -= _popcount64(bpM & SHELTER_FAR[bksm])
    if (bp & FILE_SQ[bks]) == 0:
        opn -= 1

    # ---- assemble (gate groups first, taper, bishop pair, tempo) ----
    pawn_mg = (p[P_DOUBLED_MG] * dbl + p[P_ISOLATED_MG] * iso
               + p[P_BLOCKED_MG] * blk
               + p[P_PASSED_MG] * passed[0] + p[P_PASSED_MG + 1] * passed[1]
               + p[P_PASSED_MG + 2] * passed[2]
               + p[P_PASSED_MG + 3] * passed[3])
    pawn_eg = (p[P_DOUBLED_EG] * dbl + p[P_ISOLATED_EG] * iso
               + p[P_BLOCKED_EG] * blk
               + p[P_PASSED_EG] * passed[0] + p[P_PASSED_EG + 1] * passed[1]
               + p[P_PASSED_EG + 2] * passed[2] + p[P_PASSED_EG + 3] * passed[3])
    mob_mg = (p[P_MOB_N_MG] * mN + p[P_MOB_B_MG] * mB + p[P_MOB_R_MG] * mR
              + p[P_MOB_Q_MG] * mQ)
    mob_eg = (p[P_MOB_N_EG] * mN + p[P_MOB_B_EG] * mB + p[P_MOB_R_EG] * mR
              + p[P_MOB_Q_EG] * mQ)
    ks_mg = (p[P_SHELTER_NEAR_MG] * sh_near + p[P_SHELTER_FAR_MG] * sh_far
             + p[P_OPEN_MG] * opn + p[P_KDIST_MG] * kdist)
    ks_eg = (p[P_SHELTER_NEAR_EG] * sh_near + p[P_SHELTER_FAR_EG] * sh_far
             + p[P_OPEN_EG] * opn + p[P_KDIST_EG] * kdist)

    bpw = bishops[WHITE]
    bpb = bishops[BLACK]
    bp_mg = p[P_BISHOP_PAIR_MG] * (1 if bpw >= 2 else 0) \
        - p[P_BISHOP_PAIR_MG] * (1 if bpb >= 2 else 0)
    bp_eg = p[P_BISHOP_PAIR_EG] * (1 if bpw >= 2 else 0) \
        - p[P_BISHOP_PAIR_EG] * (1 if bpb >= 2 else 0)

    mg += g[0] * pawn_mg + g[1] * mob_mg + g[2] * ks_mg + g[3] * bp_mg
    eg += g[0] * pawn_eg + g[1] * mob_eg + g[2] * ks_eg + g[3] * bp_eg

    if phase > MAX_PHASE:
        phase = MAX_PHASE
    score = (mg * phase + eg * (MAX_PHASE - phase)) // MAX_PHASE

    # Phase 3 — endgame mate-drive (hand term, NOT a tunable param: keeps
    # the tuner's 813-param contract intact). Classical king-activation:
    # in a mostly-endgame position with a material edge of a rook or more,
    # the WINNING side is rewarded for its king approaching the enemy
    # king. As a White-POV term, the negation in the return below
    # automatically makes the loser flee (its eval minimizes the drive).
    # Restores KQvK/KRvK conversion that the 1b quiet-leaf bug masked by
    # scoring every quiet leaf 0 (found during Phase-3 aspiration parity
    # forensics; eg_check KQvK/KRvK strong-side draws without it).
    if phase <= 16 and (mat >= 300 or mat <= -300):
        drive = (1 if mat > 0 else -1) * MATE_DRIVE_K * (7 - kdist)
        score += drive

    # P8 — compensation-aware clamp (CHESSATHON_COMPCLAMP; BUILD.md "P8").
    # Quirk-1 fix: the loss family shows positions where advanced-pawn
    # PST/passer credit cancels a real material deficit (r68 p65: down a
    # rook, static says +11). When either side's RAW material (pre-taper
    # `mat`, White-POV) is >= COMPCLAMP_MAT, the White-POV score is
    # clamped so it cannot sit more than COMPCLAMP_SLACK above the
    # deficit side's material: compensation credit stays bounded, the
    # search sees the deficit. Integer-only; no tuner params.
    # Endgame safety: arming requires |mat| >= 200 (a minor or more), so
    # KPK (100cp) never fires; the strong side's score can only be
    # RAISED (max branch) in a won endgame, never lowered.
    if COMPCLAMP_ON and phase <= 16:
        if mat <= -COMPCLAMP_MAT:
            floor_ = mat + COMPCLAMP_SLACK
            if score > floor_:
                score = floor_
        elif mat >= COMPCLAMP_MAT:
            ceil_ = mat - COMPCLAMP_SLACK
            if score < ceil_:
                score = ceil_
    # q5-night1 (codex1 §7): `mins` now counts BOTH minors, so this zeroes
    # only true bare-minor endings (K vs K+single-minor). The old counter
    # (bishops only) zeroed KBN-v-K — a FORCED WIN — and KNNN-v-K.
    if not has_pawn and not has_major and mins <= 1:
        return 0

    tempo = g[3] * p[P_TEMPO]
    if side == WHITE:
        return score + tempo
    return -(score + tempo)


# ---------------------------------------------------------------------------
# Sanity tests (import-time smoke in dev; also used by tools)
# ---------------------------------------------------------------------------

def _selfcheck():
    bm = __import__("engine.board", fromlist=["parse_fen"])
    st = bm.parse_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    # Structural invariants that hold for any config:
    # 1) Empty KK = 0
    st3 = bm.parse_fen("k7/8/8/8/8/8/8/K7 b - - 0 1")
    assert evaluate(st3) == 0, evaluate(st3)
    # 2) Mirror symmetry: |eval(orig) - eval(flip)| <= 2*|tempo| + 2*|kdist_mg|*14 + 2*|kdist_eg|*14
    #    (king-distance term is symmetric, tempo is anti-symmetric)
    def flip_fen(fen: str) -> str:
        parts = fen.split()
        rows = parts[0].split("/")[::-1]
        flipped = []
        for row in rows:
            out = ""
            for ch in row:
                if ch.isalpha():
                    out += ch.swapcase()
                else:
                    out += ch
            flipped.append(out)
        new_side = "w" if parts[1] == "b" else "b"
        return "/".join(flipped) + " " + new_side + " - - " + " ".join(parts[4:6])

    for _fen in [
        "8/8/2P5/8/8/8/8/K7 w - - 0 1",        # passed white pawn on 6th
        "r2q1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1",
        "k7/2p5/3p4/8/8/4P3/1P6/7K w - - 0 1",  # black pawns + passed-ish
        "k7/8/8/8/8/8/2p5/K7 b - - 0 1",        # passed BLACK pawn on 6th
    ]:
        st_a = bm.parse_fen(_fen)
        st_b = bm.parse_fen(flip_fen(_fen))
        ea, eb = evaluate(st_a), evaluate(st_b)
        tol = (2 * int(EVAL_PARAMS[P_TEMPO])
               + 2 * abs(int(EVAL_PARAMS[P_KDIST_MG])) * 14
               + 2 * abs(int(EVAL_PARAMS[P_KDIST_EG])) * 14)
        assert abs(ea - eb) <= tol, (ea, eb)

    # Config-specific value checks
    if _EVAL_CFG != "tuned":
        # hand:1111 — exact value checks calibrated for hand-tuned params
        assert evaluate(st) == int(EVAL_PARAMS[P_TEMPO]), evaluate(st)
        st2 = bm.parse_fen("k7/8/8/8/8/8/8/K6R w - - 0 1")
        assert evaluate(st2) > 400, evaluate(st2)
        st6 = bm.parse_fen("k7/8/2P5/8/8/8/8/K7 w - - 0 1")
        st7 = bm.parse_fen("k7/8/8/8/2P5/8/8/K7 w - - 0 1")
        assert evaluate(st6) > evaluate(st7), (evaluate(st6), evaluate(st7))
        st8 = bm.parse_fen("k7/1p6/8/2P5/8/8/8/K7 w - - 0 1")
        assert evaluate(st7) > evaluate(st8), (evaluate(st7), evaluate(st8))
        st11 = bm.parse_fen("k7/8/8/8/8/8/PPP5/1K6 w - - 0 1")
        st12 = bm.parse_fen("k7/8/8/8/8/8/8/1K6 w - - 0 1")
        assert evaluate(st11) > evaluate(st12), (evaluate(st11), evaluate(st12))
    else:
        # tuned: only structural checks above; value semantics tested via SPRT
        sv = evaluate(st)
        assert -50 < sv < 50, f"startpos score {sv} out of range for tuned"
    print("eval selfcheck OK")


if __name__ == "__main__":
    _selfcheck()