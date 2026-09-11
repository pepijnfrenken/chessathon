#!/usr/bin/env python3
"""SF quick review of r106 (the win) — trajectory + our mistakes."""
import io
import pathlib

import chess
import chess.engine
import chess.pgn

SF = "/home/pino/.local/bin/stockfish"
MAT = pathlib.Path("/home/pino/projects/chessathon/results/matches")
PGN = MAT / "round-106-vs-claude-s-gambit.pgn"
OURS = "En Passant Labs"

eng = chess.engine.SimpleEngine.popen_uci(SF)
eng.configure({"Threads": 4, "Hash": 768})

game = chess.pgn.read_game(io.StringIO(PGN.read_text()))
board = game.board()
our = chess.WHITE if game.headers.get("White") == OURS else chess.BLACK
moves = list(game.mainline_moves())

evals = []
for i, mv in enumerate(moves):
    info = eng.analyse(board, chess.engine.Limit(depth=10))
    evals.append(info["score"].pov(our).score(mate_score=10000))
    board.push(mv)
info = eng.analyse(board, chess.engine.Limit(depth=10))
final = info["score"].pov(our).score(mate_score=10000)

n = len(moves)
peak = max(range(n + 1), key=lambda i: evals[i] if i < n else final)
print(f"=== r106 | {n} plies | ours {'White' if our else 'Black'} | final {final:+d} ===")
print("traj(every 4 plies):", " ".join(f"{evals[i]:+d}" for i in range(0, n, 4)) + f" {final:+d}")

# our big drops
drops = []
for i in range(1, n):
    mover_us = ((i - 1) % 2 == 0) == (our == chess.WHITE)
    if mover_us and evals[i] - evals[i - 1] <= -150:
        drops.append((i, evals[i] - evals[i - 1], evals[i - 1], evals[i]))
print(f"our drops <=-150: {len(drops)}")
for i, d, a, b in drops[:8]:
    print(f"  after ply {i}: {a:+d} -> {b:+d} ({d:+d})")

never_worse_than = min(evals + [final]) if final else min(evals)
print(f"min eval along game: {never_worse_than:+d}; max: {max(evals + [final]):+d}")
eng.quit()
print("R106-REVIEW-DONE")
