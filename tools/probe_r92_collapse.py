#!/usr/bin/env python3
"""r92 collapse probe (v7's first ladder loss vs Team I Love Fortnite).

Repro + attribution matrix for the m35 Qb3 / m36 Rb5 blunders.
Run from the tree root to test THAT tree:
    cd <tree> && /tmp/chessbench/bin/python <path>/probe_r92_collapse.py
SWEEP=1 (v7 only) adds a budget sweep to map the blunder band (ms budgets).

Covers:
  1. Exact-game-budget picks at m35 (tl=64.754s) / m36 (tl=63.313s) — real
     moves were d5b3 (Qb3) and b4b5 (Rb5).
  2. Budget sweep (SWEEP=1): 1/2/3/5/10/25s — maps non-monotonicity.
  3. Black-to-move blind test: after Qb3 / after Rb5, does THIS tree's
     search find the refutation (Qg5+) at a game-like black budget?

Reference results (2026-09-10): v7 reproduces both blunders at exact game
budget (2/2 runs); V5 avoids both at 1/5/25s; SF d20: -159/-190 before,
-657/-605 after the blunders; refutation Qg5+ in both cases.
"""
import os
import sys
import time

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_r92_{os.path.basename(TREE)}"
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import eval as E  # noqa: E402
import agent as A  # noqa: E402

M35 = ("m35 before Qb3", "2r3k1/p3qpp1/Pp5p/3QN3/1R1BP3/6KP/6P1/2r5 w - - 4 35", 64754, "d5b3")
M36 = ("m36 before Rb5", "6k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/2r3P1/2r5 w - - 6 36", 63313, "b4b5")
AFTER = [
    ("after Qb3 (black to move; SF says Qg5+)", "2r3k1/p3qpp1/Pp5p/4N3/1R1BP3/1Q4KP/6P1/2r5 b - - 5 35", 26500),
    ("after Rb5 (black to move; SF says Qg5+)", "6k1/p3qpp1/Pp5p/1R2N3/3BP3/1Q4KP/2r3P1/2r5 b - - 7 36", 25500),
]
SWEEP_MS = [1000, 2000, 3000, 5000, 10000, 25000]


def probe(fen, tl):
    A._GAME_KEYS = []
    t0 = time.time()
    mv = A.get_move(fen, tl)
    return mv, time.time() - t0


def tl_for(budget_ms):
    return (budget_ms - 500) * 45


print(f"=== r92 collapse probe [{TREE}] ===")
for name, fen, tl, real in (M35, M36):
    sv = E.evaluate(B.parse_fen(fen))
    mv, dt = probe(fen, tl)
    tag = "SAME-as-game" if mv == real else "different"
    print(f"{name}: static={sv} | real={real} | exact-budget pick={mv} ({dt:.2f}s) [{tag}]")
    if os.environ.get("SWEEP") == "1":
        for b in SWEEP_MS:
            mv, dt = probe(fen, tl_for(b))
            print(f"    {b}ms -> {mv} ({dt:.2f}s)")

for name, fen, tl in AFTER:
    sv = E.evaluate(B.parse_fen(fen))
    mv, dt = probe(fen, tl)
    print(f"{name}: static(mover=black)={sv} | pick={mv} ({dt:.2f}s)")
