#!/usr/bin/env python3
"""r64 post-mortem: engine eval at key moments (empty history, ~2.5s)."""
import io, sys
import chess, chess.pgn
sys.path.insert(0, "/home/pino/projects/chessathon")
import agent  # noqa: E402
from agent import B, S  # noqa: E402
import engine.time as TM  # noqa: E402

PGN = "/home/pino/projects/chessathon/results/matches/round-64-vs-snake.pgn"
game = chess.pgn.read_game(io.open(PGN))
moves = list(game.mainline_moves())
b = game.board()

# (ply, label) — plies are 1-indexed; probe AFTER that ply is played
probes = [(33, "Bxc8 wins exchange (we move next as White? ply33=White)"),
          (75, "just before their Nxh3 fork (we played Rh3)"),
          (85, "just before Rxc1/Rxa5 trades"),
          (100, "after their e1=Q promotion (Q-endgame starts)")]
for target, label in probes:
    bb = b.copy()
    for i, mv in enumerate(moves):
        if i + 1 > target:
            break
        bb.push(mv)
    st = B.parse_fen(bb.fen())
    nodes = agent._NODES
    nodes[0] = 0
    # budget_ms = time_left/45 + inc -> pass time_left ~120s for ~2.6s budget
    deadline = S._NOW() + int(TM.budget_ms(120_000, 0) * 1_000_000)
    mv, score, depth = S.search_root(
        st, nodes, deadline, agent._TT_KEYS, agent._TT_VALS,
        agent._TT_MASK, agent._KILLERS, agent._HIST, agent._REP,
        agent._SCRATCH, agent._SSCRATCH, agent._MAX_DEPTH,
        agent._REP[:0], 0)
    side = "white" if bb.turn == chess.WHITE else "black"
    print(f"ply {target:3d} ({side} to move): {label}")
    print(f"    eval {score:+d} cp (from {side} view), best {B.move_to_uci(mv)}, depth {depth}")
