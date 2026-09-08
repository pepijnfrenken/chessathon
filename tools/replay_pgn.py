#!/usr/bin/env python3
"""Replay a real match PGN against the CURRENT shipped agent (agent.py's
get_move) to check behaviour reproduction — e.g. does it shuffle into a
threefold on the same positions the ladder saw?

Usage:
    python3 tools/replay_pgn.py <game.pgn> [--our-color black|white]
                                 [--clock 120000] [--inc 500]

Feeds positions to the agent exactly like the competition harness:
get_move(fen_of_position_before_our_move, time_left_ms). Tracks real
elapsed time against the clock (base + increment per move, like the
120s+0.5s ladder clock) and reports: our move vs actual game move,
illegal moves, flags, threefolds and the final result.

Why: the round-61 log (drawn by threefold after a Qd6/Qe7 shuffle)
cannot be classified from the log alone — the log omits the opponent's
moves. Replaying the real FEN stream through the shipped agent tells us
whether the stateful anti-shuffle fix (49c4c0e) reproduces the draw
(bug or by-design defence) or refuses the repetition (round ran an
older build / different conditions).
"""
import sys
import time
import io
import argparse

import chess
import chess.pgn

sys.path.insert(0, ".")

# Importing agent.py runs the numba JIT warmup (~40s) — that is intended:
# it mirrors the box init and must happen before any timed move.
import agent  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--our-color", default="black",
                    choices=["white", "black"])
    ap.add_argument("--clock", type=int, default=120_000,
                    help="base clock ms per side")
    ap.add_argument("--inc", type=int, default=500,
                    help="increment ms per move")
    args = ap.parse_args()

    game = chess.pgn.read_game(io.open(args.pgn))
    if game is None:
        print("no game parsed")
        return

    board = game.board()
    our_side = chess.WHITE if args.our_color == "white" else chess.BLACK
    clock = {chess.WHITE: args.clock, chess.BLACK: args.clock}
    moves = list(game.mainline_moves())
    our_moves = []
    flagged = False
    illegal = False

    print(f"replaying {len(moves)} plies; we play {args.our_color}")
    t_start = time.perf_counter()
    for i, mv in enumerate(moves):
        side = board.turn
        board.push(mv)
        if side != our_side:
            # opponent moved; our clock unchanged
            continue
        # it is our turn: board holds the position the harness would send
        fen = board.fen()
        t0 = time.perf_counter()
        got = agent.get_move(fen, clock[our_side])
        took = (time.perf_counter() - t0) * 1000
        clock[our_side] -= int(took)          # our thinking time
        clock[our_side] += args.inc           # increment
        if clock[our_side] < 0:
            flagged = True
            print(f"  FLAG on ply {i+1}")
            break
        gm = chess.Move.from_uci(got) if got != "0000" else None
        ours = mv
        match = (gm == ours)
        our_moves.append((board.san(mv), got, match))
        if not match:
            print(f"  ply {i+1}: game {board.san(ours)} vs agent {got} "
                  f"{'OK' if match else 'DIFF'}")
        if got == "0000" and not board.is_game_over():
            illegal = True
            break
        board.push(gm)  # apply what the agent played for game state
        if board.is_game_over():
            print(f"  game over after our ply {i+1}: "
                  f"{board.result()} ({board.outcome().termination.name})")
            break

    elapsed = time.perf_counter() - t_start
    print(f"\n{len(our_moves)} of our moves played in {elapsed:.0f}s "
          f"(incl. ~40s JIT warmup)")
    agreed = sum(1 for _, _, m in our_moves if m)
    print(f"moves matching the real game: {agreed}/{len(our_moves)}")
    print(f"illegal: {illegal} | flag: {flagged}")
    if our_moves:
        last = our_moves[-1]
        print(f"last agent move: {last[1]} (game played {last[0]})")


if __name__ == "__main__":
    main()
