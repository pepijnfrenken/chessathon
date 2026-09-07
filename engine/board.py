"""Chessathon engine Phase 1b — board, move generation, make/unmake, hashing.

OUR OWN original implementation (ORIGINALITY.md: fresh code, standard
published *concepts* only: 0x88 mailbox representation, zobrist hashing,
precomputed ray tables). Written from an empty file in this repo during
the event. python-chess is used ONLY as an external oracle for perft
parity tests and root-legality checks — never inside the hot path.

Representation:
  - 0x88 mailbox: square = rank*16 + file, ranks 0..7 (rank 0 = rank 1,
    white's back rank); squares[128] is int8:
        0 empty, +1..+6 = white P,N,B,R,Q,K, -1..-6 = black.
  - side: 1 = white to move, 0 = black to move.
  - castling bits: 1=WK, 2=WQ, 4=BK, 8=BQ.
  - ep: -1, or the 0x88 square behind a just-double-pushed pawn
    (canonicalised: only set when an enemy pawn could actually capture).
  - halfmove: fifty-move clock from the FEN.
  - key: zobrist, maintained incrementally by make/unmake.

Move encoding (int32):
  [from 0..6][to 7..13][flags 14..17][promo 18..19]
  (7-bit from/to: 0x88 squares go up to 119, so 6-bit fields would
  truncate any square on rank >= 4.)
  flags: 0 quiet, 1 double push, 2 castle K, 3 castle Q, 4 capture,
         5 en-passant, 6 promotion, 7 promotion-capture.
  promo index: 0=N, 1=B, 2=R, 3=Q (piece codes +2).

State is a 1-element numpy structured array mutated in place by the
jitted kernels, so the search can share one board object with zero
serialization cost.
"""

import numpy as np

from numba import njit

# ---------------------------------------------------------------------------
# Constants / piece codes
# ---------------------------------------------------------------------------

EMPTY = 0
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6
WHITE, BLACK = 1, 0

# into move flags
F_QUIET = 0
F_DOUBLE = 1
F_KCASTLE = 2
F_QCASTLE = 3
F_CAPTURE = 4
F_EP = 5
F_PROMO = 6
F_PROMOCAP = 7

MAX_MOVES = 256

# ---------------------------------------------------------------------------
# Board state dtype (numba-typed structured array)
# ---------------------------------------------------------------------------

STATE_DTYPE = np.dtype([
    ("squares", np.int8, (128,)),
    ("side", np.int8),
    ("castle", np.int8),
    ("ep", np.int8),
    ("halfmove", np.int16),
    ("kingsq", np.int8, (2,)),      # king square per color (0 black, 1 white)
    ("key", np.uint64),
])


def new_state() -> np.ndarray:
    """Fresh board state array (all zeros)."""
    return np.zeros(1, dtype=STATE_DTYPE)


# ---------------------------------------------------------------------------
# Precomputed tables (built once at import; read-only inside jitted code)
# ---------------------------------------------------------------------------

_KNIGHT_DELTAS = np.array([-33, -31, -18, -14, 14, 18, 31, 33], dtype=np.int8)
_KING_DELTAS = np.array([-17, -16, -15, -1, 1, 15, 16, 17], dtype=np.int8)
_BISHOP_DIRS = np.array([-17, -15, 15, 17], dtype=np.int8)
_ROOK_DIRS = np.array([-16, -1, 1, 16], dtype=np.int8)

# RAYS[sq][dir][step]: on-board squares in direction dir, -1 terminated.
_RAYS = np.full((128, 4, 8), -1, dtype=np.int16)
for _sq in range(128):
    for _d in range(4):
        _s = _sq
        _n = 0
        while True:
            _s += int(_BISHOP_DIRS[_d])
            if (_s & 0x88) != 0:
                break
            _RAYS[_sq, _d, _n] = _s
            _n += 1

# Zobrist keys: our own scheme, seeded PRNG (values are concept-irrelevant).
_RNG = np.random.default_rng(0xC0FFEE)
ZPIECE = _RNG.integers(0, 2 ** 64, size=(128, 12), dtype=np.uint64)   # piece+5
ZSIDE = _RNG.integers(0, 2 ** 64, size=1, dtype=np.uint64)[0]
ZCASTLE = _RNG.integers(0, 2 ** 64, size=16, dtype=np.uint64)
ZEP = _RNG.integers(0, 2 ** 64, size=8, dtype=np.uint64)
del _RNG

_PIECE_CHARS = " PNBRQK"          # type -> char; sign flips for black
_PIECE_FROM_CHAR = {c: i for i, c in enumerate(_PIECE_CHARS)}


# ---------------------------------------------------------------------------
# Small jitted helpers
# ---------------------------------------------------------------------------

@njit(inline="always")
def is_piece_color(p: int, color: int) -> bool:
    """True if piece p belongs to color (1 white, 0 black)."""
    return (p > 0) == (color == WHITE)


@njit(inline="always")
def sq64(sq: int) -> int:
    """0x88 square -> 0..63 index (a1=0 .. h8=63)."""
    return ((sq >> 4) << 3) + (sq & 7)


@njit(inline="always")
def make_move(frm: int, to: int, flags: int, promo: int) -> int:
    return frm | (to << 7) | (flags << 14) | (promo << 18)


@njit(inline="always")
def m_from(m: int) -> int:
    return m & 127


@njit(inline="always")
def m_to(m: int) -> int:
    return (m >> 7) & 127


@njit(inline="always")
def m_flags(m: int) -> int:
    return (m >> 14) & 15


@njit(inline="always")
def m_promo(m: int) -> int:
    return (m >> 18) & 3


@njit(inline="always")
def in_check(st) -> bool:
    """Is the side to move in check?"""
    return attacked(st, st['kingsq'][0][st['side'][0]], 1 - st['side'][0])


# ---------------------------------------------------------------------------
# Attack detection
# ---------------------------------------------------------------------------

@njit
def attacked(st, sq: int, by_color: int) -> bool:
    """Is square `sq` attacked by any piece of color `by_color`?"""
    sqr = st['squares'][0]
    # pawns
    if by_color == WHITE:
        a = sq - 17
        if (a & 0x88) == 0 and sqr[a] == PAWN:
            return True
        a = sq - 15
        if (a & 0x88) == 0 and sqr[a] == PAWN:
            return True
    else:
        a = sq + 17
        if (a & 0x88) == 0 and sqr[a] == -PAWN:
            return True
        a = sq + 15
        if (a & 0x88) == 0 and sqr[a] == -PAWN:
            return True
    # knights
    for d in range(8):
        a = sq + _KNIGHT_DELTAS[d]
        if (a & 0x88) == 0 and sqr[a] == (KNIGHT if by_color == WHITE else -KNIGHT):
            return True
    # king
    for d in range(8):
        a = sq + _KING_DELTAS[d]
        if (a & 0x88) == 0 and sqr[a] == (KING if by_color == WHITE else -KING):
            return True
    # sliders: walk our precomputed rays, stop at the first piece
    # (diagonal rays for bishops/queens, orthogonal rays for rooks/queens)
    for d in range(4):
        for s in range(8):
            a = _RAYS[sq, d, s]
            if a < 0:
                break
            p = sqr[a]
            if p != EMPTY:
                if is_piece_color(p, by_color) and abs(p) in (BISHOP, QUEEN):
                    return True
                break
    for d in range(4):
        for s in range(8):
            a = _ROOK_RAYS[sq, d, s]
            if a < 0:
                break
            p = sqr[a]
            if p != EMPTY:
                if is_piece_color(p, by_color) and abs(p) in (ROOK, QUEEN):
                    return True
                break
    return False


# ---------------------------------------------------------------------------
# make / unmake
# ---------------------------------------------------------------------------

@njit
def make_move_apply(st, move: int):
    """Apply `move` (pseudo-legal, side to move). Caller saves what unmake
    needs BEFORE calling: captured piece code, castle, ep, halfmove, key."""
    frm = m_from(move)
    to = m_to(move)
    fl = m_flags(move)
    promo = m_promo(move)
    sqr = st['squares'][0]
    side = st['side'][0]
    pc = sqr[frm]
    ptype = abs(pc)
    key = st['key'][0]

    # captured piece (not the ep pawn — handled below)
    captured = sqr[to]
    if fl == F_EP:
        captured = sqr[to - 16 if side == WHITE else to + 16]
        sqr[to - 16 if side == WHITE else to + 16] = EMPTY
        key ^= ZPIECE[to - 16 if side == WHITE else to + 16, captured + 5]

    # leave ep square in the key
    if st['ep'][0] >= 0:
        key ^= ZEP[st['ep'][0] & 7]

    # fifty-move clock: reset on pawn move or capture
    half = 0 if (ptype == PAWN or captured != EMPTY) else st['halfmove'][0] + 1

    # move the piece (promotion changes it)
    placed = pc
    if fl == F_PROMO or fl == F_PROMOCAP:
        placed = (promo + 2) * (1 if side == WHITE else -1)
    sqr[to] = placed
    sqr[frm] = EMPTY
    key ^= ZPIECE[frm, pc + 5] ^ ZPIECE[to, placed + 5]
    if captured != EMPTY:
        key ^= ZPIECE[to, captured + 5]

    # castling: shift the rook
    if fl == F_KCASTLE:
        rf, rt = to + 1, to - 1
        key ^= ZPIECE[rf, sqr[rf] + 5] ^ ZPIECE[rt, sqr[rf] + 5]
        sqr[rt] = sqr[rf]
        sqr[rf] = EMPTY
    elif fl == F_QCASTLE:
        rf, rt = to - 2, to + 1
        key ^= ZPIECE[rf, sqr[rf] + 5] ^ ZPIECE[rt, sqr[rf] + 5]
        sqr[rt] = sqr[rf]
        sqr[rf] = EMPTY

    if ptype == KING:
        st['kingsq'][0][side] = to

    # castling rights: king moved / rook moved / rook captured
    castle = st['castle'][0]
    if ptype == KING:
        castle &= ~(3 if side == WHITE else 12)
    elif ptype == ROOK:
        if frm == 7:
            castle &= ~1
        elif frm == 0:
            castle &= ~2
        elif frm == 119:
            castle &= ~4
        elif frm == 112:
            castle &= ~8
    if captured != EMPTY:
        if to == 7:
            castle &= ~1
        elif to == 0:
            castle &= ~2
        elif to == 119:
            castle &= ~4
        elif to == 112:
            castle &= ~8
    if castle != st['castle'][0]:
        key ^= ZCASTLE[st['castle'][0]] ^ ZCASTLE[castle]
    st['castle'][0] = castle

    # ep square from a double push, only when an enemy pawn could capture.
    # White pawn e2-e4 lands on rank 3 with ep square e3 (rank 2); the only
    # black pawns able to capture sit beside the landing square (d4/f4) and
    # attack diagonally through e3, so test to-1/to+1 for an enemy pawn.
    new_ep = -1
    if fl == F_DOUBLE:
        cand1, cand2 = to - 1, to + 1
        enemy_pawn = -PAWN if side == WHITE else PAWN
        if (cand1 & 0x88) == 0 and sqr[cand1] == enemy_pawn:
            new_ep = frm + 16 if side == WHITE else frm - 16
        elif (cand2 & 0x88) == 0 and sqr[cand2] == enemy_pawn:
            new_ep = frm + 16 if side == WHITE else frm - 16
    if new_ep >= 0:
        key ^= ZEP[new_ep & 7]
    st['ep'][0] = new_ep

    st['side'][0] = 1 - side
    st['halfmove'][0] = half
    st['key'][0] = key ^ ZSIDE


@njit
def unmake_move(st, move: int, captured: int, prev_castle: int, prev_ep: int,
                prev_halfmove: int, prev_key: int):
    """Undo make_move_apply. Needs exactly the values saved before it."""
    frm = m_from(move)
    to = m_to(move)
    fl = m_flags(move)
    sqr = st['squares'][0]
    side = 1 - st['side'][0]                       # the side that made the move
    placed = sqr[to]

    if fl == F_PROMO or fl == F_PROMOCAP:
        sqr[frm] = PAWN if side == WHITE else -PAWN
    else:
        sqr[frm] = placed
    sqr[to] = EMPTY

    if fl == F_EP:
        sqr[to - 16 if side == WHITE else to + 16] = captured
    else:
        sqr[to] = captured

    if fl == F_KCASTLE:
        rt, rf = to - 1, to + 1
        sqr[rf] = sqr[rt]
        sqr[rt] = EMPTY
    elif fl == F_QCASTLE:
        rt, rf = to + 1, to - 2
        sqr[rf] = sqr[rt]
        sqr[rt] = EMPTY

    if abs(placed) == KING or fl == F_KCASTLE or fl == F_QCASTLE:
        st['kingsq'][0][side] = frm
    if captured != EMPTY and fl != F_EP and abs(captured) == KING:
        # only reachable from a position where the enemy king was captured;
        # keep the state consistent for safety.
        st['kingsq'][0][1 - side] = to

    st['castle'][0] = prev_castle
    st['ep'][0] = prev_ep
    st['halfmove'][0] = prev_halfmove
    st['key'][0] = prev_key
    st['side'][0] = side


# ---------------------------------------------------------------------------
# Pseudo-legal move generation
# ---------------------------------------------------------------------------

@njit
def gen_moves(st, moves, cap_only: bool) -> int:
    """Fill `moves` with pseudo-legal moves for the side to move.
    cap_only=True skips quiet moves except e.p./capture promotions.
    Returns the move count."""
    sqr = st['squares'][0]
    side = st['side'][0]
    enemy = 1 - side
    cnt = 0

    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        p = sqr[sq]
        if not is_piece_color(p, side):
            continue
        t = abs(p)
        rank = sq >> 4

        if t == PAWN:
            if side == WHITE:
                # pushes
                if not cap_only:
                    to = sq + 16
                    if (to & 0x88) == 0 and sqr[to] == EMPTY:
                        if (to >> 4) == 7:
                            for pr in range(4):
                                moves[cnt] = make_move(sq, to, F_PROMO, pr)
                                cnt += 1
                        else:
                            moves[cnt] = make_move(sq, to, F_QUIET, 0)
                            cnt += 1
                            if rank == 1 and sqr[sq + 32] == EMPTY:
                                moves[cnt] = make_move(sq, sq + 32, F_DOUBLE, 0)
                                cnt += 1
                # captures incl. ep + promo captures
                for d in (15, 17):
                    to = sq + d
                    if (to & 0x88) == 0:
                        if sqr[to] != EMPTY and is_piece_color(sqr[to], enemy):
                            if (to >> 4) == 7:
                                for pr in range(4):
                                    moves[cnt] = make_move(sq, to, F_PROMOCAP, pr)
                                    cnt += 1
                            else:
                                moves[cnt] = make_move(sq, to, F_CAPTURE, 0)
                                cnt += 1
                        elif to == st['ep'][0]:
                            moves[cnt] = make_move(sq, to, F_EP, 0)
                            cnt += 1
            else:
                if not cap_only:
                    to = sq - 16
                    if (to & 0x88) == 0 and sqr[to] == EMPTY:
                        if (to >> 4) == 0:
                            for pr in range(4):
                                moves[cnt] = make_move(sq, to, F_PROMO, pr)
                                cnt += 1
                        else:
                            moves[cnt] = make_move(sq, to, F_QUIET, 0)
                            cnt += 1
                            if rank == 6 and sqr[sq - 32] == EMPTY:
                                moves[cnt] = make_move(sq, sq - 32, F_DOUBLE, 0)
                                cnt += 1
                for d in (-15, -17):
                    to = sq + d
                    if (to & 0x88) == 0:
                        if sqr[to] != EMPTY and is_piece_color(sqr[to], enemy):
                            if (to >> 4) == 0:
                                for pr in range(4):
                                    moves[cnt] = make_move(sq, to, F_PROMOCAP, pr)
                                    cnt += 1
                            else:
                                moves[cnt] = make_move(sq, to, F_CAPTURE, 0)
                                cnt += 1
                        elif to == st['ep'][0]:
                            moves[cnt] = make_move(sq, to, F_EP, 0)
                            cnt += 1

        elif t == KNIGHT or t == KING:
            # NOTE (Phase 4 audit fix): knights were previously SKIPPED
            # entirely in cap_only (qsearch) mode — silent knight-capture
            # blindness in every not-in-check quiescence node. The guard
            # below (quiet moves suppressed by `if not cap_only`) is all
            # the filtering needed; knight captures must be generated.
            deltas = _KNIGHT_DELTAS if t == KNIGHT else _KING_DELTAS
            for d in range(8):
                to = sq + deltas[d]
                if (to & 0x88) == 0:
                    q = sqr[to]
                    if q == EMPTY:
                        if not cap_only:
                            moves[cnt] = make_move(sq, to, F_QUIET, 0)
                            cnt += 1
                    elif is_piece_color(q, enemy):
                        moves[cnt] = make_move(sq, to, F_CAPTURE, 0)
                        cnt += 1

        elif t == BISHOP or t == ROOK or t == QUEEN:
            # diagonal rays (bishop, and queen's diagonals)
            if t == BISHOP or t == QUEEN:
                for di in range(4):
                    for s in range(8):
                        to = _RAYS[sq, di, s]
                        if to < 0:
                            break
                        q = sqr[to]
                        if q == EMPTY:
                            if not cap_only:
                                moves[cnt] = make_move(sq, to, F_QUIET, 0)
                                cnt += 1
                        elif is_piece_color(q, enemy):
                            moves[cnt] = make_move(sq, to, F_CAPTURE, 0)
                            cnt += 1
                            break
                        else:
                            break
            # orthogonal rays (rook, and queen's orthogonals)
            if t == ROOK or t == QUEEN:
                for di in range(4):
                    for s in range(8):
                        to = _ROOK_RAYS[sq, di, s]
                        if to < 0:
                            break
                        q = sqr[to]
                        if q == EMPTY:
                            if not cap_only:
                                moves[cnt] = make_move(sq, to, F_QUIET, 0)
                                cnt += 1
                        elif is_piece_color(q, enemy):
                            moves[cnt] = make_move(sq, to, F_CAPTURE, 0)
                            cnt += 1
                            break
                        else:
                            break

    # castling (never in cap-only mode; never possible while in check —
    # verified by the attack tests below)
    if not cap_only:
        castle = st['castle'][0]
        if side == WHITE:
            if (castle & 1) and sqr[4] == KING and sqr[5] == EMPTY \
                    and sqr[6] == EMPTY and sqr[7] == ROOK \
                    and not attacked(st, 4, enemy) \
                    and not attacked(st, 5, enemy) \
                    and not attacked(st, 6, enemy):
                moves[cnt] = make_move(4, 6, F_KCASTLE, 0)
                cnt += 1
            if (castle & 2) and sqr[4] == KING and sqr[1] == EMPTY \
                    and sqr[2] == EMPTY and sqr[3] == EMPTY \
                    and sqr[0] == ROOK \
                    and not attacked(st, 4, enemy) \
                    and not attacked(st, 3, enemy) \
                    and not attacked(st, 2, enemy):
                moves[cnt] = make_move(4, 2, F_QCASTLE, 0)
                cnt += 1
        else:
            if (castle & 4) and sqr[116] == -KING and sqr[117] == EMPTY \
                    and sqr[118] == EMPTY and sqr[119] == -ROOK \
                    and not attacked(st, 116, enemy) \
                    and not attacked(st, 117, enemy) \
                    and not attacked(st, 118, enemy):
                moves[cnt] = make_move(116, 118, F_KCASTLE, 0)
                cnt += 1
            if (castle & 8) and sqr[116] == -KING and sqr[113] == EMPTY \
                    and sqr[114] == EMPTY and sqr[115] == EMPTY \
                    and sqr[112] == -ROOK \
                    and not attacked(st, 116, enemy) \
                    and not attacked(st, 115, enemy) \
                    and not attacked(st, 114, enemy):
                moves[cnt] = make_move(116, 114, F_QCASTLE, 0)
                cnt += 1

    return cnt


# Rebuild ROOK_RAYS for the queen's orthogonal rays (kept separate for the
# 4-ray walk loops above; _ROOK_RAYS is built at module import).
_ROOK_RAYS = np.full((128, 4, 8), -1, dtype=np.int16)
for _sq in range(128):
    for _d in range(4):
        _s = _sq
        _n = 0
        while True:
            _s += int(_ROOK_DIRS[_d])
            if (_s & 0x88) != 0:
                break
            _ROOK_RAYS[_sq, _d, _n] = _s
            _n += 1


@njit
def legal_moves(st, moves, cap_only: bool) -> int:
    """Fill `moves` with legal moves (make + king-safety test + undo).
    Returns the count."""
    cnt = gen_moves(st, moves, cap_only)
    out = 0
    for i in range(cnt):
        mv = moves[i]
        captured = st['squares'][0][m_to(mv)]
        fl = m_flags(mv)
        if fl == F_EP:
            captured = st['squares'][0][m_to(mv) - 16 if st['side'][0] == WHITE
                                  else m_to(mv) + 16]
        pc = st['squares'][0][m_from(mv)]
        prev_castle = st['castle'][0]
        prev_ep = st['ep'][0]
        prev_half = st['halfmove'][0]
        prev_key = st['key'][0]
        make_move_apply(st, mv)
        if not attacked(st, st['kingsq'][0][1 - st['side'][0]], st['side'][0]):
            moves[out] = mv
            out += 1
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half, prev_key)
    return out


# ---------------------------------------------------------------------------
# Perft (dev/testing gate; jitted for speed)
# ---------------------------------------------------------------------------

@njit
def perft(st, depth: int, scratch, ply: int) -> int:
    """Count legal positions `depth` plies ahead. `scratch` is a caller-owned
    (MAXPLY x MAX_MOVES) int32 buffer; each recursion level uses its own row
    so nested calls never clobber an ancestor's move list."""
    if depth == 0:
        return 1
    cnt = legal_moves(st, scratch[ply], False)
    if depth == 1:
        return cnt
    total = 0
    me = st['side'][0]
    for i in range(cnt):
        mv = scratch[ply][i]
        captured = st['squares'][0][m_to(mv)]
        fl = m_flags(mv)
        if fl == F_EP:
            captured = st['squares'][0][m_to(mv) - 16 if me == WHITE
                                        else m_to(mv) + 16]
        prev_castle = st['castle'][0]
        prev_ep = st['ep'][0]
        prev_half = st['halfmove'][0]
        prev_key = st['key'][0]
        make_move_apply(st, mv)
        if not attacked(st, st['kingsq'][0][1 - st['side'][0]], st['side'][0]):
            total += perft(st, depth - 1, scratch, ply + 1)
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half, prev_key)
    return total


@njit
def _perft_bd(st, depth, scratch, ply, c):
    """Recursive perft with a 6-counter breakdown:
    [0] nodes, [1] captures, [2] ep, [3] castling, [4] promotions,
    [5] checks."""
    if depth == 0:
        c[0] += 1
        if in_check(st):
            c[5] += 1
        return
    cnt = legal_moves(st, scratch[ply], False)
    me = st['side'][0]
    for i in range(cnt):
        mv = scratch[ply][i]
        fl = m_flags(mv)
        captured = st['squares'][0][m_to(mv)]
        if fl == F_EP:
            captured = st['squares'][0][m_to(mv) - 16 if me == WHITE
                                        else m_to(mv) + 16]
        prev_castle = st['castle'][0]
        prev_ep = st['ep'][0]
        prev_half = st['halfmove'][0]
        prev_key = st['key'][0]
        make_move_apply(st, mv)
        if not attacked(st, st['kingsq'][0][1 - st['side'][0]], st['side'][0]):
            if fl in (F_CAPTURE, F_PROMOCAP, F_EP) or captured != EMPTY:
                c[1] += 1
            if fl == F_EP:
                c[2] += 1
            if fl == F_KCASTLE or fl == F_QCASTLE:
                c[3] += 1
            if fl == F_PROMO or fl == F_PROMOCAP:
                c[4] += 1
            _perft_bd(st, depth - 1, scratch, ply + 1, c)
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half, prev_key)


@njit
def perft_breakdown(st, depth: int, scratch):
    """Perft with a move-type breakdown, returns (nodes, captures, ep,
    castles, promotions, checks)."""
    counters = np.zeros(6, dtype=np.int64)
    _perft_bd(st, depth, scratch, 0, counters)
    return (counters[0], counters[1], counters[2],
            counters[3], counters[4], counters[5])


# module-level scratch buffers (passed into jitted fns as writable args)
MAX_PLY = 64
MOVES = np.zeros((MAX_PLY, MAX_MOVES), dtype=np.int32)  # per-ply move buffer


# ---------------------------------------------------------------------------
# FEN (pure Python, cold path)
# ---------------------------------------------------------------------------

def parse_fen(fen: str) -> np.ndarray:
    """Parse a FEN string into a board state array. Raises ValueError on
    malformed input."""
    parts = fen.strip().split()
    if not parts:
        raise ValueError("empty FEN")
    placement = parts[0]
    st = new_state()
    sqr = st["squares"][0]
    r = 7
    for token in placement.split("/"):
        f = 0
        for ch in token:
            if ch.isdigit():
                f += int(ch)
            else:
                if f > 7 or r < 0:
                    raise ValueError(f"bad placement: {placement}")
                pc = _PIECE_FROM_CHAR.get(ch.upper())
                if pc is None or pc == 0:
                    raise ValueError(f"bad piece char: {ch}")
                sq = r * 16 + f
                sqr[sq] = pc if ch.isupper() else -pc
                f += 1
        if f != 8:
            raise ValueError(f"rank width != 8: {placement}")
        r -= 1
    if r != -1:
        raise ValueError(f"too few ranks: {placement}")

    side_str = parts[1] if len(parts) > 1 else "w"
    st["side"][0] = 1 if side_str == "w" else 0

    castle_str = parts[2] if len(parts) > 2 else "-"
    c = 0
    if "K" in castle_str:
        c |= 1
    if "Q" in castle_str:
        c |= 2
    if "k" in castle_str:
        c |= 4
    if "q" in castle_str:
        c |= 8
    st["castle"][0] = c

    ep_str = parts[3] if len(parts) > 3 else "-"
    if ep_str != "-":
        file_c = ord(ep_str[0]) - ord("a")
        rank_c = int(ep_str[1]) - 1
        st["ep"][0] = rank_c * 16 + file_c
    else:
        # new_state() zero-fills: ep MUST be -1 when absent, or the parse
        # hashes ZEP[0] into the root key while in-search makes clear ep
        # to -1 — the root position would never match a repetition and
        # won endgames shuffle into threefold draws (Phase 3 find).
        st["ep"][0] = -1

    st["halfmove"][0] = int(parts[4]) if len(parts) > 4 else 0

    # king squares + zobrist key from scratch
    key = np.uint64(0)
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        p = sqr[sq]
        if p == EMPTY:
            continue
        key ^= ZPIECE[sq, p + 5]
        if abs(p) == KING:
            st["kingsq"][0][1 if p > 0 else 0] = sq
    if st["side"][0] == 1:
        key ^= ZSIDE
    if c:
        key ^= ZCASTLE[c]
    if st["ep"][0] >= 0:
        key ^= ZEP[st["ep"][0] & 7]
    st["key"][0] = key
    return st


def to_fen(st: np.ndarray) -> str:
    """Export the board state back to a FEN string (debug/testing)."""
    sqr = st["squares"][0]
    rows = []
    for r in range(7, -1, -1):
        row = ""
        gap = 0
        for f in range(8):
            p = sqr[r * 16 + f]
            if p == EMPTY:
                gap += 1
            else:
                if gap:
                    row += str(gap)
                    gap = 0
                ch = _PIECE_CHARS[abs(p)]
                row += ch if (p > 0) else ch.lower()
        if gap:
            row += str(gap)
        rows.append(row)
    side = "w" if st["side"][0] == 1 else "b"
    c = int(st["castle"][0])
    castle = ""
    if c & 1:
        castle += "K"
    if c & 2:
        castle += "Q"
    if c & 4:
        castle += "k"
    if c & 8:
        castle += "q"
    castle = castle or "-"
    ep = "-"
    if st["ep"][0] >= 0:
        e = int(st["ep"][0])
        ep = chr(ord("a") + (e & 7)) + str((e >> 4) + 1)
    return f"{'/'.join(rows)} {side} {castle} {ep} {int(st['halfmove'][0])} 1"


def move_to_uci(move: int) -> str:
    """Encode our move int as a UCI string."""
    frm = m_from(move)
    to = m_to(move)
    fl = m_flags(move)
    promo = m_promo(move)
    s = chr(ord("a") + (frm & 7)) + str((frm >> 4) + 1) + \
        chr(ord("a") + (to & 7)) + str((to >> 4) + 1)
    if fl == F_PROMO or fl == F_PROMOCAP:
        s += "nbrq"[promo]
    return s