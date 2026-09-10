#!/usr/bin/env python3
"""SF review of r105 (loss vs Zero Elo): trajectory, our drops, key moments.

Also extracts per-move clock from PGN for correlation with mistakes."""
import io
import pathlib
import re
import sys

import chess
import chess.engine
import chess.pgn

SF = "/home/pino/.local/bin/stockfish"
MAT = pathlib.Path("/home/pino/projects/chessathon/results/matches")
PGN = MAT / "round-105-vs-zero-elo.pgn"
OURS = "En Passant Labs"
D_SWEEP = 10
D_CHECK = 16

eng = chess.engine.SimpleEngine.popen_uci(SF)
eng.configure({"Threads": 4, "Hash": 768})


def ev(b):
    return eng.analyse(b, chess.engine.Limit(depth=D_SWEEP))["score"].pov(our).score(mate_score=10000)


txt = PGN.read_text()
game = chess.pgn.read_game(io.StringIO(txt))
board = game.board()
our = chess.WHITE if game.headers.get("White") == OURS else chess.BLACK
moves = list(game.mainline_moves())

# per-ply clock (seconds) from %clk annotations, both sides
clks = [float(x) for x in re.findall(r"\[%clk (\d+):(\d+):([\d.]+)\]", txt) and
        [float(a) * 60 + float(b) for a, b in re.findall(r"\[%clk (\d+):(\d+):", txt)]]

evals = []  # (ply, cp pov us, our clock after our move)
for i, mv in enumerate(moves):
    e = ev(board)
    evals.append((i, e))
    board.push(mv)
evals.append((len(moves), ev(board)))

print(f"=== r105 SF review | {len(moves)} plies | ours {'White' if our else 'Black'} ===")
print("ply  eval(us)   mover")
for i, (ply, e) in enumerate(evals):
    mover = "US" if (i % 2 == 0) == (our == chess.WHITE) else "op"
    flag = ""
    if mover == "US" and i > 0:
        d = evals[i][1] - evals[i - 1][1]
        if d <= -150:
            flag = f"  <<< drop {d:+d}"
    print(f"{ply:>4} {e:>+7}   {mover}{flag}")

peak = max(evals, key=lambda x: x[1])
trough = min(evals, key=lambda x: x[1])
print(f"\npeak for us: {peak[1]:+d} at ply {peak[0]}; trough: {trough[1]:+d} at ply {trough[0]}")
print(f"final eval: {evals[-1][1]:+d}")

# deep-check on turning points: find biggest sustained drop
drops = []
for i in range(1, len(evals)):
    if evals[i][0] % 2 == (0 if our == chess.WHITE else 1) and evals[i][1] <= -130 and evals[i-1][1] > -130:
        drops.append(i)
print("\nentry points into <=-1.3:")
for i in drops[:5]:
    b = game.board()
    for mv in moves[:i]:
        b.push(mv)
    print(f"  ply{i} first-fall: d10 {evals[i][1]:+d} -> d16 {eng.analyse(b, chess.engine.Limit(depth=D_CHECK))['score'].pov(our).score(mate_score=10000):+d}  (FEN {b.fen()})")
    sys.stdout.flush()

# our worst single moves (loss > 150)
worst = []
for i in range(1, len(evals)):
    mover_us = (i % 2 == 0) == (our == chess.WHITE) if False else None
for i in range(1, len(evals) - 1):
    # position evals[i-1] is before move i-1... we stored evals[i] AFTER push i-1? 
    pass

eng.quit()
print("R105-REVIEW-DONE")
