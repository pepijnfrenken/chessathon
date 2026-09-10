# CHESSATHON AUDIT 2-A — SOUNDNESS HAWK — REPORT (final)

Auditor: adversarial compiler engineer / correctness hawk. Read-only audit.
Tree audited: HEAD `b320e3a` (engine byte-identical to shipped `49c4c0e`).
Environment: linux, probe python = /tmp/chessbench/bin/python (numba cache
warmed across probes). Report file: /tmp/chess-aud2-sound-report.md (this).

## Scope run (probes)
- probe1.py: perft (10 FENs incl. EP-pin, castling-gap, promotion, epmix)
  vs python-chess oracle; make/unmake zobrist key vs parse_fen over every
  legal move of 4 FENs; in-process fixed-depth determinism; deadline
  overshoot at 800/1500/3166 ms; agent-level game-history + edge FENs;
  root-return repetition pre-seed comparison; numba OOB behaviour.
- probe_det.py x2 fresh processes: cross-process fixed-depth determinism.
- probe2.py (running): corrected-EP key tests, EP game-history window,
  retry-guard semantics, root 3rd-occurrence refusal.

## FINDINGS (draft; fill severities/evidence as probes land)

### F1 [CONFIRMED by probe + orchestrator code-read — MAJOR, FIX PROVEN SAFE]
make_move_apply hashes a spurious piece removal on EP captures.
- Code path (engine/board.py make_move_apply): F_EP branch removes the
  captured pawn from its REAL square (`to∓16`) and XORs
  ZPIECE[real_sq, pawn] (line 239). `captured` stays non-EMPTY, so the
  generic cleanup XORed ZPIECE[to, captured+5] — a removal of a piece
  from square `to`, which was EMPTY before the capture. Net effect: every
  post-EP position's zobrist key differs from the same board parsed from
  FEN by exactly one term.
- IMPORTANT REFINEMENT (this audit): the naive fix "set captured = EMPTY
  in the F_EP branch" is WRONG — `captured` feeds the halfmove reset
  (line 246: EP is a capture) and unmake's pawn restoration (line 338).
  The correct minimal fix is to guard ONLY the key XOR:
      if captured != EMPTY and fl != F_EP:
          key ^= ZPIECE[to, captured + 5]
  This is what was applied and validated in the snapshot.
- Probe evidence (UNFIXED snapshot, probe_f1.py S1 — proves sensitivity):
  white fxe6 e.p. engine key 7eaaf7ed87d825bf vs parse f53ccad739f44d60;
  black exf3 e.p. ccd9f1031fd3188a vs c82198642273b4c1 → 2/2 EP positions
  MISMATCH (make/unmake roundtrip self-consistency held on both — the bug
  is key-divergence, not state corruption).
- Probe evidence (FIXED snapshot, probe_f1_fix.py):
  P1: 3 EP positions (white fxe6, black exf3, white cxd6) now match
      parse_fen exactly; 5 non-EP sanity moves (normal capture, promo
      capture, both castles, double push) still match. fails=0.
  P2: search from a pre-EP position (search_root d5, 6449 nodes): all 21
      root moves' recorded keys == parse_fen of the same position,
      including the EP capture the search plays. mismatches=0.
  P3: all 177 legal moves across 6 FENs (3 EP-rich, kiwipete, epmix):
      key == parse_fen for every move. mismatches=0.
  D1: determinism with fix — 3 positions x fixed-depth d8, fresh TT x2:
      byte-identical (mv, score, depth, nodes) on all, incl. an EP-rich
      position (f5e6/29/8/399510 twice).
  D2/D3 + full gate: tools/perft_check.py with fix = ALL PASS (published
  values to d4/d5, python-chess parity, move-type breakdowns incl. ep
  counts 46/2/4 at depth), plus 5 hand-picked tricky FENs (EP horizontal
  pin, castle-through-check, pawn-capture pin, promo+EP mix, EP vertical
  pin) — all parity.
- Regression risk, stated honestly: the fix changes EVERY post-EP
  zobrist key (that is the point). Parity probes + determinism + full
  perft gate above are the safety evidence; a full 24-game ladder-style
  gate before the 11 Sep freeze is the orchestrator's call.
- Root-rule impact (unchanged from draft): agent.py stores the engine
  key after each own move (_GAME_KEYS); after an EP capture that key was
  corrupted, so the NEXT get_move (clean parse key) never matched it →
  repetitions across an EP capture were invisible to anti-threefold.
  With the fix, the stored key equals the parse key (proven above), so
  the game-history window sees EP-created positions correctly.

### F2 [CONFIRMED — MINOR/INFO] 'gcnt=0 byte-identical to pre-Phase-4' claim is false
- search_root (search.py) writes rep[GAME_HIST] = st['key'][0] whenever it
  runs (line 567; verified present in the LIVE tree via inspect of the
  jitted source, not just the snapshot) — even when gcnt==0. _draw_score's
  step-2 parity scan then sees the ROOT key inside rep and scores any
  search-path RETURN to the root position as a repetition draw (0).
  Pre-Phase-4 behavior: that slot stayed zero, root-returning lines were
  scored normally.
- Fresh evidence (probe_f1.py S4, d8, fixed budget, identical TT state):
  startpos: shipped path best (b1a3, score 10, 143535 nodes) vs
  pre-Phase-4 emulation (fresh rep per root move, no root pre-seed)
  best (b1c3, score 10) — same SCORE, DIFFERENT MOVE.
  pos3: shipped (b4c4, 63, 100755 nodes) vs emulation (a5a6, 65).
- Assessment: the deviation is correct anti-repetition behavior (a line
  that revisits the root position IS a twofold-with-repetition-of-side
  and usually precedes a threefold), it only manifests on root-revisiting
  lines, and it is bounded (draw=0 score, not a wrong score). The gate
  claim "provably inert at gcnt=0" should be re-read as "inert on the
  tested gate position"; universally it is false. No action required;
  document as intended-behavior delta.

### F3 [CONFIRMED — MINOR] retry guard only checks _GAME_KEYS[-1]
- agent.py get_move dedupe compares the new root key only against the
  LAST appended key (the position after our previous move). A harness
  retry of the same FEN arrives AFTER we appended the post-move key, so
  the retry root is appended again: probe1 E1 — after call1 len=2, after
  same-FEN retry len=4 (guard_ok=False).
- Impact: retries inflate occurrence counts in the game-history window
  → a position occurring twice in-game can reach gcnt_occ>=2 early →
  the root may refuse (score 0) a move creating a '3rd' occurrence that
  is really only the 2nd. Narrow (needs harness retry + a position that
  recurs), self-corrects as the window rolls. Note the '-2-slot' fix is
  NOT obviously safe: an opponent move that undoes our move legitimately
  recreates _GAME_KEYS[-2]; deduping there would break genuine 2nd-
  occurrence counting. Current choice errs toward overcounting =
  conservative.

### F4 [CONFIRMED — INFO] check-extension can grow ply past MAX_PLY=64 with no protection
- search(): depth += 1 on every in-check node; consecutive checking lines
  keep depth from shrinking; scratch/killers/hist/rep are sized MAX_PLY=64.
- probe1 G: numba does NO bounds checking (a[64,0] returned 0 instead of
  raising) → ply >= 64 reads/writes past the scratch rows = silent memory
  corruption/noise in the search. Cannot produce an illegal move (root
  legality is re-checked and fallback exists), but could produce wrong
  scores/moves. Trigger needs 64+ consecutive checks without repeat
  (repetition usually cuts these lines earlier) — practically unreachable
  in ladder games; fix = clamp ply or size MAX_PLY=128.

### F5 [CONFIRMED — PASS] determinism
- In-process (fresh TT each run) fixed-depth d8 on 2 FENs: identical
  (mv, score, depth, nodes). Two fresh processes (probe_det): byte-
  identical hashes / the same quadruples on 3 FENs incl. startpos.

### F6 [CONFIRMED — PASS] deadline granularity
- search_root at 800/1500/3166 ms budgets: elapsed = budget +0..+2 ms.
  Node-entry check every 1024 nodes + iteration discard on timeout keeps
  overshoot <~3 ms on this box. The documented 4.9 s-vs-3.2 s replay
  overrun is NOT deadline granularity (consistent with the "machine
  artifact" attribution: replay-time JIT recompile).
### F7 [CONFIRMED — PASS] perft vs oracle (full gate rerun on FIXED snapshot)
- tools/perft_check.py with the F1 fix applied, fresh JIT cache:
  ALL PASS, three sections:
  1. published values: startpos d1-5 (4865609), kiwipete d1-5 (193690690,
     ~10.4 Mnps), pos3 d1-5, pos4 d1-4, pos5 d1-4, pos6 d1-4 — exact.
  2. python-chess parity d3 on all six positions — exact.
  3. move-type breakdowns (nodes/captures/ep/castles/promos/checks) d2-3
     vs python-chess — exact tuples, incl. kiwipete (97862, 17461, 46,
     3255, 0, 993) and pos4 EP=4/promo=168.
- Audit's own tricky FENs (probe_f1_det.py D3, vs python-chess):
  ep-horizontal-pin (8/8/8/K2pP2q/8/8/8/7k w - d6) d3 = 776 both —
  engine correctly EXCLUDES the EP capture along the pinned rank;
  castle-through-check (r3k2r/.../5q2/8/R3K2R) d3 = 15621 both;
  pawn-capture-pin family d4 = 6133 both; promo+EP mix (epmix) d3 =
  9483 both; EP vertical pin d4 = 5227 both.
- UNFIXED baseline (probe_f1.py S3) matched the same numbers: the fix
  changes keys only, never move legality.
- Probe-legality note (new, minor): the task-suggested probe line
  "1. e4 d5 2. e5 d4 3. exd6 e.p." is ILLEGAL by pin (the e5 pawn is
  pinned by the e8 queen; python-chess refuses the move). Any future
  key-parity probe must use pin-free EP lines (e.g. 1. f4 e6 2. f5 e5
  3. fxe6). Also: python-chess omits/normalizes the FEN ep field when no
  legal EP capture exists (status 512 = invalid ep square on naive
  fields) — EP test FENs must set the field to the square the
  double-pushed pawn passed AND guarantee at least one legal EP capture.

### F9 update — perft sections 1-3 above also close F9's open condition
  (no legality regression from the knight-capture qsearch fix): EP,
  promotion, castling breakdowns all exact on the fixed tree.

## VERDICT (final)

**Fix before freeze: F1 (one-line EP-hash fix, parity-proven).**

Rationale:
- F1 is a real soundness defect reachable in ANY game where an en-passant
  capture is played or searched: post-EP zobrist keys diverge from
  parse_fen truth. That silently defeats the Phase-4 anti-threefold
  game-history pre-seed across EP captures (the exact r54/r55 shuffle
  class it was built to stop) and mis-keys TT entries for post-EP
  subtrees. It is a one-line, mechanics-level fix.
- Safety evidence for the fix, all on the snapshot (fresh JIT cache):
  key parity P1/P2/P3 (3 EP positions + 177-move sweep + all root moves
  of a real search == parse_fen, 0 mismatches), determinism D1 (3
  positions, byte-identical quadruples), full perft gate
  tools/perft_check.py ALL PASS (published values, python-chess parity,
  breakdowns) + 5 tricky FENs. Unfixed snapshot reproduces the mismatch
  (2/2 EP positions), so the probe is sensitive.
- Residual risk: every post-EP key changes (that is the fix). Engine
  self-play strength is not re-measured here; a 24-game gate is the
  orchestrator's call before the 11 Sep freeze. The fix touches only
  make_move_apply's key XOR — no movegen, no eval, no search logic.

Not blocking freeze: F2 (document as intended-behavior delta, "provably
inert" wording retracted), F3 (conservative direction), F4 (practically
unreachable; optional MAX_PLY=128 hardening), F8 (policy tuning).
PASS: F5, F6, F7, F9.

Fix location: engine/board.py make_move_apply, generic captured-key XOR:
`if captured != EMPTY and fl != F_EP: key ^= ZPIECE[to, captured + 5]`.
Snapshot validation scripts: probe_f1.py (unfixed sanity + F2 probe),
probe_f1_fix.py (parity battery), probe_f1_det.py (determinism + perft
tricky FENs). Live repo is UNTOUCHED (read-only audit; fix exists only
in /tmp/chess-aud2-sound).