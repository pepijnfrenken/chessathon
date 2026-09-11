#!/usr/bin/env python3
"""SF quick reviews of r107, r108, r109: trajectory + our blunders."""
import re
import chess
import chess.engine
import chess.pgn
from pathlib import Path

SF = "/home/pino/.local/bin/stockfish"
MAT = Path("/home/pino/projects/chessathon/results/matches")
GAMES = [
    ("r107", MAT / "round-107-vs-istanbul-s-finest.pgn"),
    ("r108", MAT / "round-108-vs-shallow-blue-2-0.pgn"),
    ("r109", MAT / "round-109-vs-jlu.pgn"),
]
WHO = "En Passant Labs"


def review(tag, path):
    game = chess.pgn.read_game(open(path))
    board = game.board()
    ours_white = WHO in (game.headers.get("White") or "")
    print(f"\n=== {tag} | {game.headers.get('White')} vs {game.headers.get('Black')} | {game.headers.get('Result')} | ours {'White' if ours_white else 'Black'}")
    traj = []
    with chess.engine.SimpleEngine.popen_uci(SF) as eng:
        for i, mv in enumerate(game.mainline_moves()):
            board.push(mv)
            if board.is_game_over():
                break
            # eval from OUR perspective
            info = eng.analyse(board, chess.engine.Limit(depth=14))
            sc = info["score"].pov(chess.WHITE if ours_white else chess.BLACK)
            cp = sc.score(mate_score=10000)
            traj.append(cp if cp is not None else 0)
    # trajectory every 4 plies + drops
    print("traj (every 4):", " ".join(f"{v:+d}" for v in traj[::4]))
    drops = []
    prev = None
    for i, v in enumerate(traj):
        if prev is not None and v - prev <= -150:
            drops.append((i, prev, v))
        prev = v
    print(f"drops <=-150cp: {len(drops)}")
    for i, a, b in drops[:8]:
        print(f"   ply {i}: {a} -> {b}")
    if traj:
        print(f"min {min(traj)} max {max(traj)} final {traj[-1]}")


for tag, p in GAMES:
    if p.exists():
        review(tag, p)
    else:
        print(f"missing: {p}")
