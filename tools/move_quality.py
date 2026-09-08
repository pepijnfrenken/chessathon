"""Move-quality classifier for Chessathon ladder PGNs (dev tool, NOT shipped).

Classifies every move of a game from brilliant to blunder using OUR OWN
engine's search at a fixed depth as the referee (self-consistent with how
the engine plays; --depth controls effort). Optionally cross-check with
Stockfish later (--engine sf).

Method (sequential evals):
  For each position i (side_i to move) run search_root at fixed depth ->
  E_i (cp from side_i's perspective; MATE scores clamped to +-30000).
  The value of the played move m_i from side_i's perspective is -E_{i+1}
  (E_{i+1} = value of the resulting position from the NEXT side's view).
  cp_loss(m_i) = E_i + E_{i+1}   (>= 0; 0 = perfect move)

Buckets (documented, tuned to this engine's eval scale):
  <= 10 best | <= 40 excellent | <= 90 good | <= 160 inaccuracy
  | <= 300 mistake | > 300 blunder
  brilliant = special: played move is a material SACRIFICE (gives up >= 3
  material points, python-chess material diff) yet still scores <= 20 cp
  loss (i.e. it is the best move anyway).

Usage:
  PY=/tmp/chessbench/bin/python (has python-chess); run from repo root:
  python tools/move_quality.py results/matches/round-74-vs-rohan.pgn \
      --depth 10 [--side white|black] [--json out.json]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache_chessathon_mq")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import chess  # noqa: E402
import chess.pgn  # noqa: E402

import agent as A  # noqa: E402  (import warms up the jitted chain)
from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
       chess.ROOK: 5, chess.QUEEN: 9}

CLAMP = 30000


def _search_eval(st, depth):
    """Search `st` (our board state) at fixed depth; return (move, score)."""
    A._NODES[0] = 0
    far = S._NOW() + 3600_000_000_000  # 1h deadline: depth-limited, not time
    ghist, gcnt = A._ghist()  # empty window outside get_move flow
    mv, score, _depth = S.search_root(
        st, A._NODES, far, A._TT_KEYS, A._TT_VALS, A._TT_MASK,
        A._KILLERS, A._HIST, A._REP, A._SCRATCH, A._SSCRATCH, depth,
        ghist, gcnt)
    return mv, score


def _mat(b):
    return sum(VAL[p.piece_type] * (1 if p.color == chess.WHITE else -1)
               for sq in chess.SQUARES if (p := b.piece_at(sq)))


def classify(loss, sac_ok, was_best):
    if sac_ok and loss <= 20:
        return "brilliant"
    if loss <= 10:
        return "best"
    if loss <= 40:
        return "excellent"
    if loss <= 90:
        return "good"
    if loss <= 160:
        return "inaccuracy"
    if loss <= 300:
        return "mistake"
    return "blunder"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--side", choices=["white", "black"], default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    g = chess.pgn.read_game(open(a.pgn))
    b = g.board()
    rows = []
    evals = []          # E_i per position index (side_i perspective)
    nodes = list(g.mainline())

    # E_0..E_n: search EVERY position once (n+1 searches)
    t0 = time.time()
    st = B.parse_fen(b.fen())
    for i, node in enumerate([None] + list(nodes)):
        if i > 0:
            b.push(nodes[i - 1].move)
        mv, score = _search_eval(B.parse_fen(b.fen()), a.depth)
        evals.append(score)
        if (i % 20) == 0:
            print(f"  searched pos {i}/{len(nodes)} ({time.time()-t0:.0f}s)",
                  file=sys.stderr)

    # classify moves i (0-based ply index): uses E_i and E_{i+1}
    b = g.board()
    side_names = {chess.WHITE: "white", chess.BLACK: "black"}
    for i, node in enumerate(nodes):
        mv = node.move
        mover = side_names[b.turn]
        b.push(mv)
        E_i = evals[i]
        E_next = evals[i + 1]
        loss = E_i + E_next                      # from mover's perspective
        mate = abs(E_i) >= 29000 or abs(E_next) >= 29000
        loss = max(0, loss)
        # sacrifice detection: mover's material dropped by >= 3 in this move
        b2 = g.board()
        for k in range(i + 1):
            b2.push(nodes[k].move)
        # material before move == material at position i: track incrementally
        # (cheap redo: mat_before from board with i pushes)
        b1 = g.board()
        for k in range(i):
            b1.push(nodes[k].move)
        sign = 1 if b1.turn == chess.WHITE else -1
        sac = sign * (_mat(b1) - _mat(b)) >= 3
        v = classify(loss, sac, loss <= 10)
        rows.append({
            "ply": i + 1, "side": mover, "san": b.san(mv),
            "uci": mv.uci(), "cp_loss": round(loss),
            "eval_before": E_i, "verdict": v, "sacrifice": sac,
            "mate_ctx": mate,
        })
        if a.side and mover != a.side:
            continue
        print(f"{i+1:3d} {mover[0].upper()} {b.san(mv):<12s} "
              f"loss {loss:6.0f}  {v}")

    counts = {}
    for r in rows:
        if a.side and r["side"] != a.side:
            continue
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("\nSUMMARY:", counts)
    print(f"biggest losses: " +
          ", ".join(f"{r['san']} ({r['cp_loss']}cp {r['verdict']})"
                    for r in sorted(rows, key=lambda r: -r["cp_loss"])[:5]))
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
