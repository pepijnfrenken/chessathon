"""Chessathon engine Phase 1b — search core (numba-jitted).

Iterative-deepening negamax alpha-beta with:
  - principal variation search (zero-window sibling re-search)
  - transposition table (engine.tt; TT move ordering + score cutoffs)
  - MVV-LVA capture ordering + 2 killers/ply + quiet history
  - quiescence search (stand-pat + captures; full evasions in check;
    QCAP depth cap)
  - null-move pruning (R=2, eval >= beta, endgame zugzwang guard)
  - late move reductions (quiet moves, depth >= 3, cap 2)
  - check extension (+1 ply)
  - repetition (path zobrist keys) + fifty-move draws

Time: aborted from INSIDE the recursion via a monotonic clock (ctypes
CFUNCTYPE callback — numba has no time_ns) checked against a deadline
every 1024 nodes; a TIMEOUT sentinel propagates to the root, which keeps
the last completed iteration's best move. No aspiration windows in 1b
(they arrive with the tuning phase); every iteration runs full-window.

Scores: centipawns from the side to move; MATE at +-30000 with
mate-distance (checkmate = -MATE + ply); TT stores MATE-ply adjusted.
Sentinels: TIMEOUT = 1e9 (never stored, never compared as a score).
"""

import ctypes
import time

import numpy as np

from numba import njit

from engine.board import (EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
                          WHITE, BLACK, F_QUIET, F_DOUBLE, F_KCASTLE,
                          F_QCASTLE, F_CAPTURE, F_EP, F_PROMO, F_PROMOCAP,
                          MAX_MOVES, MAX_PLY, ZEP as _ZEP, ZSIDE as _ZSIDE,
                          m_from, m_to, m_flags, m_promo,
                          make_move_apply, unmake_move, legal_moves,
                          in_check, sq64)
from engine.eval import evaluate
from engine.tt import (BOUND_NONE, BOUND_LOWER, BOUND_UPPER, BOUND_EXACT,
                       tt_probe, tt_store)

MATE = 30000
INF = 32000
TIMEOUT = 1_000_000_000       # sentinel outside all real scores
NULL_R = 2
LMR_MIN_DEPTH = 3
LMR_MAX = 2
QCAP = 12                     # quiescence depth cap
REP_LOOKBACK = 16             # plies of search path scanned for repeats
MAX_ROOT_DEPTH = 64

_NOW = ctypes.CFUNCTYPE(ctypes.c_longlong)(lambda: time.monotonic_ns())

# dummy tables for qsearch ordering (q-search uses no killers/history)
_KILLER_DUMMY = np.zeros((2, MAX_PLY), dtype=np.int32)
_HIST_DUMMY = np.zeros((2, 64, 64), dtype=np.int32)
_VICTIM = np.array([0, 100, 320, 330, 500, 900, 20000], dtype=np.int32)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@njit(inline="always")
def _time_up(nodes, deadline) -> bool:
    if (nodes[0] & 1023) == 0:
        return _NOW() >= deadline
    return False


@njit(inline="always")
def _is_quiet(mv: int) -> bool:
    fl = m_flags(mv)
    return fl in (F_QUIET, F_DOUBLE, F_KCASTLE, F_QCASTLE)


@njit
def _draw_score(st, rep, ply) -> bool:
    """Fifty-move and repetition draws. Records rep[ply] = key. Returns
    True if the position is a draw."""
    if st['halfmove'][0] >= 100:
        return True
    key = st['key'][0]
    rep[ply] = key
    lo = ply - REP_LOOKBACK
    if lo < 0:
        lo = 0
    p = ply - 2
    while p >= lo:
        if rep[p] == key:
            return True
        p -= 2
    return False


@njit
def _count_nonpawns(st) -> int:
    n = 0
    sqr = st['squares'][0]
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        t = sqr[sq]
        if t < 0:
            t = -t
        if t == KNIGHT or t == BISHOP or t == ROOK or t == QUEEN:
            n += 1
    return n


@njit
def _score_move(mv: int, st, ttmove: int, killers, hist, ply: int) -> int:
    """Ordering score: TT move >> captures (MVV-LVA) > killers > history
    > rest; promotions above quiet captures."""
    if mv == ttmove:
        return 1 << 20
    fl = m_flags(mv)
    if fl in (F_PROMO, F_PROMOCAP):
        return 800000 + _VICTIM[m_promo(mv) + 2]
    if fl in (F_CAPTURE, F_EP, F_PROMOCAP):
        victim = PAWN if fl == F_EP else abs(st['squares'][0][m_to(mv)])
        attacker = abs(st['squares'][0][m_from(mv)])
        return 700000 + _VICTIM[victim] * 32 - _VICTIM[attacker]
    if killers[0, ply] == mv:
        return 400000
    if killers[1, ply] == mv:
        return 390000
    s = sq64(m_from(mv))
    t = sq64(m_to(mv))
    h = hist[1 if st['side'][0] == WHITE else 0, s, t]
    return h if h > 0 else 0


@njit
def _order_moves(st, moves, scores, cnt: int, ttmove: int, killers, hist,
                 ply: int):
    """Insertion sort moves[0..cnt) by descending score. `scores` is a
    caller-owned scratch row (per ply), reused -- no per-node alloc."""
    for i in range(cnt):
        scores[i] = _score_move(moves[i], st, ttmove, killers, hist, ply)
    for i in range(1, cnt):
        mv = moves[i]
        sc = scores[i]
        j = i - 1
        while j >= 0 and scores[j] < sc:
            moves[j + 1] = moves[j]
            scores[j + 1] = scores[j]
            j -= 1
        moves[j + 1] = mv
        scores[j + 1] = sc


# ---------------------------------------------------------------------------
# Quiescence
# ---------------------------------------------------------------------------

@njit
def qsearch(st, ply: int, alpha: int, beta: int, qdepth: int, nodes,
            deadline, scratch, sscratch, rep) -> int:
    """Quiescence: stand-pat + captures; full evasions when in check.
    No TT / killers / history. Fail-soft, returns side-to-move score."""
    nodes[0] += 1
    if (nodes[0] & 1023) == 0 and _NOW() >= deadline:
        return TIMEOUT
    if _draw_score(st, rep, ply):
        return 0

    check = in_check(st)

    if qdepth >= QCAP:
        # depth cap against quiescence explosions: evaluate statically;
        # if we are in check with no legal escape, it is mate.
        if check:
            if legal_moves(st, scratch[ply], False) == 0:
                return -MATE + ply
        return evaluate(st)

    if not check:
        stand = evaluate(st)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand

    cnt = legal_moves(st, scratch[ply], check == 0)   # all moves if in check
    if cnt == 0:
        return -MATE + ply if check else 0

    _order_moves(st, scratch[ply], sscratch[ply], cnt, 0, _KILLER_DUMMY,
                 _HIST_DUMMY, ply)

    best = -INF
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
        child = qsearch(st, ply + 1, -beta, -alpha, qdepth + 1, nodes,
                        deadline, scratch, sscratch, rep)
        if child == TIMEOUT:
            unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                        prev_key)
            return TIMEOUT
        score = -child
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                    prev_key)
        if score > best:
            best = score
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
    return best if best > -INF else alpha


# ---------------------------------------------------------------------------
# Main alpha-beta
# ---------------------------------------------------------------------------

@njit
def search(st, depth: int, alpha: int, beta: int, ply: int, nodes,
           deadline, ttk, ttv, mask, killers, hist, rep, scratch,
           sscratch) -> int:
    """Negamax alpha-beta (fail-soft) with PVS. `depth` is the remaining
    ply budget; depth<=0 hands off to quiescence."""
    if depth <= 0:
        return qsearch(st, ply, alpha, beta, 0, nodes, deadline, scratch,
                       sscratch, rep)

    nodes[0] += 1
    if (nodes[0] & 1023) == 0 and _NOW() >= deadline:
        return TIMEOUT
    if _draw_score(st, rep, ply):
        return 0

    check = in_check(st)
    if check:
        depth += 1                      # check extension

    key = st['key'][0]
    orig_alpha = alpha
    ttmove = 0

    hit, bound, ttscore, ttdepth, ttmove = tt_probe(ttk, ttv, mask, key, ply)
    if hit and ttdepth >= depth and bound != BOUND_NONE:
        if bound == BOUND_EXACT:
            return ttscore
        if bound == BOUND_LOWER and ttscore >= beta:
            return ttscore
        if bound == BOUND_UPPER and ttscore <= alpha:
            return ttscore

    # null-move pruning: skip in check, at the root, and in near-piece-less
    # endgames (zugzwang risk)
    if not check and depth >= 2 and ply >= 1 and _count_nonpawns(st) >= 2:
        stand = evaluate(st)
        if stand >= beta:
            prev_ep = st['ep'][0]
            prev_half = st['halfmove'][0]
            prev_key = st['key'][0]
            nkey = prev_key
            if prev_ep >= 0:
                nkey ^= _ZEP[prev_ep & 7]
            st['ep'][0] = -1
            st['halfmove'][0] = prev_half + 1
            st['side'][0] = 1 - st['side'][0]
            st['key'][0] = nkey ^ _ZSIDE
            child = search(st, depth - 1 - NULL_R, -beta, -beta + 1,
                           ply + 1, nodes, deadline, ttk, ttv, mask,
                           killers, hist, rep, scratch, sscratch)
            st['ep'][0] = prev_ep
            st['halfmove'][0] = prev_half
            st['key'][0] = prev_key
            st['side'][0] = 1 - st['side'][0]
            if child == TIMEOUT:
                return TIMEOUT
            if child >= beta:
                return child

    cnt = legal_moves(st, scratch[ply], False)
    if cnt == 0:
        return -MATE + ply if check else 0

    _order_moves(st, scratch[ply], sscratch[ply], cnt, ttmove, killers, hist, ply)

    best = -INF
    bestmove = 0
    me = st['side'][0]
    for i in range(cnt):
        mv = scratch[ply][i]
        quiet = _is_quiet(mv)
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

        if i == 0:
            child = search(st, depth - 1, -beta, -alpha, ply + 1, nodes,
                           deadline, ttk, ttv, mask, killers, hist, rep,
                           scratch, sscratch)
        else:
            if quiet and depth >= LMR_MIN_DEPTH and i >= 4:
                r = i // 4
                if r > LMR_MAX:
                    r = LMR_MAX
                child = search(st, depth - 1 - r, -alpha - 1, -alpha,
                               ply + 1, nodes, deadline, ttk, ttv, mask,
                               killers, hist, rep, scratch, sscratch)
            else:
                child = search(st, depth - 1, -alpha - 1, -alpha, ply + 1,
                               nodes, deadline, ttk, ttv, mask, killers,
                               hist, rep, scratch, sscratch)
            if child != TIMEOUT and child > alpha:
                child = search(st, depth - 1, -beta, -alpha, ply + 1, nodes,
                               deadline, ttk, ttv, mask, killers, hist, rep,
                               scratch, sscratch)

        if child == TIMEOUT:
            unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                        prev_key)
            return TIMEOUT
        score = -child
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                    prev_key)

        # history penalty for quiet moves that failed to raise alpha
        if quiet and score <= orig_alpha:
            s = sq64(m_from(mv))
            t = sq64(m_to(mv))
            c = 1 if me == WHITE else 0
            hist[c, s, t] -= depth * depth * 4
            if hist[c, s, t] < -30000:
                hist[c, s, t] = -30000

        if score > best:
            best = score
            bestmove = mv
            if score >= beta:
                if quiet:
                    s = sq64(m_from(mv))
                    t = sq64(m_to(mv))
                    c = 1 if me == WHITE else 0
                    hist[c, s, t] += depth * depth
                    if hist[c, s, t] > 30000:
                        hist[c, s, t] = 30000
                    killers[1, ply] = killers[0, ply]
                    killers[0, ply] = mv
                break
            if score > alpha:
                alpha = score

    # store only real scores (draw 0 is path-dependent -> skip)
    if best != TIMEOUT and best != 0:
        if best <= orig_alpha:
            bound = BOUND_UPPER
        elif best >= beta:
            bound = BOUND_LOWER
        else:
            bound = BOUND_EXACT
        tt_store(ttk, ttv, mask, key, ply, depth, bound, best, bestmove)
    return best


# ---------------------------------------------------------------------------
# Iterative deepening root
# ---------------------------------------------------------------------------

@njit
def search_root(st, nodes, deadline, ttk, ttv, mask, killers, hist, rep,
                scratch, sscratch, max_depth: int):
    """Iterative deepening at the root. Returns (bestmove, score,
    completed_depth); bestmove==0 => no legal move / call failed. On
    timeout the last completed iteration's move wins."""
    cnt = legal_moves(st, scratch[0], False)
    if cnt == 0:
        return 0, 0, 0
    if cnt == 1:
        return scratch[0][0], 0, 0

    rep[0] = st['key'][0]
    best_move = 0
    best_score = -INF
    completed = 0
    me = st['side'][0]

    for depth in range(1, max_depth + 1):
        if _NOW() >= deadline:
            break
        _order_moves(st, scratch[0], sscratch[0], cnt, 0, killers, hist, 0)
        alpha = -INF
        beta = INF
        iter_best = -INF
        iter_move = 0
        key = st['key'][0]
        hit, bound, ttscore, ttdepth, ttmove = tt_probe(ttk, ttv, mask,
                                                        key, 0)
        for i in range(cnt):
            mv = scratch[0][i]
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
            if i == 0:
                child = search(st, depth - 1, -beta, -alpha, 1, nodes,
                               deadline, ttk, ttv, mask, killers, hist, rep,
                               scratch, sscratch)
            else:
                child = search(st, depth - 1, -alpha - 1, -alpha, 1, nodes,
                               deadline, ttk, ttv, mask, killers, hist, rep,
                               scratch, sscratch)
                if child != TIMEOUT and child > alpha:
                    child = search(st, depth - 1, -beta, -alpha, 1, nodes,
                                   deadline, ttk, ttv, mask, killers, hist,
                                   rep, scratch, sscratch)
            unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                        prev_key)
            if child == TIMEOUT:
                iter_move = 0            # iteration incomplete -> discard
                break
            score = -child
            if score > iter_best:
                iter_best = score
                iter_move = mv
                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    break
        if iter_move == 0:
            break
        best_move = iter_move
        best_score = iter_best
        completed = depth
        if best_score >= MATE - 32 or best_score <= -MATE + 32:
            break                        # forced mate found: stop early
    return best_move, best_score, completed