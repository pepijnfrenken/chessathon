# AUDIT 3 — Builder check (P7+P8 zobrist fixes, commit 73c7d44) — VERDICT: BUILDER VERIFIED

Target: verify builder round B4 did exactly what it claims. Live repo untouched (read-only).
Snapshot: /tmp/chess-aud3-builder (git archive HEAD = 08d4cb6), harness copy with ROOT repointed.
Python: /tmp/chessbench/bin/python. Fresh caches: /tmp/numba_cache_aud3, /tmp/numba_cache_epkey2.

## 1. Diff hygiene — CLEAN

`ca7dc96..HEAD` (= 73c7d44 + 08d4cb6), full change set verified:
- engine/board.py: +10 −2, exactly two hunks in make_move_apply, nothing else:
  - P7 (line ~255): `if captured != EMPTY:` → `if captured != EMPTY and fl != F_EP:` + 2 comment lines.
  - P8 (line ~297): `key ^= ZCASTLE[old] ^ ZCASTLE[castle]` → `key ^= ZCASTLE[old]` plus
    `if castle: key ^= ZCASTLE[castle]` + 4 comment lines.
- tools/probe_ep_key.py: new, 120 lines, no side effects on repo state.
- BUILD.md +8, PROCESS.md +28/−15: docs only.
- NO changes to eval weights, search params, agent.py, timings, or any other engine file.

Fix semantics checked against source: parse_fen (board.py:756-757) hashes ZCASTLE[c] only
`if c:` — the make-side fix mirrors this exactly (drop old unconditionally, add new only if
nonzero). P7 comment matches the code path (captured pawn removed at its real square, line ~239).

Probe verified NOT vacuous by inspection: 4 real EP games (white/black x kingside/queenside,
parity engine-key vs parse_fen truth) + control sweep of ALL legal moves of a KQ-rights
middlegame FEN — king moves there hit the castle->0 transition (P8 path).

## 2. Fresh-snapshot independent rerun — ALL PASS

- tools/probe_ep_key.py: 4/4 EP cases PASS, control sweep 38 moves parity OK, rc 0 (11.0s).
- builder_check.py (copy, ROOT repointed): determinism PASS (depth-6 x2 identical, best f1d3
  score 37); replay parity PASS 211 plies (r61+ r66 + r67 PGNs), rc 0 (46s).
- tools/perft_check.py: rc 0 — published refs d1-d5 OK (startpos 4865609, kiwipete 193690690),
  python-chess oracle depth-3 OK on all 6 positions, move-type breakdowns (EP/castle/promo/
  checks) byte-identical to python-chess on all 6.
- Smoke rc detail: agent warmup 48.1s < 60s init budget.

## 3. Probe sensitivity — probe FAILS on the unfixed tree (not vacuous)

With engine/board.py replaced by 73c7d44~1 (sha256-verified restore afterward; restored file
identical to HEAD: c36229c9...8d814):
- All 4 EP cases FAIL with distinct key divergences (P7 detected).
- Control sweep: exactly 2 FAILURES — e1d2 and e1e2, the two king moves that kill KQ->0
  (P8 detected). Remaining 36 control moves PASS, so failures are precisely the bug paths.
- rc 1 as designed.

## 4. Smoke (agent.get_move, time_left_ms=60000) — PASS

- castling-middlegame (r3k2r/... w KQkq): e3c5, legal, 3.1s.
- endgame (8/2p5/... w -: b4f4, legal, 1.8s.
- No exceptions. (Agent logged its usual "slow move 3142ms" warmup note; harmless.)

## Verdict: BUILDER-VERIFIED

Every claim in 73c7d44/08d4cb6 reproduced independently on a fresh snapshot with fresh JIT
caches: exact diff scope, probe ALL PASS, determinism, 211-ply replay parity, perft ALL PASS.
Probe demonstrably detects both bugs on the pre-fix tree. No hidden edits, no broken behavior.
