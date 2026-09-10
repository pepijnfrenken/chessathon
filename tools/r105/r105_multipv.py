#!/usr/bin/env python3
"""Quick: multipv=6 at d20 on the r105 pre-#42 position (how many moves win?)."""
import chess
import chess.engine

SF = "/home/pino/.local/bin/stockfish"
FEN = "6k1/5ppp/p7/3P4/6P1/4q2P/5Q2/6K1 b - - 0 47"

eng = chess.engine.SimpleEngine.popen_uci(SF)
eng.configure({"Threads": 4, "Hash": 1024})
b = chess.Board(FEN)
info = eng.analyse(b, chess.engine.Limit(depth=20), multipv=6)
print("d20 multipv6 (our POV):")
for pv in info:
    bb = b.copy()
    parts = []
    for m in pv["pv"][:4]:
        parts.append(bb.san(m))
        bb.push(m)
    print(f"  {' '.join(parts):<28} {pv['score'].pov(chess.BLACK).score(mate_score=10000):+d}")
eng.quit()
print("MULTIPV-DONE")
