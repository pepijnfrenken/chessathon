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
    ap.add_argument("--clkfile", type=str, default=None,
                    help="file with the exact time_left_ms to pass BEFORE "
                         "each of OUR moves (one value per line, seconds "
                         "or ms; first line = move 1). From the ladder "
                         "match log: clock-left after our previous move "
                         "(move 1 = 120000). Exact clocks make the "
                         "deterministic engine reproduce the real game "
                         "move-for-move unless behaviour differs.")
    args = ap.parse_args()

    exact_clocks = None
    if args.clkfile:
        exact_clocks = []
        for ln in open(args.clkfile):
            ln = ln.strip()
            if not ln:
                continue
            v = float(ln)
            exact_clocks.append(int(v * 1000) if v < 1000 else int(v))
        print(f"using {len(exact_clocks)} exact clocks from {args.clkfile}")

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
        if side == our_side:
            # OUR turn: feed the position exactly as the harness would
            # (position BEFORE our move), then push what the agent plays.
            fen = board.fen()
            t0 = time.perf_counter()
            tl = (exact_clocks[len(our_moves)]
                  if exact_clocks is not None else clock[our_side])
            got = agent.get_move(fen, tl)
            took = (time.perf_counter() - t0) * 1000
            if exact_clocks is None:
                clock[our_side] -= int(took)          # our thinking time
                clock[our_side] += args.inc           # increment
                if clock[our_side] < 0:
                    flagged = True
                    print(f"  FLAG on ply {i+1}")
                    break
            gm = chess.Move.from_uci(got) if got != "0000" else None
            ours = mv
            match = (gm == ours)
            # san() only works when the move is legal on the current
            # board — after a deviation the REAL move may not be; use
            # uci in that case (the pre-move position always has ours
            # legal, but the board may already be the agent's branch).
            try:
                ours_san = board.san(ours)
            except Exception:
                ours_san = ours.uci()
            our_moves.append((ours_san, got, match))
            if not match:
                print(f"  ply {i+1}: game {ours_san} vs agent {got} DIFF")
            if got == "0000" or gm is None or gm not in board.legal_moves:
                illegal = True
                break
            board.push(gm)  # agent's branch: game diverges from PGN here
            if board.is_game_over():
                print(f"  game over after our ply {i+1}: "
                      f"{board.result()} ({board.outcome().termination.name})")
                break
        else:
            # opponent's turn: play the real PGN move if still legal on
            # the agent's branch; otherwise we have diverged and the PGN
            # no longer constrains the game -> stop and report.
            if mv not in board.legal_moves:
                print(f"  divergence: opponent move {board.san(mv)} no "
                      f"longer legal after our deviation (ply {i+1})")
                break
            board.push(mv)

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
