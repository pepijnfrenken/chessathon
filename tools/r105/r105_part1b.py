#!/usr/bin/env python3
"""r105 post-mortem — part 1b: SF deep truth on the critical FENs (fixed PV printing)."""
import chess
import chess.engine

SF = "/home/pino/.local/bin/stockfish"

CASES = [
    ("#42 pre Qxh3", "6k1/5ppp/p7/3P4/6P1/4q2P/5Q2/6K1 b - - 0 47"),
    ("#46 pre g6", "4q1k1/2Q2ppp/p7/3P4/6P1/8/5K2/8 b - - 7 51"),
    ("#47 pre Qe5", "4q1k1/2Q2p1p/p2P2p1/8/6P1/8/5K2/8 b - - 0 52"),
    ("#33 pre Rc7", "2r3k1/1p3ppp/p2N4/3P4/2P2pP1/3q1PbP/8/1R4QK b - - 13 38"),
]

eng = chess.engine.SimpleEngine.popen_uci(SF)
eng.configure({"Threads": 4, "Hash": 1024})


def pv_san(b, pv_moves, n=8):
    parts = []
    bb = b.copy()
    for m in pv_moves[:n]:
        try:
            parts.append(bb.san(m))
            bb.push(m)
        except Exception:
            parts.append(m.uci() + "?")
            break
    return " ".join(parts)


for name, fen in CASES:
    b = chess.Board(fen)
    print(f"\n=== {name} ===")
    print(f"    FEN: {fen}")
    for d in (12, 16, 20, 24):
        sc = eng.analyse(b, chess.engine.Limit(depth=d))["score"].pov(chess.BLACK).score(mate_score=10000)
        print(f"    d{d}: {sc:+d}", flush=True)
    info = eng.analyse(b, chess.engine.Limit(depth=18), multipv=3)
    print("    d18 top3 (our POV):")
    for pv in info:
        print(f"      {pv_san(b, pv['pv'])}  ({pv['score'].pov(chess.BLACK).score(mate_score=10000):+d})")

eng.quit()
print("\nPART1B-DONE")
