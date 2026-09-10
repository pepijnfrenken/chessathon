#!/usr/bin/env python3
"""r105 focused: our-move table with deltas + deep checks on the collapse.

Also pulls our per-move times from the venue log to correlate blunder vs budget."""
import io
import pathlib
import re

import chess
import chess.engine
import chess.pgn

SF = "/home/pino/.local/bin/stockfish"
MAT = pathlib.Path("/home/pino/projects/chessathon/results/matches")
PGN = MAT / "round-105-vs-zero-elo.pgn"
LOG = MAT / "round-105-vs-zero-elo.log"
OURS = "En Passant Labs"

eng = chess.engine.SimpleEngine.popen_uci(SF)
eng.configure({"Threads": 4, "Hash": 1024})

txt = PGN.read_text()
game = chess.pgn.read_game(io.StringIO(txt))
board = game.board()
moves = list(game.mainline_moves())

# our move times from the venue log
logtxt = LOG.read_text()
our_times = {}
for m in re.finditer(r"^\s*(\d+)\s+(\S+)\s+([\d.]+)\s*s", logtxt, re.M):
    our_times[int(m.group(1))] = (m.group(2), float(m.group(3)), )


def ev(b, d=12):
    return eng.analyse(b, chess.engine.Limit(depth=d))["score"].pov(chess.BLACK).score(mate_score=10000)


print("=== our moves: #, SAN, [time], eval_before, eval_after, delta ===")
rows = []
our_move_no = 0
ev_before = None
for i, mv in enumerate(moves):
    if board.turn == chess.BLACK:
        our_move_no += 1
        e_b = ev(board)
        san = board.san(mv)
        board.push(mv)
        e_a = ev(board)
        tm = our_times.get(our_move_no, ("?", 0))
        rows.append((our_move_no, san, tm, e_b, e_a, e_a - e_b))
        board.pop()
        board.push(mv)
    else:
        board.push(mv)

for no, san, tm, eb, ea, dd in rows:
    mark = " <<<<<" if dd <= -200 else (" <<<" if dd <= -120 else "")
    print(f"  #{no:>2} {san:<7} [{tm[1]:>4.1f}s]  {eb:>+6} -> {ea:>+6}  ({dd:>+5}){mark}")

# deep checks on key positions
print("\n=== deep checks (d18) at the collapse ===")
keys = []
for no, san, tm, eb, ea, dd in rows:
    if dd <= -250:
        keys.append(no)
print("blunder move numbers:", keys)

board2 = game.board()
n = 0
for i, mv in enumerate(moves):
    if board2.turn == chess.BLACK:
        n += 1
        if n in keys:
            fen = board2.fen()
            b = chess.Board(fen)
            played = board2.san(mv)
            eng.configure({"MultiPV": 2})
            info = eng.analyse(b, chess.engine.Limit(depth=18), multipv=2)
            pvs = []
            for pv in info:
                line = " ".join(b.san(m) for m in pv["pv"][:5])
                pvs.append(f"{line} ({pv['score'].pov(chess.BLACK).score(mate_score=10000):+d})")
            print(f"\n  our move #{n} played: {played}")
            print(f"    d18 best:    {pvs[0]}")
            if len(pvs) > 1:
                print(f"    d18 2nd:     {pvs[1]}")
            print(f"    position: {fen}")
    board2.push(mv)
eng.quit()
print("DONE-FOCUS")
