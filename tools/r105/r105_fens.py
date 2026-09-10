#!/usr/bin/env python3
"""Extract the exact pre-move FENs for r105 critical moves (both colors)."""
import io

import chess.pgn

PGN = "/home/pino/projects/chessathon/results/matches/round-105-vs-zero-elo.pgn"
game = chess.pgn.read_game(io.StringIO(open(PGN).read()))
board = game.board()
moves = list(game.mainline_moves())

WANT = {33: "Rc7", 41: "Bxf2+", 42: "Qxh3", 46: "g6", 47: "Qe5", 70: "Qf4"}
n = 0
for mv in moves:
    if board.turn == chess.BLACK:
        n += 1
        if n in WANT:
            san_check = board.san(mv)
            print(f"MOVE#{n} played={san_check} fen_before={board.fen()}")
    board.push(mv)
print("FENS-DONE")
