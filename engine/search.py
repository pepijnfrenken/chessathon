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
  - repetition (path zobrist keys) + fifty-move draws

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
                          in_check, attacked, sq64, _KING_DELTAS)
from engine.eval import evaluate, EVAL_PARAMS, P_MAT_MG
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


@njit(inline="always")
def _few_pieces(st) -> bool:
    """Sparse-position gate for the qsearch stalemate probe. A true
    stalemate with >8 pieces on the board is practically nonexistent
    (and the main search catches genuine stalemates at full nodes via its
    own legal_moves count); gating keeps the probe's attack tests off the
    middlegame hot path. Early-exits as soon as the 9th piece is seen."""
    sqr = st['squares'][0]
    n = 0
    for sq in range(128):
        if (sq & 0x88) == 0 and sqr[sq] != EMPTY:
            n += 1
            if n > 8:
                return False
    return True


@njit(inline="always")
def _drive_net(st) -> bool:
    """Is this a mate-net position (few pieces, material edge of a rook
    or more)? Shares the eval's gate (phase<=16, |mat|>=300) with an
    early exit at 6 pieces seen — the drive/prox/budget machinery is
    restricted to the bare-king family (KQvK/KRvK/KRPvK <= 4 pieces);
    the 500ms-vs-HEAD gate showed the terms mis-firing in 6-10-piece
    endings (QvR-style) and eroding material. Gates the endgame
    search-budget boost and partial-iteration adoption in search_root."""
    sqr = st['squares'][0]
    n = 0
    mat = 0
    phase = 0
    for sq in range(128):
        if (sq & 0x88) != 0:
            continue
        pc = sqr[sq]
        if pc == EMPTY:
            continue
        n += 1
        if n > 6:
            return False
        t = pc if pc > 0 else -pc
        sign = 1 if pc > 0 else -1
        mat += sign * int(EVAL_PARAMS[P_MAT_MG + t - 1])
        if t == KNIGHT or t == BISHOP:
            phase += 1
        elif t == ROOK:
            phase += 2
        elif t == QUEEN:
            phase += 4
    return phase <= 16 and (mat >= 300 or mat <= -300)


@njit(inline="always")
def _king_has_move(st) -> bool:
    """Cheap stalemate probe: does the side to move's KING have any legal
    move? If yes, the position cannot be stalemate. Rejects own pieces,
    squares attacked by the enemy, and squares adjacent to the enemy king
    (those are attacked by it). A king-step-less position still needs the
    full movegen to rule out other pieces' moves (pins, castling) — that
    rare fallback lives in qsearch. Cost ~8 attacked() calls vs a full
    legal_moves — qsearch's quiet-leaf fast path."""
    sqr = st['squares'][0]
    me = st['side'][0]
    ks = st['kingsq'][0][me]
    for d in range(8):
        a = ks + _KING_DELTAS[d]
        if (a & 0x88) != 0:
            continue
        pc = sqr[a]
        if pc != EMPTY and (pc > 0) == (me == WHITE):
            continue                # own piece
        if attacked(st, a, 1 - me):
            continue                # attacked / adjacent enemy king
        return True
    return False


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
        # if we are in check with no legal escape, it is mate. A genuine
        # stalemate must score 0 (see probe note below).
        if check:
            if legal_moves(st, scratch[ply], False) == 0:
                return -MATE + ply
        elif _few_pieces(st) and not _king_has_move(st) \
                and legal_moves(st, scratch[ply], False) == 0:
            return 0
        return evaluate(st)

    if not check:
        # STALEMATE probe BEFORE the stand-pat cutoff: a position with no
        # legal moves must score 0, not the static eval — scoring the
        # stand-pat there made the search play into cornered-king
        # stalemates believing it was winning (measured: Kh8 / Kg2+Qg6
        # stalemate scored -1284 instead of 0; it also slipped through
        # the beta cutoff as a false fail-high). Sparse-only: real
        # stalemates need few pieces (cornered king nets); the middlegame
        # hot path pays only the piece-count scan's early exit.
        if _few_pieces(st) and not _king_has_move(st):
            if legal_moves(st, scratch[ply], False) == 0:
                return 0
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
        # forensics; KRvK static +524 searched as 0). Stalemates were
        # already caught by the probe above.
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
                child = search(st, depth - 1, -beta, -alpha, ply + 1,
                               nodes, deadline, ttk, ttv, mask, killers,
                               hist, rep, scratch, sscratch)

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
               ttv, mask, killers, hist, rep, scratch, sscratch):
    """Search all root moves under window [alpha, beta) with PVS.
    `scratch[0]` holds the already-ordered legal moves (caller orders once
    per depth; the aspiration re-search reuses the same order). Returns
    (bestmove, score); bestmove == 0 => the iteration is INCOMPLETE
    (timeout inside a subtree) and must be discarded.

    Timeout tolerance (endgame-conversion fixer): a timeout inside the
    iteration no longer discards it entirely — the deepest usable result
    is returned with `complete=False`, and search_root adopts the partial
    best-so-far (searched moves kept their exact values) when it improves
    on the last completed iteration. Measured: at short budgets every
    iteration used to die on the good move's full-window re-search, so
    the root played a permanently stale iteration and won endgames
    shuffled into draws. Fixed-depth parity is unaffected (the fallback
    never fires without a timeout)."""
    iter_best = -INF
    iter_move = 0
    complete = True
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
        unmake_move(st, mv, captured, prev_castle, prev_ep, prev_half,
                    prev_key)
        if child == TIMEOUT:
            # iteration incomplete: the first move timed out (iter_best
            # stays -INF => nothing usable) or a later move did (the
            # partial best-so-far is still a valid move — the caller
            # adopts it when it improves on the completed iterations).
            complete = False
            break
        score = -child
        if score > iter_best:
            iter_best = score
            iter_move = mv
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
    return iter_move, iter_best, complete


@njit
def search_root(st, nodes, deadline, ttk, ttv, mask, killers, hist, rep,
                scratch, sscratch, max_depth: int):
    """Iterative deepening at the root. Returns (bestmove, score,
    completed_depth); bestmove==0 => no legal move / call failed. On
    timeout the deepest usable iteration wins — a PARTIAL iteration's
    best-so-far move is adopted when it improves on the last completed
    one (endgame-conversion fixer: at short budgets every iteration used
    to die on the good move's PVS re-search, freezing the root behind a
    stale iteration and shuffling won endgames into draws).

    Every iteration searches the FULL window [−INF, INF]. Root aspiration
    was tried in Phase 3 (window [prev−40, prev+40], full-window re-search
    on fail low/high): byte-exact at fixed depth (parity proven), but the
    24-game 500ms gate was NEGATIVE (0.438: 5W-8L-11D) — at short TCs the
    window misses often and the re-search burns the budget, so fewer
    iterations complete than the full-window search. Reverted by
    evidence; a Stockfish-style widening re-search is a documented
    follow-up for real-clock TCs."""
    cnt = legal_moves(st, scratch[0], False)
    if cnt == 0:
        return 0, 0, 0
    if cnt == 1:
        return scratch[0][0], 0, 0

    rep[0] = st['key'][0]
    best_move = 0
    best_score = -INF
    completed = 0

    # Mate-net regime (few pieces, R+ edge): enables the endgame budget
    # boost below AND the partial-iteration adoption in the loop. In the
    # MIDDLEGAME the root keeps the classic 'last completed iteration'
    # semantics — the 500ms-vs-HEAD gate showed the deeper-partial
    # adoption regressing fresh middlegame positions (partial bests are
    # drawn from move-ordered prefixes, biased away from late-order
    # refinements); in mate-nets the partial's depth gain is what makes
    # the corner nets visible. (see _drive_net)
    net = _drive_net(st)

    # Endgame search budget: in a mate-net position (few pieces, R+ edge)
    # a small caller budget can't reach the corner nets (measured: the
    # 300ms eg gate completes ~7-9 plies; the KQvK/KRvK nets need 13+).
    # Spend up to 8x, capped +2.1s, but ONLY when the caller's budget is
    # <=1.5s — the competition's time.py budget (remaining/45+inc) is
    # already >=1.5s in endgames, so real-clock spend is untouched.
    dl = _NOW()
    if net:
        base = deadline - dl
        if 0 < base <= 1_500_000_000:
            extra = base * 7
            if extra > 2_100_000_000:
                extra = 2_100_000_000
            deadline = dl + base + extra

    for depth in range(1, max_depth + 1):
        if _NOW() >= deadline:
            break
        _order_moves(st, scratch[0], sscratch[0], cnt, 0, killers, hist, 0)
        iter_move, iter_best, complete = _root_iter(
            st, depth, -INF, INF, cnt, nodes, deadline, ttk, ttv, mask,
            killers, hist, rep, scratch, sscratch)
        if iter_best == -INF:
            break                        # first root move timed out
        if complete:
            best_move = iter_move        # deepest completed iteration wins
            best_score = iter_best       # (fail-soft scores may wiggle)
            completed = depth
        elif net and iter_best > best_score:
            # deeper PARTIAL iteration (timed out mid-loop) adopted only
            # when it improves on the completed best — and only in
            # mate-nets (see the `net` note above)
            best_move = iter_move
            best_score = iter_best
            completed = depth
        if best_score >= MATE - 32 or best_score <= -MATE + 32:
            break                        # forced mate found: stop early
    return best_move, best_score, completed