#!/usr/bin/env python3
"""r61 decision probe v2 — deterministic.

Builds the engine's _GAME_KEYS window EXACTLY as the real ladder run had
it (pre-move + post-our-move keys for our moves 1..12, from the real PGN
— no get_move replay, so machine-speed overruns can't corrupt state),
then searches the REAL decision position (before our 13th move,
20...Qd6) with the real history window.

score < 0  -> engine saw itself worse: the repetition was a correct hold
score ~ 0  -> equal position drawn by repetition: acceptable, but note it
score > 0  -> engine thought it was BETTER and still repeated: the
              -20cp 2nd-occurrence penalty was too soft (design finding)
"""
import io
import sys

import chess
import chess.pgn

sys.path.insert(0, "/home/pino/projects/chessathon")
import agent  # noqa: E402  (JIT warmup ~40s)
from agent import B, S, _GAME_KEYS, _ghist, _inc_ms  # noqa: E402
import engine.time as TM  # noqa: E402

PGN = "/home/pino/projects/chessathon/results/matches/round-61-vs-crimsonbot.pgn"
CLOCK13_MS = 90_700   # time_left before our 13th move (from the match log)

game = chess.pgn.read_game(io.open(PGN))
board = game.board()
our = chess.BLACK
moves = list(game.mainline_moves())

pre_fens, post_fens = [], []
b = board.copy()
for mv in moves:
    if b.turn == our:
        pre_fens.append(b.fen())
        b.push(mv)
        post_fens.append(b.fen())
    else:
        b.push(mv)

# decision position = before our 13th move (ply 26)
assert len(pre_fens) == 13, len(pre_fens)
decision_fen = pre_fens[-1]
print(f"decision position (before 20...Qd6): {decision_fen}")
print(f"real move played here: Qd6 (2nd occurrence of this position)\n")

# rebuild the game window as the engine had it: for moves 1..12, the
# pre-move key was appended at get_move start, the post-move key at the
# end (agent.py lines ~145-161); then get_move for move 13 appends the
# root and searches with everything before it.
_GAME_KEYS.clear()
for p, q in zip(pre_fens[:-1], post_fens[:-1]):
    _GAME_KEYS.append(B.parse_fen(p)["key"][0])
    _GAME_KEYS.append(B.parse_fen(q)["key"][0])
print(f"rebuilt window: {len(_GAME_KEYS)} pre-decision keys "
      f"(expect 24: 12 pre-move + 12 post-move)")

st = B.parse_fen(decision_fen)
if not _GAME_KEYS or _GAME_KEYS[-1] != st["key"][0]:
    _GAME_KEYS.append(st["key"][0])


def root_probe(ghist, gcnt, label):
    nodes = agent._NODES
    nodes[0] = 0
    deadline = S._NOW() + int(TM.budget_ms(CLOCK13_MS, _inc_ms()) * 1_000_000)
    mv, score, depth = S.search_root(
        st, nodes, deadline, agent._TT_KEYS, agent._TT_VALS,
        agent._TT_MASK, agent._KILLERS, agent._HIST, agent._REP,
        agent._SCRATCH, agent._SSCRATCH, agent._MAX_DEPTH, ghist, gcnt)
    uci = B.move_to_uci(mv) if mv else "none"
    print(f"[{label}] best={uci} eff_score={score} depth={depth} "
          f"nodes={nodes[0]}")


ghist, gcnt = _ghist()
root_probe(ghist, gcnt, "with history  ")
root_probe(agent._REP[:0], 0, "empty history ")
