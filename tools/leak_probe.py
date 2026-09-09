#!/usr/bin/env python3
"""L2 leak-suite probe runner (dev tool, NOT shipped).

Reads results/leak_suite/fens.json (list of {game, side, ply, san,
cp_loss, verdict, fen_before}) and probes each FEN on THIS tree at a
fixed per-move budget (default 2.6s, the real-clock budget), printing
one line per FEN: searched score + chosen move UCI. Run twice (two
trees or two toggle states) and diff the outputs.

Usage:
  python tools/leak_probe.py <tag> [budget_s]
"""
import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

_NAMES = "abcdefgh"

from engine import board as B  # noqa: E402
from engine import search as S  # noqa: E402
from engine import tt as TT  # noqa: E402


def _uci(mv) -> str:
    fr, to = B.m_from(mv), B.m_to(mv)
    # 0x88 square = rank*16 + file; sq64 = (sq >> 4) << 3 + (sq & 7)
    s = _NAMES[B.sq64(fr) & 7] + str((B.sq64(fr) >> 3) + 1) \
        + _NAMES[B.sq64(to) & 7] + str((B.sq64(to) >> 3) + 1)
    promo = B.m_promo(mv)
    if promo:
        s += {2: "n", 3: "b", 4: "r", 5: "q"}.get(promo, "")
    return s


def one(fen, budget_ns):
    st = B.parse_fen(fen)
    ttk, ttv = TT.make()
    mask = np.uint64(len(ttk) - 1)
    killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
    hist = np.zeros((2, 64, 64), dtype=np.int32)
    rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
    scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
    nodes = np.zeros(1, dtype=np.int64)
    mv, score, cd = S.search_root(st, nodes, time.monotonic_ns()
                                  + budget_ns, ttk, ttv,
                                  mask, killers, hist, rep, scratch,
                                  sscratch, 64,
                                  np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
    return nodes[0], score, cd, _uci(mv)


def main():
    tag = sys.argv[1]
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 2.6
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fens = json.load(open(os.path.join(here,
                                       "results/leak_suite/fens.json")))
    for e in fens:
        n, sc, cd, uci = one(e["fen_before"], int(budget * 1e9))
        print(f"{tag} {e['game'][:28]:30} ply={e['ply']:3} "
              f"vloss={e['cp_loss']:5} nodes={n} score={sc} "
              f"depth={cd} best={uci}", flush=True)


if __name__ == "__main__":
    main()
