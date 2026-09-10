import os, sys, time, json
from pathlib import Path
sys.path.insert(0, '/tmp/chessathon-aud6')
sys.path.insert(0, '/tmp/chessathon-aud6/tools')
import numpy as np
import chess
from engine import board as B, search as S, eval as E, tt as TT, time as TM
import agent as A

def emit(name, **v):
    print(json.dumps(dict(probe=name, **v), default=int), flush=True)

def clear():
    A._TT_KEYS.fill(0); A._TT_VALS.fill(0); A._REP.fill(0)
    A._KILLERS.fill(0); A._HIST.fill(0); A._NODES.fill(0); A.reset_game()

def search(fen, depth=2, ply=1):
    A._NODES.fill(0)
    return int(S.search(B.parse_fen(fen), depth, -S.INF, S.INF, ply, A._NODES,
        S._NOW()+10_000_000_000, A._TT_KEYS, A._TT_VALS, A._TT_MASK,
        A._KILLERS, A._HIST, A._REP, A._SCRATCH, A._SSCRATCH))

def qs(fen, ply=1, qdepth=0):
    A._NODES.fill(0)
    return int(S.qsearch(B.parse_fen(fen), ply, -S.INF, S.INF, qdepth, A._NODES,
        S._NOW()+10_000_000_000, A._SCRATCH, A._SSCRATCH, A._REP))

# ---------- F2: king-color zobrist alias ----------
f1 = '7k/8/8/8/8/8/8/K7 w - - 0 1'
f2 = '7K/8/8/8/8/8/8/k7 w - - 0 1'
k1 = int(B.parse_fen(f1)['key'][0]); k2 = int(B.parse_fen(f2)['key'][0])
emit('f2_king_alias', f1=f1, f2=f2, key1=k1, key2=k2, keys_equal=k1 == k2,
     valid=[chess.Board(f).is_valid() for f in (f1, f2)])

# generalized: white K vs black k at same square, mirrored placements
alias_rows = []
for sq in ['a1','d4','h8','e2']:
    a = f'7k/8/8/8/8/8/8/{sq.upper() if 0 else "K"} w - - 0 1'
    # construct: white K on sq, black k on some other square vs swap chars
    pass
emit('warmup_done', seconds=A._WARMUP_S, max_ply=B.MAX_PLY)

# ---------- F3: pinned-EP repetition identity ----------
cb = chess.Board('3k4/8/8/8/3p4/8/4P3/K2R4 w - - 0 1')
st = B.parse_fen(cb.fen())
start_key = int(st['key'][0])
keys_seq = [start_key]
ep_seq = []
mvbuf = np.zeros(B.MAX_MOVES, dtype=np.int32)
for uci in ['e2e4', 'd8e8', 'a1b1', 'e8d8', 'b1a1']:
    pm = chess.Move.from_uci(uci)
    assert pm in cb.legal_moves, uci
    cb.push(pm)
    n = B.legal_moves(st, mvbuf, False)
    tgt = None
    for i in range(n):
        if B.move_to_uci(int(mvbuf[i])) == uci:
            tgt = int(mvbuf[i]); break
    assert tgt is not None, uci
    B.make_move_apply(st, tgt)
    keys_seq.append(int(st['key'][0]))
    ep_seq.append(int(st['ep'][0]))
emit('f3_pinned_ep', oracle_repeat2=cb.is_repetition(2),
     engine_repeat2=(int(st['key'][0]) == start_key),
     start_key=start_key, final_key=int(st['key'][0]),
     mid_key_after_e2e4=keys_seq[1], ep_after_each_move=ep_seq,
     python_chess_ep_after_e2e4=None,
     engine_fen=B.to_fen(st), oracle_fen=cb.fen())

# ---------- F3b: EP-in-FEN but no legal EP capture: does key change? ----------
ep_rows = []
for fen_noep, fen_ep, note in [
    ('4k3/8/8/8/8/8/8/4K3 w - - 0 1', '4k3/8/8/8/8/8/8/4K3 w - e6 0 1', 'no pawns at all'),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - - 0 1', '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'legal ep exists'),
    ('4k3/8/8/8/4p3/8/8/4K3 w - - 0 1', '4k3/8/8/8/4p3/8/8/4K3 w - e6 0 1', 'black pawn e4, no white capturer'),
    ('4k3/8/8/8/4P3/8/8/4K3 b - - 0 1', '4k3/8/8/8/4P3/8/8/4K3 b - e3 0 1', 'black to move, ep e3, no black pawn'),
]:
    b_no = chess.Board(fen_noep); b_ep = chess.Board(fen_ep)
    ka = int(B.parse_fen(fen_noep)['key'][0]); kb = int(B.parse_fen(fen_ep)['key'][0])
    ep_rows.append(dict(note=note, key_noep=ka, key_ep=kb, same=ka == kb,
                        py_legal_ep=b_ep.has_legal_en_passant(),
                        py_fen_normalized=b_ep.fen(),
                        engine_to_fen=B.to_fen(B.parse_fen(fen_ep))))
emit('f3b_ep_key', rows=ep_rows)

# ---------- F4: TT ignores halfmove ----------
f0 = '7k/8/8/8/8/8/8/KR6 w - - 0 1'; f99 = f0.replace('0 1', '99 1')
clear(); cold99 = search(f99)
clear(); zero = search(f0)
clear(); warm99 = search(f99)
emit('f4_tt_halfmove', fen99=f99, cold=cold99, halfmove0_same_placement=zero,
     warm=warm99, same_key=int(B.parse_fen(f0)['key'][0]) == int(B.parse_fen(f99)['key'][0]))

# ---------- mate score packing roundtrip ----------
for score in [123, -456, 29990, -29990, 31999, -31999]:
    keys, vals = TT.make(1024); mask = np.uint64(1023); key = np.uint64(123456)
    TT.tt_store(keys, vals, mask, key, 7, 9, TT.BOUND_EXACT, score, 123)
    emit('tt_mate_roundtrip', stored=score, at7=TT.tt_probe(keys, vals, mask, key, 7),
         at3=TT.tt_probe(keys, vals, mask, key, 3))

# ---------- boundaries ----------
mate = '7k/6Q1/5K2/8/8/8/8/8 b - - 100 1'
clear(); emit('b_mate_fifty', fen=mate, oracle_checkmate=chess.Board(mate).is_checkmate(),
              search=search(mate), qsearch=qs(mate), expected=-S.MATE + 1)
stale = '7k/5K2/6Q1/8/8/8/8/8 b - - 0 1'
clear(); emit('b_stalemate', fen=stale, oracle_stalemate=chess.Board(stale).is_stalemate(),
              search=search(stale), qsearch=qs(stale), expected=0)
clear()
try:
    r = qs(f0, B.MAX_PLY)
    emit('b_ply_boundary', result=r)
except Exception as e:
    emit('b_ply_boundary', error=repr(e), ply=B.MAX_PLY)

# fifty-move at halfmove 99 vs 100 for a quiet winning position
for hm in [0, 98, 99, 100, 101]:
    clear(); emit('b_fifty_budget', halfmove=hm, score=search(f0.replace('0 1', f'{hm} 1')))

# ---------- budget model ----------
for rem in [0, 1, 20, 49, 50, 100, 149, 500, 1940, 30000, 65000, 120000, 1000]:
    emit('budget', remaining=rem, budget=TM.budget_ms(rem))

# ---------- stalemate / draw logic ----------
emit('done')
