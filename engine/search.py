"""Chessathon engine Phase 1b/3 — search core (numba-jitted).

Iterative-deepening negamax alpha-beta with:
  - principal variation search (zero-window sibling re-search)
  - transposition table (engine.tt; TT move ordering + score cutoffs)
  - MVV-LVA capture ordering + 2 killers/ply + quiet history
  - quiescence search (stand-pat + captures; full evasions in check;
    QCAP depth cap)
  - null-move pruning (R=2, eval >= beta, endgame zugzwang guard;
    beta > 0 only)
  - late move reductions (quiet moves, depth >= 3, cap 2)
  - check extension (+1 ply)
  - repetition (path zobrist keys) + fifty-move draws. Phase 4: the
    caller pre-seeds rep[0..GAME_HIST) with the REAL game's position
    keys (see search_root), so repetitions across moves in the game are
    seen by the search (the agent was stateless before; ladder r54/r55
    threefold-shuffled won endgames because every move looked fresh).
    The root additionally refuses moves that would create a THIRD
    occurrence of a game position and penalizes second occurrences when
    a non-repeating alternative exists (anti-shuffle; never weakens
    defense: a losing side still repeats into the draw).

Time: aborted from INSIDE the recursion via a monotonic clock (ctypes
CFUNCTYPE callback — numba has no time_ns) checked against a deadline
every 1024 nodes; a TIMEOUT sentinel propagates to the root, which keeps
the last completed iteration's best move. Every root iteration searches
the full window (root aspiration was tried in Phase 3 and REVERTED after
a negative 500ms gate — see search_root doc).

Scores: centipawns from the side to move; MATE at +-30000 with
mate-distance (checkmate = -MATE + ply); TT stores MATE-ply adjusted.
Sentinels: TIMEOUT = 1e9 (never stored, never compared as a score).

Search feature toggles (read at import — numba bakes globals at compile;
each A/B side runs as its own process):
  CHESSATHON_LMR  = 0 disables late move reduction (default: on)
"""

import ctypes
import os
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
MAX_ROOT_DEPTH = 64

# Phase 4 — game-history / anti-shuffle constants. The agent used to be
# STATELESS: get_move parsed the FEN fresh every call, so the search's
# repetition detector (rep[] path keys) could only see the CURRENT
# search's path — positions that recurred in the REAL game (2-20 plies
# ago) looked fresh, quiet moves scored equal, and the engine shuffled a
# rook/queen in loops until the harness declared a threefold draw
# (ladder rounds 54/55; reproduced: KQvK/KRvK-w threefold at 2 s/move).
#
#   GAME_HIST      rolling window of game position keys kept in rep[]
#                  BEFORE the search path: rep[i] for i in
#                  [GAME_HIST-1, ...] = the positions 1, 2, ... plies
#                  before the root (chronological). The search path then
#                  occupies rep[GAME_HIST + ply]. _draw_score's step-2
#                  parity scan therefore sees REAL-game repetitions and
#                  alpha-beta naturally avoids shuffling into a draw.
#   REP_LOOKBACK   plies scanned for repeats: the full history window
#                  plus 16 plies of the live search path.
#   REPEAT_PENALTY root-level cp penalty on a move that would create a
#                  SECOND occurrence of a game position (one that would
#                  create the THIRD — the actual draw — is scored 0).
#                  Both apply only when the side is not losing, so
#                  defense is never weakened (a losing side keeps the
#                  right to repeat into a draw).
GAME_HIST = 32
REP_LOOKBACK = GAME_HIST + 16
REPEAT_PENALTY = 20
REP_SIZE = MAX_PLY + GAME_HIST + 8

# LMR toggle (Phase 3 A/B infra; default on = the 1b behavior). Used to
# gate LMR itself.
LMR_ON = os.environ.get("CHESSATHON_LMR", "1") != "0"

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
    """Fifty-move and repetition draws. Records rep[GAME_HIST + ply] =
    key and returns True if the position repeats a game position or an
    earlier position on the search path (Phase 4: rep[0..GAME_HIST) is
    pre-seeded with the REAL game's position keys — see search_root —
    so repetitions ACROSS moves in the game are visible to the search
    instead of looking fresh every get_move). The step-2 scan keeps the
    side-to-move parity (matching keys carry their own side)."""
    if st['halfmove'][0] >= 100:
        return True
    key = st['key'][0]
    g = GAME_HIST + ply
    rep[g] = key
    lo = g - REP_LOOKBACK
    if lo < 0:
        lo = 0
    p = g - 2
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
        # No captures (or no evasions in check). In check this is mate.
        # Otherwise the value is the stand-pat eval we just computed —
        # returning 0 here (the 1b behavior) scored EVERY quiet leaf as a
        # draw, deafening the horizon to the static eval and causing the
        # won-endgame shuffling (Phase 3: found via aspiration-parity
        # forensics; KRvK static +524 searched as 0).
        if check:
            return -MATE + ply
        return stand

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
    # Fail-soft end: the value is max(stand-pat, best capture). `alpha`
    # already carries max(caller alpha, stand, every raised move score);
    # the naive `return best` would DROP stand-pat when every capture is
    # worse than standing pat, returning a FALSE low bound that parents
    # negate into a false fail-high (Phase 3: found via aspiration-parity
    # forensics — a depth-1 node claimed +1231 in an even position).
    if best < alpha:
        best = alpha
    return best


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
    # endgames (zugzwang risk). The `beta > 0` guard keeps this in the
    # positive-beta regime where the cutoff is meaningful: with the Phase 3
    # aspiration windows, child nodes can carry NEGATIVE beta (e.g. a root
    # child searched with [-beta_root, -alpha_root]), where `stand >= beta`
    # is trivially true and the null cutoff would return a corrupted value.
    # (Full-window searches have beta=INF, so this guard never changed that
    # shipped behavior; null-move was effectively dead code there.)
    if (not check and depth >= 2 and ply >= 1
            and beta > 0 and _count_nonpawns(st) >= 2):
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
            if quiet and depth >= LMR_MIN_DEPTH and i >= 4 and LMR_ON:
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
            if child != TIMEOUT and -child > alpha:
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
    bound = BOUND_NONE
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
def _root_iter(st, depth: int, alpha, beta, cnt: int, nodes, deadline, ttk,
               ttv, mask, killers, hist, rep, scratch, sscratch, ghist,
               gcnt: int):
    """Search all root moves under window [alpha, beta) with PVS.
    `scratch[0]` holds the already-ordered legal moves (caller orders once
    per depth; the aspiration re-search reuses the same order). Returns
    (bestmove, effective_score); bestmove == 0 => the iteration is
    INCOMPLETE (timeout inside a subtree) and must be discarded.

    Phase 4 anti-shuffle (STATELESS-AGENT fix): every root move's
    resulting position key is counted against the game-history window
    (ghist[0..gcnt), positions before the root). A move creating the
    THIRD occurrence of a game position instantly draws the game — its
    effective score is forced to 0 regardless of the search result. A
    move creating the SECOND occurrence gets a small penalty when the
    side is not already losing (score >= 0), so the search prefers a
    non-repeating progress move over re-treading a shuffle; a LOSING
    side keeps the repetition (it is the correct way to hold a draw).
    Selection and alpha use the effective score only."""
    iter_best = -INF
    iter_move = 0
    me = st['side'][0]
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
            if child != TIMEOUT and -child > alpha:
                child = search(st, depth - 1, -beta, -alpha, 1, nodes,
                               deadline, ttk, ttv, mask, killers, hist,
                               rep, scratch, sscratch)
        # game-repetition count for the resulting position (st already
        # holds it; ghist holds the positions before the root)
        gcnt_occ = 0
        if child != TIMEOUT:
            pos_key = st['key'][0]
            for k in range(gcnt):
                if ghist[k] == pos_key:
                    gcnt_occ += 1
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                    prev_key)
        if child == TIMEOUT:
            iter_move = 0            # iteration incomplete -> discard
            break
        score = -child
        eff = score
        if gcnt_occ >= 2:
            eff = 0                  # 3rd occurrence: the game draws now
        elif gcnt_occ == 1 and score >= 0:
            eff = score - REPEAT_PENALTY
        if eff > iter_best:
            iter_best = eff
            iter_move = mv
            if eff > alpha:
                alpha = eff
            if alpha >= beta:
                break
    return iter_move, iter_best


@njit
def search_root(st, nodes, deadline, ttk, ttv, mask, killers, hist, rep,
                scratch, sscratch, max_depth: int, ghist, gcnt: int):
    """Iterative deepening at the root. Returns (bestmove, score,
    completed_depth); bestmove==0 => no legal move / call failed. On
    timeout the last completed iteration's move wins.

    Every iteration searches the FULL window [−INF, INF]. Root aspiration
    was tried in Phase 3 (window [prev−40, prev+40], full-window re-search
    on fail low/high): byte-exact at fixed depth (parity proven), but the
    24-game 500ms gate was NEGATIVE (0.438: 5W-8L-11D) — at short TCs the
    window misses often and the re-search burns the budget, so fewer
    iterations complete than the full-window search. Reverted by
    evidence; a Stockfish-style widening re-search is a documented
    follow-up for real-clock TCs.

    Phase 4 — game history pre-seed: ghist[0..gcnt) holds the REAL game's
    position keys in chronological order, ending with the position 1 ply
    before the root. They are mapped into rep[0..GAME_HIST) so _draw_score's
    parity scan sees cross-move game repetitions (the stateless-agent
    fix); the root's own key sits at rep[GAME_HIST]. With gcnt == 0 the
    search is byte-identical to the Phase-3 behavior."""
    cnt = legal_moves(st, scratch[0], False)
    if cnt == 0:
        return 0, 0, 0
    if cnt == 1:
        return scratch[0][0], 0, 0

    # pre-seed: newest pre-root position at rep[GAME_HIST-1], older
    # before it (chronological), rest zero-padded.
    for i in range(gcnt):
        rep[GAME_HIST - gcnt + i] = ghist[i]
    rep[GAME_HIST] = st['key'][0]
    best_move = 0
    best_score = -INF
    completed = 0

    for depth in range(1, max_depth + 1):
        if _NOW() >= deadline:
            break
        _order_moves(st, scratch[0], sscratch[0], cnt, 0, killers, hist, 0)
        iter_move, iter_best = _root_iter(st, depth, -INF, INF, cnt, nodes,
                                          deadline, ttk, ttv, mask, killers,
                                          hist, rep, scratch, sscratch,
                                          ghist, gcnt)
        if iter_move == 0:
            break                        # timed out mid-iteration
        best_move = iter_move
        best_score = iter_best
        completed = depth
        if best_score >= MATE - 32 or best_score <= -MATE + 32:
            break                        # forced mate found: stop early
    return best_move, best_score, completed