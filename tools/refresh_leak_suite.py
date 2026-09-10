#!/usr/bin/env python3
"""Refresh the leak suite from the SF review corpus (add-only).

Convention (established 2026-09-09/10, see PROCESS §12-13):
- rows: OUR side only (side detected via the PGN header name == OUR_NAME),
  cp_loss >= 160
- split: |eval_before| >= 20000 -> mate_stratum.json, else fens.json
- add-only: new rows are appended; existing rows are never modified/removed
- fen_before = position before the flagged move (PGN replay)

Usage:
    /tmp/chessbench/bin/python tools/refresh_leak_suite.py [--dry]

Reads:  results/leak_reviews/round-*.sf16.json  (+ matching results/matches/*.pgn)
Writes: results/leak_suite/fens.json, results/leak_suite/mate_stratum.json
"""
import argparse
import glob
import json
import os
import re
import sys

import chess.pgn

OUR_NAME = "En Passant Labs"
CP_THRESHOLD = 160
MATE_SPLIT = 20000

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEWS = os.path.join(ROOT, "results", "leak_reviews")
MATCHES = os.path.join(ROOT, "results", "matches")
SUITE = os.path.join(ROOT, "results", "leak_suite")


def our_side(pgn_path):
    with open(pgn_path) as f:
        game = chess.pgn.read_game(f)
    w, b = game.headers["White"], game.headers["Black"]
    if w == OUR_NAME:
        return "white", game
    if b == OUR_NAME:
        return "black", game
    raise SystemExit(f"cannot identify our side in {pgn_path}: White={w!r} Black={b!r}")


def refresh_one(review_path, fens, mate, added_fens, added_mate, dry):
    base = os.path.basename(review_path)
    game_name = base.split(".sf16.json")[0]
    pgn_path = os.path.join(MATCHES, game_name + ".pgn")
    if not os.path.exists(pgn_path):
        print(f"  SKIP {game_name}: no pgn")
        return
    side, game = our_side(pgn_path)
    rows = json.load(open(review_path))
    have = {(r["game"], r["ply"]) for r in fens + mate}

    # walk the mainline once, remembering the board BEFORE each ply
    board = game.board()
    fens_before = []
    moves = []
    for mv in game.mainline_moves():
        fens_before.append(board.fen())
        moves.append(mv)
        board.push(mv)

    n_new = 0
    for r in rows:
        if r.get("side") != side or (r.get("cp_loss") or 0) < CP_THRESHOLD:
            continue
        if r.get("verdict") not in ("blunder", "mistake"):
            continue
        key = (game_name, r["ply"])
        if key in have:
            continue
        ply = r["ply"]
        if not (1 <= ply <= len(fens_before)):
            print(f"  WARN {game_name} ply {ply} out of range")
            continue
        # cross-check against the uci field when present
        uci = r.get("uci")
        if uci and uci != moves[ply - 1].uci():
            print(f"  WARN {game_name} ply {ply}: uci mismatch {uci} vs {moves[ply-1].uci()}")
            continue
        row = {
            "game": game_name,
            "side": side,
            "ply": ply,
            "san": r.get("san"),
            "cp_loss": r.get("cp_loss"),
            "verdict": r.get("verdict"),
            "eval_before": r.get("eval_before"),
            "fen_before": fens_before[ply - 1],
        }
        dest = "mate" if abs(r.get("eval_before") or 0) >= MATE_SPLIT else "fens"
        (added_mate if dest == "mate" else added_fens).append(row)
        if not dry:
            (mate if dest == "mate" else fens).append(row)
        n_new += 1
        print(f"  + [{dest}] ply {ply:>3} {row['san']:<7} loss={row['cp_loss']:>5} "
              f"eval_before={row['eval_before']:>7} fen={row['fen_before']}")
    if not n_new:
        print(f"  (nothing new in {game_name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    fpath = os.path.join(SUITE, "fens.json")
    mpath = os.path.join(SUITE, "mate_stratum.json")
    fens = json.load(open(fpath))
    mate = json.load(open(mpath))
    n0f, n0m = len(fens), len(mate)
    added_fens, added_mate = [], []

    for rp in sorted(glob.glob(os.path.join(REVIEWS, "round-*.sf16.json"))):
        print(f"== {os.path.basename(rp)}")
        refresh_one(rp, fens, mate, added_fens, added_mate, args.dry)

    print(f"\nfens:  {n0f} -> {n0f + len(added_fens)} (+{len(added_fens)})")
    print(f"mate:  {n0m} -> {n0m + len(added_mate)} (+{len(added_mate)})")
    if args.dry:
        print("dry run — nothing written")
        return
    if added_fens or added_mate:
        json.dump(fens, open(fpath, "w"), indent=1)
        json.dump(mate, open(mpath, "w"), indent=1)
        print("written")


if __name__ == "__main__":
    sys.exit(main())
