# chess-q5 — SHIP-GATE AUDIT, round 2 (resume) — 2026-09-09 ~12:30 UTC

Auditor: q5-audit2b (independent, read-only). Scope: tools/quality_ab.py as
standing ship gate (PROCESS.md §10) + its first two verdicts (SEEPRUNE
NULL, NULL_DEEP NEGATIVE). Snapshot /tmp/chess-q5-audit2/ re-archived from
HEAD (9195058) before check batches. Repo untouched. Budget ~45 min used.

Carryover from the killed q5-audit2 run: items 1-5 re-confirmed; item 6
(the r70 ply verification + referee identity) finished here.

## 0. Verified facts (carryover confirmations + new)

- Tool state: `git diff 051a2cf HEAD -- tools/quality_ab.py` is EMPTY;
  between evidence commit 84815a4 and HEAD only docs/PROCESS changed. The
  bytes that produced the A/B evidence are the bytes at HEAD.
- Referee identity: ONE binary and ONE code path for both sides of every
  A/B. V5 rows come from cached `results/leak_reviews/<game>.sf16.json`
  (written 07:15-07:29 by review_sf.py); candidate replay rows are
  generated fresh by the same tools/review_sf.py (unchanged since commit
  0119923, 07:04 — before all evidence). Binary = ~/.local/bin/stockfish,
  "Stockfish 19". No asymmetry.
- NULL_DEEP code: engine/search.py:587-590 swaps R=2→3 at depth ≥
  NULL_DEEP_MIN(6) inside the identical guard set. Toggle mechanics as
  claimed.
- Replay/means structure: aggregate candidate mean 845.0 = Σ(mean·n)/Σn
  over n=70 moves; r70 contributes 1924.8×30 = 97.6% of the total. V5
  mean 768.1 is over n=378 whole-game moves. The two means are computed
  over non-comparable move populations (see F1, F7).
- EMPIRICAL RERUN (question E): NULL_DEEP r70 rerun through the tool at
  HEAD (snapshot tree, fresh NUMBA_CACHE_DIR, quiet box, 192 s):
  - cand mean 1956.7 vs committed 1924.8 → +1.7%, inside ±10%. REPRODUCES
    at the aggregate level.
  - Leak classification identical: retained 1 / avoided 0 / replaced-worse 0.
  - Fidelity 23/30 vs committed 25/30; move-level identity does NOT
    reproduce: this run collapsed via h6?? (28483), Ne6?? (28604), g4??
    (28490) instead of f6?? (27870) + fxg5 (28213). The mate-clamp
    blunder class recurs; the individual moves are real-clock-timing
    dice (consistent with QUALITY_AB.md LIMITS #3).

## 1. Findings

### F1 — HIGH — Aggregate "mean cp_loss" is dominated by SF19 mate-clamp discontinuities; the 845-vs-768 number is mostly artifact
- Mechanism: review_sf.py `_sf_eval` clamps mate scores to ±30000 with
  |m|·100 steps. Once a forced-mate line exists, cp_loss jumps to
  ~28000-29900 for the side being mated REGARDLESS of the move played.
  V5's own fxg5 at ply 52 of the real r70 game scores 0 ("best"); the
  same capture idea in the candidate's diverged replay scores 28213
  ("blunder") purely because evals sit inside the clamp region.
- Evidence: of the V5 corpus total (290,347 cp over 378 moves), moves
  ≥20000 cp contribute 81.5% (9 moves) and ≥1000 cp contribute 93.4%
  (14 moves). In the candidate's r70 total, two clamp entries are 97.1%.
  The "mean" compares ~14 clamp events (V5, whole games) vs ~5 (cand,
  mostly one game) — a clamp-event count ratio, not a quality metric.
- Repro: jq/python over results/leak_reviews/*.sf16.json and
  results/quality_ab/ab-nulldeep/*.replay.sf16.json; totals above.
- Fix: report clamp-robust statistics alongside raw mean: winsorize
  cp_loss (e.g. cap 1000) and/or report median; classify mate-region
  moves separately ("mated-side", not "blunder"); never let raw mean
  alone fire mean_not_worse. ~10-line change in quality_ab.py stats().

### F2 — HIGH — On this box the gate's first PASS condition (leaks avoided ≥1) is structurally near-vacuous
- Mechanism: "avoided" counts only V5 leaks faced PRE-DIVERGENCE. Replay
  prefixes are short everywhere: in the nulldeep run, V5's 51 corpus
  leaks — only 2 were faced (r70 Nb4, r71 Qg3, both retained); 6 of 7
  games diverge at our-move k=1-3. A real candidate build will also
  diverge within a few moves (ID-completion timing, LIMITS #3), so the
  reachable leak pool is ~2 plies. `avoided ≥1` fires only if the
  candidate happens to dodge one of ~2 reachable leaks — a coin flip,
  not a capability measurement.
- Consequence: a genuinely improved candidate has maybe ~50% chance of
  collecting its one "avoided", independent of strength. PASS is a
  lottery ticket; WEAK/FAIL is the default regardless of quality.
  QUALITY_AB.md documents that HEAD self-tests are "WEAK by
  construction" but does NOT state that real candidates hit the same
  wall.
- Repro: per-game faced-leak table (nulldeep): r64 0/12, r68 0/9, r70
  1/5, r74 0/11, r71 1/5, r72 0/5, r73 0/4 (faced/total).
- Fix: print faced/total denominators next to retained/avoided/
  replaced-worse; extend prefix coverage (multi-run replays with
  deliberate early divergence branches, or fixed-position leak probes —
  the leak-suite FENs from bb51872 are the right instrument for "does
  the candidate still leak here").

### F3 — HIGH (record integrity) — PROCESS §10 / commit 84815a4 narrative misattributes OPPONENT moves to the candidate
- Mechanism: the sf16 JSONs contain both sides; the narrative plucked
  plies without filtering side=black.
- Verified: "fxg5 28113" is ply 51 (side=white — KingsGuard's move);
  "Bf5 28878" is ply 59 (side=white). The candidate's actual black-side
  clamp blunders in the committed replay are f6 (27870, ply 50) and
  fxg5 (28213, ply 52); there is no "Bf5" candidate move at all (the
  game's ply-58 Rf5 was answered by the candidate with Rxe6).
- Repro: `jq '.[] | select(.ply==51 or .ply==59)' results/quality_ab/
  ab-nulldeep/round-70-vs-kingsguard.replay.sf16.json` → side "white".
- Fix: amend PROCESS §10 wording (f6?? 27870 + fxg5 28213 only) and the
  eventual audit trail. The causal story still needs F4's correction
  before it explains anything.

### F4 — MEDIUM — The "R=3 skips the refutation horizon" causal story is NOT established by this evidence
- (a) Shared-prefix control: on the 11 moves before the first divergence
  (identical positions), candidate and V5 are indistinguishable (means
  52.3 vs 52.6). The toggle demonstrably does nothing bad there.
- (b) V5 itself walked into the same mating attack IN THE REAL GAME:
  black's f6?? (28129) at ply 50 is in the leak_reviews baseline; the
  real r70 game ended in checkmate against V5 (Result 1-0, Termination
  checkmate). "Only the candidate collapses into mating attacks" is
  false — the ladder game being replayed is already a mating-attack
  collapse by V5.
- (c) The candidate's extra clamp loss (fxg5 28213 vs V5's 0 for the
  same conceptual capture) is a referee-region artifact of its diverged
  position path, not evidence of a deeper-null horizon miss.
- (d) Rerun instability (h6??/g4?? vs f6??) shows the specific "mechanism
  on tape" is one sample of a real-clock-timing distribution, not a
  deterministic R=3 signature.
- What survives: NULL_DEEP produced NO detectable improvement at real
  clocks and one full-game replay whose clamp-bugget count (2) exceeded
  V5's in the same game (1... plus real-game blunders 3 total). What
  does not survive: "confirmed and amplified NEGATIVE" as a mechanism
  claim.
- Fix: reframe §10 NULL_DEEP entry as "no real-clock evidence of
  benefit; single-game negative signal is clamp-dominated"; if the
  question matters, re-run with the F4-fixed metric (paired prefix +
  trimmed means) across several real-clock replays.

### F5 — MEDIUM-HIGH — The gate as-is can judge in BOTH wrong directions
- PASS a harmful change: 6 of 7 corpus games contribute only 0-11
  candidate moves, all opening theory (per-game cand means 11.6-68.2,
  max 243) — middlegame/endgame regressions are invisible there. The
  no_more_blunders check compares candidate b+m over n=70 (opening-
  heavy) vs V5 b+m over n=378 (whole games, complex positions) —
  populations so different that the check is biased in the candidate's
  favor. A change that only breaks post-opening play could go 4/4.
- FAIL a helpful change: demonstrated by the NULL_DEEP evidence itself —
  on any clamp-robust basis the committed r70 data flips direction:
  - r70 paired full game, trimmed (<1000 cp): V5 80.4 (n=29) vs cand
    59.3 (n=28), Welch t=0.53 — n.s.
  - r70 full raw: V5 1015.4 vs cand 1924.8, Welch t=-0.57 — n.s.
  - corpus trimmed means: cand 45.1 (n=68) vs V5 53.0 (n=364).
  Neither direction is statistically distinguishable; the committed
  "NEGATIVE" is carried by clamp entries and a one-game qualitative
  story.
- Fix: same as F1/F2 plus paired-prefix comparison restricted to
  identical positions; treat post-divergence standalone scores as
  anecdote (they referee Frankenstein games where the opponent replays
  scripted moves — documented in LIMITS #1 but §10's verdict leaned on
  exactly that regime).

### F6 — LOW — 845-vs-768 is not a statistical claim and was never going to be
- 378 vs 70 unmatched moves, r70 = 97.6% of the candidate total, single
  replay per toggle. No test rescues this; the tool's own doc says
  "read the numbers" — but these numbers need the F1/F5 fixes first.
- Fix: drop aggregate mean from verdict inputs until paired/robust
  stats exist; keep per-leak entries (they are the honest part).

### F7 — LOW (ops) — Read-only discipline hazard in load_real_review
- If a corpus game lacks a cached leak review, quality_ab WRITES
  `<name>.sf16.json` into the repo's results/leak_reviews/ (and for
  --candidate <sha> runs, REPO is still the live repo because REPO is
  tool-relative). For the standard 7-game d16 corpus all caches exist,
  so runs so far were read-only in practice. New games or --sf-depth
  changes will write.
- Fix: none urgent; document "prefetch reviews before read-only runs".

### F8 — INFO — SEEPRUNE "NULL" = no-evidence, and that is fine
- Confirmed: exactly ONE V5 leak was faced pre-divergence in the whole
  seeprune run (r71 Qg3 243→275, retained). "Retained 1 / avoided 0 /
  replaced-worse 0 / mean 55.7" is a NULL RESULT in the experimental
  sense — the instrument had essentially nothing to measure. It neither
  incriminates nor clears SEEPRUNE at real clocks. The real evidence
  for keeping it OFF is the 500ms gate (0.458), not this run.

### F9 — INFO — Instrument mechanics are trustworthy
- Replay worker: exact-clock extraction, k-index leak alignment,
  PGN/FEN handling, review caching — all verified in code and by the
  self-test signature (retained-but-never-avoided on HEAD, matched
  prefix means 52.3 vs 52.6). The rerun reproduces the committed
  aggregate within 1.7% and the leak counts exactly. The problems in
  F1-F6 are instrument DESIGN (what is measured and compared), not
  implementation bugs, with F3 the one record-accuracy exception.

## 2. Question D — gate soundness + minimum honest evidence standard

Can "leaks avoided ≥1" ever fire meaningfully? See F2: on this box, only
by luck (~2 reachable leaks corpus-wide). Is there a regime where the
gate PASSes harm or FAILs help? Yes, both (F5), and the NULL_DEEP
verdict is itself the FAIL-help demonstration. Documented as limits?
Partially (LIMITS #1/#2/#5 graze it); the clamp dominance (F1),
population asymmetry (F5) and the faced-leak denominator (F2) are NOT
documented anywhere.

Recommended minimum evidence standard for a ship decision (decision-ready
for the next builder round; freeze 2026-09-11 11:00 UTC):

- L1 (always, engine changes): existing 24-game @500ms self-play gate +
  60s init + perft/shuffle suites. This stays the only controlled-
  statistics instrument.
- L2 (always, engine changes): leak-suite FEN probes (bb51872 set):
  does the change move the referee's eval/choice on the ACTUAL leak
  positions? Deterministic, cheap, directly aimed at the leak family.
- L3 (real clocks, any candidate that passes L1+L2): SF19 real-clock
  bout vs the external SF harness (run_vs_stockfish) — read W/D/L, not
  a single number.
- L4 (supporting only): quality_ab replay A/B — after applying fixes
  (a) winsorized/median cp_loss in stats(), (b) paired shared-prefix
  deltas per game, (c) faced/total denominators printed, (d) our-side
  filtering discipline in any narrative. Interpretation aid and
  mechanism finder; NEVER the deciding vote. A FAIL that survives
  clamp-exclusion is a real red flag; a PASS alone never ships.
- Ship rule: ship iff L1 positive ∧ L2 non-regressive ∧ L3 not worse ∧
  L4 shows no clamp-excluded regression. The PASS/WEAK/FAIL label is
  advisory in all cases.

Cheap pre-freeze tool patch worth doing (small, low-risk): (a)+(c)+(d)
above, then re-run the two A/Bs so PROCESS carries trimmed means. Not
blocking.

## 3. Verdicts

Ship gate: **"gate needs clamp-robust scoring, paired shared-prefix
comparison, faced-leak denominators, and independent confirmation (L1
500ms gate + L2 leak-FEN probes + L3 real-clock bout) before it judges a
real change" — it is NOT "TRUSTWORTHY for candidate A/B" as a deciding
instrument today.** Its mechanics are sound (F9); its decision metrics
are not (F1/F2/F5).

Toggle conclusions:
- SEEPRUNE "NULL": stands only as "no evidence either way at real
  clocks" (one faced leak, F8). Stays OFF on the 500ms gate's null —
  correct conclusion, quality_ab added nothing.
- NULL_DEEP "NEGATIVE": **does not stand as stated.** The 845-vs-768
  real-clock "confirmation and amplification" is clamp-dominated (F1),
  the narrative misattributes two opponent moves (F3), the mechanism
  story is contradicted by V5's identical real-game collapse (F4), and
  the single-replay path is timing-unstable (rerun: different blunder
  moves, same class). Stays OFF on the 500ms gate's 0.438 — but the
  quality_ab leg of the negative is retracted as evidence.

Upload-blocking: nothing. Ship state (all toggles OFF, V5) is unchanged
and remains the best-supported build; the record corrections (F3, F4)
should be appended to PROCESS §10 by the builders.
