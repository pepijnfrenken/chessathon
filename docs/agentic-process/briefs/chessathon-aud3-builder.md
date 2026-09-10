# AUDIT 3 — BUILDER CHECK (small, read-only): verify the P7+P8 key fixes

## Context
Builder round B4 (commit `73c7d44` on `master`) applied two zobrist key
fixes to `/home/pino/projects/chessathon/engine/board.py`:

- **P7** (audit 2-A F1, EP): guard `fl != F_EP` on the captured-piece key
  removal — EP captures previously XORed a phantom ZPIECE[to].
- **P8** (found by the builder's probe, missed by audit 2-A): when the last
  castling right dies (castle -> 0) make previously XORed
  `ZCASTLE[old]^ZCASTLE[new]` where ZCASTLE[0] is random and parse_fen
  never hashes it — now it XORs ZCASTLE[old] and only adds ZCASTLE[new]
  when nonzero.

Plus `tools/probe_ep_key.py` (parity regression probe) and doc commits
(`08d4cb6`). A 24-game gate is running on the live tree (D11) — NOT your
job; it measures strength. Your job: verify the BUILDER did not lie,
break anything, or hide anything.

## Your tasks
1. **Diff hygiene**: `git -C /home/pino/projects/chessathon show 73c7d44`
   and `08d4cb6`. Verify: exactly the two guard changes + comment lines in
   `engine/board.py` (nothing else changed in that file or any other engine
   file), the probe file is new, no sneaky edits (eval weights, search
   params, agent.py, timings). Report anything unexpected.
2. **Fresh-snapshot independent rerun**: `git archive` HEAD into
   `/tmp/chess-aud3-builder` (repo is at /home/pino/projects/chessathon),
   then with `NUMBA_CACHE_DIR=/tmp/numba_cache_aud3` (FRESH — the live
   repo caches compiled board.py from the fixed code; your own cache must
   also be fresh) run:
   - `tools/probe_ep_key.py` (expect ALL PASS — 4 EP cases + 38-move
     control sweep)
   - determinism + replay parity: `/tmp/builder_check.py` (copy it into
     your snapshot; it needs results/matches/*.pgn — copy those too)
   - `tools/perft_check.py` (expect rc 0)
3. **Probe sensitivity (prove the probe detects the bugs)**: in your
   snapshot, `git checkout 73c7d44~1 -- engine/board.py` (the UNFIXED
   file), fresh numba cache, run `tools/probe_ep_key.py` — it MUST report
   FAILURES (EP cases and/or control). Then restore HEAD. This proves the
   probe is not vacuously passing.
4. **Smoke**: import `agent.py` from the snapshot root and call
   `get_move` on 2 FENs (one with castling rights, one endgame) with
   time_left_ms=60000; assert legal UCI output, no exceptions. (agent.py
   warmup ~45s — budget for it.)
5. **Verdict**: builder-verified or not, with the numbers. Keep the repo
   read-only; all work in /tmp/chess-aud3-builder. If a probe contradicts
   the builder's claims, dig until you can say exactly which claim is
   wrong and why.

## Rules
- Read-only on /home/pino/projects/chessathon — NO commits, NO pushes.
- `PY=/tmp/chessbench/bin/python`. Per-process JIT warmup ~10-45s — batch.
- Provider hiccups: wait + retry; on 3 consecutive empty responses, write
  your partial findings to the report and stop.
- Final summary in-session; keep a report file at
  `/tmp/chess-aud3-builder-report.md` updated as you go. Time budget ~1h.

<!-- source session: 2026-09-08T14-31-26-498Z_01a0816e -->
