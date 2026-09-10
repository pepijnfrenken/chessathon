#!/usr/bin/env python3
"""q5-v8dp L2: leak-suite probe runner over an ARBITRARY tree (dev tool).

tools/leak_probe.py hardcodes the corpus path and engine import to its own
repo root, so it cannot probe a second tree against the SAME corpus. This
variant takes the tree root and the corpus path explicitly:

  python tools/leak_probe_tree.py <tag> <tree_root> <corpus.json> [budget_s]

It imports `engine` (board/search/tt) from <tree_root>, probes every row's
`fen_before` at the given per-move budget (default 2.6s = the real-clock
budget) and prints one line per row:

  <tag> <game> ply=<ply> vloss=<SF16 cp_loss> nodes=<n> score=<s>
        depth=<d> best=<uci>

`score` is search_root's return value = our-side (STM) POV; the row's SF16
`eval_before` is also our-side POV (see tools/refresh_leak_suite.py), so
the two are directly comparable. Move strings come from the tree's own
board.move_to_uci (authoritative; note tools/leak_probe.py's inline promo
map is off by one for Q/R promos). Rows are emitted in corpus order.
"""
import json
import os
import sys

import numpy as np


def main():
    tag, root, corpus = sys.argv[1], sys.argv[2], sys.argv[3]
    budget = float(sys.argv[4]) if len(sys.argv) > 4 else 2.6
    root = os.path.abspath(root)
    sys.path.insert(0, root)
    os.environ.setdefault("NUMBA_NUM_THREADS", "1")
    os.environ["NUMBA_CACHE_DIR"] = f"/tmp/numba_leak_{tag}"

    from engine import board as B
    from engine import search as S
    from engine import tt as TT

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
        mv, score, cd = S.search_root(
            st, nodes, S._NOW() + budget_ns, ttk, ttv, mask, killers, hist,
            rep, scratch, sscratch, 64,
            np.zeros(S.GAME_HIST, dtype=np.uint64), 0)
        return nodes[0], score, cd, B.move_to_uci(mv)

    import hashlib
    raw = open(corpus, "rb").read()
    rows = json.loads(raw)
    print(f"# tag={tag} root={root} corpus={corpus} "
          f"sha256={hashlib.sha256(raw).hexdigest()[:16]} rows={len(rows)} "
          f"budget_s={budget}", flush=True)
    # Warm the jitted path FIRST: search_root's numba compile costs far more
    # than one move budget, and the budget is computed before each call, so
    # without this the first corpus row would be searched with a budget
    # already consumed by compilation (nodes=0, score=-INF). Calling it on a
    # disposable board keeps the corpus rows unaffected (audit-6 §A16).
    one("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        int(0.2e9))
    for e in rows:
        n, sc, cd, uci = one(e["fen_before"], int(budget * 1e9))
        # `game` is the corpus key (no whitespace in the refresh tools'
        # naming); nothing is truncated and no field is space-padded, so the
        # log is machine-joinable on (game, ply) — audit-6 §A17.
        print(f"{tag} {e['game']} ply={int(e['ply'])} "
              f"vloss={int(e['cp_loss'])} nodes={n} score={sc} "
              f"depth={cd} best={uci}", flush=True)


if __name__ == "__main__":
    main()
