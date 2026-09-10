"""Mate-stratum / C3b relevance check (python-chess + logs only; no engine)."""
import json
import re

import chess

LOG = "/home/pino/projects/chessathon/results/v8dp_leak_probe_cand_mate.log"
MS = "/home/pino/projects/chessathon/results/leak_suite/mate_stratum.json"


def load(p):
    out = []
    for ln in open(p):
        if ln.startswith("#"):
            continue
        m = re.search(r"ply=\s*(\d+)\s+vloss=\s*(\d+)\s+nodes=(\d+)\s+"
                      r"score=(-?\d+)\s+depth=(\d+)\s+best=(\S+)", ln)
        if m:
            out.append(dict(game=ln.split()[1], ply=int(m.group(1)),
                            score=int(m.group(4)), depth=int(m.group(5)),
                            uci=m.group(6)))
    return out


rows = load(LOG)
ms = json.load(open(MS))
meta = {(r["game"], r["ply"]): r for r in ms}

mate = p7 = other = nofen = 0
print(f"{'game':30s} {'ply':>4} {'score':>7} {'pc':>3} pawn7  class")
for r in rows:
    src = meta.get((r["game"], r["ply"]))
    ismate = abs(r["score"]) > 29000
    has7 = False
    n = -1
    if src:
        b = chess.Board(src["fen_before"])
        n = len(b.piece_map())
        for sq, pc in b.piece_map().items():
            if pc.piece_type == chess.PAWN:
                if pc.color == chess.WHITE and chess.square_rank(sq) == 6:
                    has7 = True
                if pc.color == chess.BLACK and chess.square_rank(sq) == 1:
                    has7 = True
    cls = "MATE" if ismate else ("PAWN-ON-7" if has7 else "other")
    if ismate:
        mate += 1
    elif src is None:
        nofen += 1
    elif has7:
        p7 += 1
    else:
        other += 1
    print(f"{r['game'][-30:]:30s} {r['ply']:>4} {r['score']:>7} {n:>3} "
          f"{str(has7):5s} {cls}")

print()
print(f"rows={len(rows)}  mate={mate}  non-mate+pawn-on-7th={p7}  "
      f"non-mate-other={other}  no-fen={nofen}")
tot = mate + p7 + other
if tot:
    print(f"=> C3b (quiet promotions) is implicated in {p7}/{tot} rows "
          f"({100*p7/tot:.0f}%)")
print("DONE")
