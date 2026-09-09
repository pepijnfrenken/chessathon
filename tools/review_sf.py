"""SF19 game review for Chessathon ladder PGNs (dev tool, NOT shipped).

Local equivalent of aichessathon.com's "Game Review Stockfish — depth N":
every move of a game classified from brilliant to blunder using Stockfish
19 as the referee (stronger + independent of our own eval).

Method (sequential evals, same as move_quality.py):
  E_i = SF score at position i (from side_i, cp, mate clamped).
  cp_loss(played m_i) = E_i + E_{i+1}.
Buckets identical to move_quality.py (<=10 best, <=40 excellent, <=90
good, <=160 inaccuracy, <=300 mistake, >300 blunder; brilliant = sac
>=3pt that still scores <=20 loss).

Usage (from repo root, PY=/tmp/chessbench/bin/python):
  python tools/review_sf.py results/matches/round-74-vs-rohan.pgn \
      --depth 16 [--side white] [--json out.json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

import chess  # noqa: E402
import chess.engine  # noqa: E402
import chess.pgn  # noqa: E402

SF = str(Path.home() / ".local/bin/stockfish")
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
       chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def _sf_eval(engine, board, depth):
    """Score of `board` from the side to move (cp; mate clamped to +-30000)."""
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    s = info.get("score")
    if s is None:
        return 0
    pv = s.pov(board.turn)
    if pv.is_mate():
        m = pv.mate()
        return 30000 - abs(m) * 100 if m > 0 else -30000 + abs(m) * 100
    return pv.score() or 0


def _mat(b):
    return sum(VAL[p.piece_type] * (1 if p.color == chess.WHITE else -1)
               for sq in chess.SQUARES if (p := b.piece_at(sq)))


def classify(loss, sac):
    if sac and loss <= 20:
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


def _game_board(g):
    """Starting board of a game, honoring [SetUp]/[FEN] headers."""
    b = g.board()
    if g.headers.get("SetUp") and g.headers.get("FEN"):
        b.set_fen(g.headers["FEN"])
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--depth", type=int, default=16)
    ap.add_argument("--side", choices=["white", "black"], default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    g = chess.pgn.read_game(open(a.pgn))
    engine = chess.engine.SimpleEngine.popen_uci(SF)
    engine.configure({"Threads": 6})
    nodes = list(g.mainline())
    t0 = time.time()

    # E_0..E_n: score every position
    evals = []
    b = _game_board(g)
    for i in range(len(nodes) + 1):
        evals.append(_sf_eval(engine, b, a.depth))
        if i < len(nodes):
            b.push(nodes[i].move)
        if i % 20 == 0:
            print(f"  scored pos {i}/{len(nodes)} ({time.time()-t0:.0f}s)",
                  file=sys.stderr)

    rows = []
    b = _game_board(g)
    for i, node in enumerate(nodes):
        mv = node.move
        mover = "white" if b.turn == chess.WHITE else "black"
        san = b.san(mv)
        sign = 1 if b.turn == chess.WHITE else -1
        mat_before = _mat(b)
        b.push(mv)
        loss = max(0, evals[i] + evals[i + 1])
        sac = sign * (mat_before - _mat(b)) >= 3
        v = classify(loss, sac)
        rows.append({"ply": i + 1, "side": mover, "san": san,
                     "uci": mv.uci(), "cp_loss": round(loss),
                     "eval_before": evals[i], "verdict": v,
                     "sacrifice": sac})
        if a.side and mover != a.side:
            continue
        print(f"{i+1:3d} {mover[0].upper()} {san:<12s} "
              f"loss {loss:6.0f}  {v}")

    counts = {}
    for r in rows:
        if a.side and r["side"] != a.side:
            continue
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("\nSUMMARY:", counts)
    print("biggest: " + ", ".join(
        f"{r['san']} ({r['cp_loss']}cp {r['verdict']})"
        for r in sorted(rows, key=lambda r: -r["cp_loss"])[:5]))
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    engine.quit()


if __name__ == "__main__":
    main()
