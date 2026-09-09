#!/usr/bin/env python3
"""Determinism probe (dev tool, NOT shipped).

Runs search_root on one FEN at a fixed depth in N fresh processes and
prints nodes/best/score per process — identical lines prove the build is
deterministic (and, for a toggle A/B, that feature-OFF matches the
baseline node-for-node).

Usage:
  python tools/det_check.py "<FEN>" <depth> [--env CHESSATHON_X=1]
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = "/tmp/chessbench/bin/python"

PROBE = r'''
import sys, time
sys.path.insert(0, ".")
import numpy as np
from engine import board as B
from engine import search as S
from engine import tt as TT

fen, depth = sys.argv[1], int(sys.argv[2])
st = B.parse_fen(fen)
ttk, ttv = TT.make()
mask = np.uint64(len(ttk) - 1)
killers = np.zeros((2, B.MAX_PLY), dtype=np.int32)
hist = np.zeros((2, 64, 64), dtype=np.int32)
rep = np.zeros(S.REP_SIZE, dtype=np.uint64)
scratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
sscratch = np.zeros((B.MAX_PLY, B.MAX_MOVES), dtype=np.int32)
nodes = np.zeros(1, dtype=np.int64)
mv, score, cd = S.search_root(st, nodes, S._NOW() + 3_600_000_000_000,
                              ttk, ttv, mask, killers, hist, rep,
                              scratch, sscratch, depth,
                              np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
print(f"proc: nodes={nodes[0]} best={mv} score={score} depth={cd}")
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fen")
    ap.add_argument("depth", type=int)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--label", default="")
    ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args()
    if a.label:
        print(f"# {a.label}")
    env = dict(os.environ)
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v
    env.setdefault("NUMBA_NUM_THREADS", "1")
    lines = []
    for _ in range(a.procs):
        r = subprocess.run([PY, "-u", "-c", PROBE, a.fen, str(a.depth)],
                           capture_output=True, text=True, cwd=os.getcwd(),
                           env=env)
        out = r.stdout.strip().splitlines()
        line = out[-1] if out else f"proc: ERROR {r.stderr[-200:]}"
        print(line, flush=True)
        lines.append(line)
    return 0 if len(set(lines)) == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
