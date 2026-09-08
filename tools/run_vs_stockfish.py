"""V5 vs Stockfish 19 bout (dev tool, NOT shipped).

Runs the shipped engine (via engine_side subprocess semantics) against a
real Stockfish under UCI_LimitStrength (so SF plays a calibrated, beatable
but clearly-better level) from the ladder's curated mid-book start FENs.

Our side: engine_side.py subprocess with CHESSATHON_MOVE_BUDGET_MS (fixed
per-move budget; default 1200). SF side: python-chess engine, UCI_Elo
(default 2200) + fixed time limit.

Usage (from repo root, PY=/tmp/chessbench/bin/python):
  python tools/run_vs_stockfish.py --games 6 --our-budget-ms 1200 \
      --sf-elo 2200 [--out results/vs_sf/]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

import chess  # noqa: E402
import chess.engine  # noqa: E402
import chess.pgn  # noqa: E402

ENGINE_SIDE = sys.executable  # chessbench python (has python-chess)
STOCKFISH = str(Path.home() / ".local/bin/stockfish")

# Curated mid-book start FENs from our own ladder PGNs (r69-r74)
STARTS = [
    # (fen, side-to-move name for OUR engine)
    ("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 1", "b"),  # noqa
]


def fen_starts_from_pgns(repo: Path, limit: int = 6):
    """Pull distinct [SetUp] FENs from our ladder PGNs (mid-book starts)."""
    fens = []
    for p in sorted((repo / "results/matches").glob("round-6*.pgn")):
        if len(fens) >= limit:
            break
        txt = p.read_text(errors="ignore")
        import io
        g = chess.pgn.read_game(io.StringIO(txt))
        if not g:
            continue
        h = g.headers
        if h.get("SetUp") == "1" and "FEN" in h:
            fen = h["FEN"]
            board = chess.Board(fen)
            if board.is_valid():
                fens.append(fen)
    # pad with classic middlegame positions if corpus is short
    while len(fens) < limit:
        fens.append(STARTS[0])
    return fens[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--our-budget-ms", type=int, default=1200)
    ap.add_argument("--sf-elo", type=int, default=2200)
    ap.add_argument("--sf-time-ms", type=int, default=400)
    ap.add_argument("--out", default="results/vs_sf")
    a = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    outdir = repo / a.out
    outdir.mkdir(parents=True, exist_ok=True)
    fens = fen_starts_from_pgns(repo, a.games)

    sf = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    sf.configure({"UCI_LimitStrength": True, "UCI_Elo": a.sf_elo})
    env = dict(os.environ, CHESSATHON_MOVE_BUDGET_MS=str(a.our_budget_ms))
    eng = subprocess.Popen(
        [ENGINE_SIDE, "-u", str(repo / "tools/_sf_bout_side.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=env, cwd=str(repo))

    summary = []
    for gi, fen in enumerate(fens):
        our_white = (gi % 2 == 0)
        board = chess.Board(fen)
        eng.stdin.write("reset\n")
        eng.stdin.flush()
        pgn = chess.pgn.Game()
        pgn.headers.update({
            "Event": "V5 vs Stockfish19 bout (local)",
            "White": "EnPassantLabs-V5" if our_white else "Stockfish19-e2200",
            "Black": "Stockfish19-e2200" if our_white else "EnPassantLabs-V5",
            "SetUp": "1", "FEN": fen,
        })
        node = pgn
        flags = []
        t0 = time.time()
        try:
            while not board.is_game_over() and node.ply() < 240:
                if board.turn == (chess.WHITE if our_white else chess.BLACK):
                    eng.stdin.write(f"{board.fen()}\n")
                    eng.stdin.flush()
                    # select-based read: 90s cap so a wedged side can't hang
                    import select
                    r, _, _ = select.select([eng.stdout], [], [], 90)
                    if not r:
                        flags.append("SIDE-TIMEOUT")
                        break
                    uci = eng.stdout.readline().strip()
                    if uci == "0000":
                        break
                    mv = chess.Move.from_uci(uci)
                    if mv not in board.legal_moves:
                        flags.append(f"ILLEGAL {uci}")
                        break
                    board.push(mv)
                else:
                    res = sf.play(board, chess.engine.Limit(time=a.sf_time_ms / 1000))
                    board.push(res.move)
                node = node.add_variation(board.peek())
            result = board.result()
        except Exception as exc:  # noqa
            result = "*"
            flags.append(f"EXC {exc!r}")
        node.comment = f"[%clk n/a] {result} flags={flags}"
        fname = outdir / f"v5sf_{'w' if our_white else 'b'}_{gi}.pgn"
        fname.write_text(str(pgn))
        summary.append((gi + 1, "W" if our_white else "B", result, flags,
                        round(time.time() - t0), board.fullmove_number))
        print(f"game {gi+1}: ours={'W' if our_white else 'B'} result={result} "
              f"flags={flags} plies={board.fullmove_number*2} "
              f"({time.time()-t0:.0f}s) -> {fname}")
    eng.kill()
    sf.quit()
    w = sum(1 for s in summary if s[2] == ("1-0" if s[1] == "W" else "0-1"))
    d = sum(1 for s in summary if s[2] == "1/2-1/2")
    print(f"\nBOUT SUMMARY: {w}W-{d}D-{len(summary)-w-d}L of {len(summary)} "
          f"(ours as W: {sum(1 for s in summary if s[1]=='W' and (s[2]=='1-0'))}, "
          f"ours as B: {sum(1 for s in summary if s[1]=='B' and s[2]=='0-1')})")
    (outdir / "summary.txt").write_text("\n".join(str(s) for s in summary))


if __name__ == "__main__":
    main()
