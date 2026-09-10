"""Corpus probe: run the leak-suite FENs through a tree and print, per row,
the pick + static. Run per-tree (Modal modal_probe.py, or locally in the
tree root) to diff candidate vs control WITHOUT the box.

Completes audit-6 C1's pending evidence: "how many of the corpus moves
change, and does any new >=300cp swing appear".

Env:
  PFENS      path to fens.json (default results/leak_suite/fens.json)
  PBUDGET_MS per-move budget in ms (default 2600, the L2 convention)

Output: one line per row: idx | ply | san | pick | static | same?(real san)
"""
import json
import os
import sys
import time

TREE = os.getcwd()
os.environ["NUMBA_CACHE_DIR"] = os.environ.get(
    "NUMBA_CACHE_DIR", f"/tmp/numba_corpus_{os.path.basename(TREE)}")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
sys.path.insert(0, TREE)

from engine import board as B  # noqa: E402
from engine import eval as E  # noqa: E402
import agent as A  # noqa: E402

PFENS = os.environ.get("PFENS", "results/leak_suite/fens.json")
BUDGET_MS = int(os.environ.get("PBUDGET_MS", "2600"))
TL = (BUDGET_MS - 500) * 45  # invert TM.budget = rem//45 + 500


def main():
    rows = json.load(open(PFENS))
    print(f"=== corpus probe [{TREE}] fens={len(rows)} budget={BUDGET_MS}ms ===")
    t0 = time.time()
    for i, r in enumerate(rows):
        fen = r["fen_before"]
        A._GAME_KEYS = []
        st = B.parse_fen(fen)
        sv = int(E.evaluate(st))
        mv = A.get_move(fen, TL)
        print(f"{i:4d} | {r.get('game', '?')[:22]:22s} | ply {r.get('ply', -1):3d} | "
              f"{r.get('san', '?'):7s} | pick={mv:6s} | static={sv:6d} | "
              f"eval_before={r.get('eval_before', 0):6d}",
              flush=True)
    print(f"=== done {len(rows)} rows in {time.time() - t0:.0f}s ===")


if __name__ == "__main__":
    main()
