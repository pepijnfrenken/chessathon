#!/usr/bin/env python
"""P7 regression probe: EP-capture zobrist key parity (repo-local).

Pre-fix (audit 2-A, F1, 2026-09-08): make_move_apply XORed a phantom
ZPIECE[to] removal on EN-PASSANT captures (captured pawn was already
removed at its real square), so the search key diverged from the
parse_fen truth after any EP capture — breaking the stateful
anti-threefold's game-history pre-seed and TT keying on post-EP trees.

This probe FAILS on the unfixed tree and PASSES on the fixed tree.

Run: /tmp/chessbench/bin/python tools/probe_ep_key.py   (repo root)
Exit 0 = parity holds everywhere.  NUMBA_CACHE_DIR is isolated+fresh so
the fix is actually compiled in (never reuse a cache seeded by old code).
"""
import os
import sys
import time

os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache_epkey2'
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.stdout.reconfigure(line_buffering=True)

import chess
from engine import board as B

T0 = time.perf_counter()
print('[probe_ep_key] numba warmup...', flush=True)


def make_ep_game(moves, ep_sq, uci, tag):
    """Push `moves` from startpos, set the ep square by hand, then push
    the EP capture. Returns (tag, pre_fen, ep_uci, post_fen)."""
    b = chess.Board()
    for m in moves:
        b.push(chess.Move.from_uci(m))
    parts = b.fen().split()
    parts[3] = ep_sq          # force the ep-available square
    pre = ' '.join(parts)
    b = chess.Board(pre)
    assert chess.Move.from_uci(uci) in b.legal_moves, (tag, pre, uci)
    b.push(chess.Move.from_uci(uci))
    return tag, pre, uci, b.fen()


def engine_key_after(st, mv):
    """key(st) after make_move_apply(mv), restored by unmake."""
    captured = st['squares'][0][B.m_to(mv)]
    me = st['side'][0]
    if B.m_flags(mv) == B.F_EP:
        captured = st['squares'][0][B.m_to(mv) - 16 if me == B.WHITE
                                    else B.m_to(mv) + 16]
    saved = (st['castle'][0], st['ep'][0], st['halfmove'][0], st['key'][0])
    B.make_move_apply(st, mv)
    key = int(st['key'][0])
    B.unmake_move(st, mv, captured, *saved)
    return key


def int_of_uci(st, uci):
    moves = __import__('numpy').zeros(B.MAX_MOVES, dtype='int32')
    cnt = B.legal_moves(st, moves, False)
    for i in range(cnt):
        if B.move_to_uci(moves[i]) == uci:
            return moves[i]
    raise AssertionError(f'move {uci} not generated from state')


GAMES = [
    # tag,        moves-to-EP-pos,      ep_sq,  ep capture,  note
    # real games: waiting move keeps the double-push EP window alive
    ('white-EP-classic',  ['e2e4', 'a7a6', 'e4e5', 'd7d5'], 'd6', 'e5d6',
     '1.e4 a6 2.e5 d5 3.exd6 e.p.'),
    ('black-EP-classic',  ['d2d4', 'h7h6', 'd4d5', 'e7e5'], 'e6', 'd5e6',
     '1.d4 h6 2.d5 e5 3.dxe6 e.p.'),
    ('white-EP-queenside',['c2c4', 'b7b5', 'c4c5', 'd7d5'], 'd6', 'c5d6',
     'queenside white EP'),
    ('black-EP-queenside',['b2b4', 'h7h6', 'b4b5', 'a7a5'], 'a6', 'b5a6',
     'queenside black EP'),
]
# sanity: double-push EP pairs (non-EP captures, promos) as control
CONTROL = [
    ('plain-capture', ['e2e4', 'd7d5', 'e4d5'], None, None),
    ('knight-take',   ['g1f3', 'g8f6', 'f3e5', 'd7d6', 'e5f7'], None, None),
]

failures = 0
for tag, moves, ep_sq, ep_uci, note in GAMES:
    t, pre, uci, post = make_ep_game(moves, ep_sq, ep_uci, tag)
    st = B.parse_fen(pre)
    mv = int_of_uci(st, uci)
    eng = engine_key_after(st, mv)
    truth = int(B.parse_fen(post)['key'][0])
    ok = eng == truth
    print(f'{"PASS" if ok else "FAIL"}  {t:<22} {note}')
    if not ok:
        print(f'     engine={eng:#x} truth={truth:#x} (post={post})')
        failures += 1

# control: engine key must match parse_fen truth for every legal move of a
# real middlegame position (catches collateral damage from the fix)
b = chess.Board('r1bq1rk1/pppnbpp1/4pn1p/3p4/2PP3B/2N1PN2/PP3PPP/R2QKB1R w KQ - 2 8')
st = B.parse_fen(b.fen())
moves = __import__('numpy').zeros(B.MAX_MOVES, dtype='int32')
cnt = B.legal_moves(st, moves, False)
for i in range(cnt):
    mv = moves[i]
    eng = engine_key_after(st, mv)
    bb = chess.Board(b.fen())
    bb.push(chess.Move.from_uci(B.move_to_uci(mv)))
    truth = int(B.parse_fen(bb.fen())['key'][0])
    if eng != truth:
        print(f'FAIL  control move {B.move_to_uci(mv)}: {eng:#x} != {truth:#x}')
        failures += 1
print(f'[control] {cnt} legal moves of r61 start FEN: parity '
      + ('OK' if failures == 0 else f'{failures} FAILURES'))

print(f'[probe_ep_key] done in {time.perf_counter()-T0:.1f}s '
      f'({len(GAMES)} EP cases + {cnt}-move control sweep)')
sys.exit(1 if failures else 0)
