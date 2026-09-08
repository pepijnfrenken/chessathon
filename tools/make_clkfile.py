#!/usr/bin/env python3
"""Emit a replay --clkfile (exact time_left before each of OUR moves) from a
match log (clock-left-after-move list) or from the PGN %clk annotations.

Usage:
  from_log:  python3 make_clkfile.py --from-log <match.log> [--n-moves 13]
  from_pgn:  python3 make_clkfile.py --pgn <game.pgn> --our white|black
"""
import argparse
import io
import re

import chess
import chess.pgn


def from_log(path: str, n_moves: int) -> list:
    txt = open(path).read()
    # the .log lists "clock left" after each of OUR moves, e.g. " 1 dxc4 4.3 s 116.2 s"
    vals = []
    for line in txt.splitlines():
        m = re.search(r"^\s*\d+\s+\S+\s+[\d.]+\s*s\s+([\d.]+)\s*s", line)
        if m:
            vals.append(float(m.group(1)))
    if len(vals) < n_moves:
        raise SystemExit(f"only {len(vals)} clock values found, need {n_moves}")
    return [120.0] + vals[:n_moves - 1]   # move1 starts on full base


def from_pgn(path: str, our_color: str) -> list:
    game = chess.pgn.read_game(io.open(path))
    our = chess.WHITE if our_color == "white" else chess.BLACK
    after_ours = []
    node = game
    while node.variations:
        node = node.variations[0]
        if node.move is not None and node.turn() != our:
            if node.clock() is not None:
                after_ours.append(node.clock())
    if not after_ours:
        raise SystemExit("no %clk values found on our moves")
    return [120.0] + after_ours[:-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-log")
    ap.add_argument("--pgn")
    ap.add_argument("--our", choices=["white", "black"])
    ap.add_argument("--n-moves", type=int)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    if args.from_log:
        clocks = from_log(args.from_log, args.n_moves or 13)
    elif args.pgn:
        clocks = from_pgn(args.pgn, args.our)
    else:
        raise SystemExit("need --from-log or --pgn")
    with open(args.out, "w") as fh:
        fh.write("\n".join(f"{c:.3f}" for c in clocks) + "\n")
    print(f"{len(clocks)} time_left values -> {args.out} "
          f"(move 1 = {clocks[0]}, last = {clocks[-1]})")


if __name__ == "__main__":
    main()
