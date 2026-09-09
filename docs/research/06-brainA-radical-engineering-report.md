# Chess Brain-A — radical search/eval probes (Sep 8, before freeze Sep 11 11:00)

READ-ONLY research. Repo HEAD `73c7d44` + process commits (V5). All engine
claims verified by reading the shipped code; all numbers below measured this
session on the dev box with /tmp/chessbench/bin/python against the repo tree.

---

## 0. Engine state (what the probes must beat)

- Search: ID negamax, full-window root (aspiration reverted, D5), PVS,
  TT (64 MB = 2^22 × 16 B, 2-slot depth-preferred), null R=2 (guard:
  `not check and depth>=2 and ply>=1 and beta>0 and _count_nonpawns>=2`),
  LMR (quiet, depth>=3, i>=4, r=i//4 cap 2), check ext +1, qsearch
  (stand-pat + all captures MVV-LVA ordering, full evasions in check,
  QCAP=12, **no TT, no SEE, no pruning**), stateful anti-threefold.
- Eval: hand-tuned, 813-param layout (material frozen), gateable term
  groups; taper mg/eg by phase (N1/B1/R2/Q4, max 24); mate-drive term.
- Time: `remaining//45 + 500` ms, clamped [50 ms, 45 s], never-flag by
  geometric decay. Real budget curve: 120 s→3.16 s, 60 s→1.83 s,
  10 s→0.72 s per move.
- Measured this session (real budgets): r70-B position at 2.6 s budget =
  1.49 M nodes, depth 9, score −97; startpos at 3.2 s = 1.78 M nodes,
  depth 10. V5 own nps on the loaded box: 433–496 knps (BUILD.md Phase 4).
- Node budget vs TT: ~1.5–1.8 M nodes written per move into a 4.19 M-entry
  table → **each move churns ~35–45 % of the TT**. Games run 60–220 plies
  (r64 was 224 plies); late-move TT quality is low.
- Minor time-mgmt fidelity note (seen in `probe_v5_divergences.log`):
  at a 1 s budget the search ran 2.7 s (depth-7 finish past the
  1024-node check granularity). Harmless at 120 s clocks; relevant for any
  probe that touches budget policy.

## 1. The loss family (what actually loses games)

PGN material trajectories (computed from `results/matches/*.pgn`, diff in
our favor, per ply), cross-checked with PROCESS.md forensics and
`results/sims-v5/README.md`:

- **r64 (L, 224 plies, we are White):** +2 after winning the exchange at
  ply 33; grinds to +3 at ply 69; then a 14-ply heavy-piece transition
  (plies 76–90) flips **+3 → −2** (queen/rook scramble); we then sit at
  −1..−2 for ~90 plies unable to hold OR convert; final meltdown −5..−9
  from plies 181–192 (queen recaptured, two black promotions). PROCESS:
  "won position +1.5 leaked at ply 76 (fork), Q-endgame perpetual failed".
- **r68 (L, 78 plies, we are Black):** material even through ply 49; a
  12-ply queen-transition (plies 50–61) plunges **0 → −10** (their
  Nxf6 takes our queen; we recapture the knight, still −10); lost.
  PROCESS: "even at ply 49, −3 by 57, −10 by 65 — second material-leak
  loss — Q-ending transition".
- **r70 (L, 61 plies, we are Black):** material even; the a3/Na2/Qxb2
  skirmish (plies 15–23) leaves us **−2 pawns, no full piece**; from ply
  28 the game is the depth-instability case (Rb8@1s / c4@5s / Bg7@25s);
  the Rf5 hang at ply 58 (f8f5, "instant" TT-cached) seals it at −8.
  PROCESS Quirk 1: V5 *believed* the post-skirmish position ≈ −1 pawn
  (searched −92..−104, truth ≈ −250..−350).

**Pattern:** three losses, two mechanisms — (a) **material leakage in
heavy-piece transitions** (r64, r68; the tactical/horizon family), and
(b) **structural belief errors while lives are still on the board**
(r70; eval-skew + plan instability). Everything else (r61 hold, r62/r69
conversions) is verified-correct behavior (P1/P2/P4 resolution).

## 2. Quirk-1 root cause — measured, not guessed

Eval term decomposition of the r70-B position (the "knight down, −92..−104"
position), using the tuner's bit-parity feature extractor + hand params:

```
r4rk1/1p2pp1p/p2p1bp1/2pP4/7P/P2PP1P1/2R2PBN/5RK1 b  (sims position B)
  material     +220        (white up a knight for a pawn — TRUE edge)
  PST          −140 / −220 (white − black; black pawn PST alone +260)
  pawn_struct  −12 / −8
  mobility     −4 / −2     ← NOT the culprit (sims guessed mobility; wrong)
  kingsafety   −12 / −4
  bp+tempo     +10 / +10
  tapered total: +26 for WHITE  →  static eval = −26 for black
```

Per-piece PST deltas: black pawns **+260** (c5/d6/f6/g6 advanced phalanx),
white pawns +155, white knight h2 −40, rooks ±10, bishops ≈0.

So the skew mechanism is precise: **advanced-pawn PST credit at phase 11
(EG-taper, mostly endgame) nearly cancels a 220cp material edge**. The
search then sees −92..−104 (partially correcting via tactics), never the
−220..−320 truth. Mobility is innocent; the sims' audit guess should be
corrected in any follow-up.

Sanity contrast, position C (r70, before Kxh5): same +220 edge but the
decomposition reads −140 black because white's PST is only −35/−100 there
— the engine *correctly* knows it is lost (Quirk 3). The skew is
position-B-shaped (passive-vs-advanced placement + low phase), which is
exactly why it is a *compensation-calibration* bug, not a missing feature.

## 3. Probe menu

Common infra requirements (already in repo, reused by every probe):
`CHESSATHON_*` env toggles read at import (numba bakes globals; each A/B
side = its own process — `gate_match_tree.py` pattern with `--side-b-root`
snapshot), 24-game 500 ms gate + eg_check 8/8 + perft on every change,
real-clock confirmation via `local_game.py` at 120 s + 0.5 s (≈ 5–8
min/game; 16–24 games ≈ 1.5–3 h wall — treat as luxury, not default).

Regime rules learned by the project and applied below:
- Search-structure features (LMR precedent): discriminate at 500 ms gates.
- Eval changes: wash at 500 ms (Phase 2 0.479), show at real TC.
- Endgame/repetition-class features: pass eg-suites, fail 500 ms gates,
  correct at real TC (Phase 3.1 band 0.396–0.417 = known-null; 0.750 =
  the 05d0101-beating reference).
- Time/root-policy features: real-clock only.

---

### P1 — SEE-based capture pruning + ordering in qsearch  [`CHESSATHON_SEE=1`]
(a) **Idea.** Replace MVV-LVA-only qsearch ordering with a static exchange
evaluation, and prune captures with SEE < 0 when not in check (classical
SEE pruning; delta-pruning option `stand + victim + 100 ≤ alpha`). The
qsearch is the tactical safety net: it has no TT, no pruning, and its only
ordering is victim-value. A queen on f6 hangs into Nxf6 (r68) because the
transaction is seen only if the *whole* sequence fits the depth cap; SEE
sees the full recapture chain at every node and deletes losing captures
from the tree.
(b) **Why it attacks a documented weakness.** r64/r68 are the two
"material-leak in a heavy-piece transition" losses; both leaks are
12–14-ply queen/rook transactions. Phase-4's knight-capture fix
(`496b86a`, qsearch knight blindness) already proved qsearch horizon
errors are ladder-visible. SEE is the standard completion of that fix.
(c) **Implementation sketch.** New jitted `see(st, from_sq, to_sq)`
(0x88 attacker walk + least-valuable-attacker recursion, ~40 lines, our
own code) in `search.py`; in `qsearch`, non-check nodes: order captures by
SEE then MVV-LVA; skip `SEE < 0` captures (never in check); QCAP unchanged.
Separate sub-toggle `CHESSATHON_SEEPRUNE` so ordering and pruning can be
gated independently (ordering first: pure nps win, near-zero risk; then
pruning). Toggles at import, baked at compile.
(d) **Effort 5–6 h. Risk: MEDIUM** — qsearch value changes are global;
the Phase-3 audit proved silent qsearch bugs deafen the whole horizon.
Regressions would appear as (i) the 500 ms gate band, (ii) eg_check, (iii)
new **leak-suite** (below). Pass criteria must include the mate-drive
endgames staying 8/8 (SEE ordering must not reorder killing lines out of
view — order only *losing* captures down, keep best-response ordering).
(e) **Test regime: 500 ms gate PRIMARY** (qsearch behavior is TC-
independent; the Phase-4 knight fix gated exactly this way), + eg_check,
+ perft, + a new **leak-suite**: the r68 plies 50–61 FENs and r64 plies
76–90/181–183 FENs at 2.6 s budget — regression assert: post-fix search
must see the transition loss ≥2 plies earlier / not play the hanging
move. These FENs extract programmatically from the ladder PGNs (I used
`fen_at()` on `mainline_moves()`; parity: r64 white=odd plies, r68/r70
black=even plies).
(f) **Verdict: YES, top priority.** Highest expected Elo of the menu —
directly kills the loss family — and the ordering half alone (no prune)
is already a safe nps gain.

### P4 — dynamic null-move reduction (R=3 at depth ≥ 6)  [`CHESSATHON_NULLR=2|3|4`]
(a) **Idea.** NULL_R is a fixed 2 with a tight activation guard. At depth
≥ 6, deepen the reduction to 3 (optionally 4 at depth ≥ 9). This engine
is node-starved (1.5–1.8 M nodes/move ≈ depth 9–10 middlegame); every
reduction buys depth, and depth is the primary horizon-error killer.
(b) **Why now.** The LMR gate (Phase 3, 0.542) proved this engine's
branching is worth cutting; null R=2 is the conservative anchor, not the
optimum, for a 1-core engine with a thin eval. The `beta > 0` guard and
`_count_nonpawns >= 2` zugzwang guard stay — the endgame risk is already
boxed. Deeper null interacts with the skew (P8) only through depth, i.e.
favourably (deeper search partially corrects the −100 vs −220 gap).
(c) **Implementation sketch.** In `search()`, `r = NULL_R`; new global
`NULL_R_DEEP`; `if depth >= NULL_DEEP_MIN: r = NULL_R_DEEP` (default
NULL_DEEP_MIN=6, NULL_R_DEEP=3; env-gated). Three lines + globals.
(d) **Effort 2–3 h. Risk: LOW–MEDIUM** — bounded, local, reverted by
env var; eg_check guards the zugzwang family; the 500 ms gate measures.
(e) **Test regime: 500 ms gate PRIMARY** (search-structure changes
discriminate at short TC — LMR precedent), + eg_check + perft. One
real-clock confirmation handful of games.
(f) **Verdict: YES.** Best effort/risk ratio in the menu; a guaranteed
depth bump on the node-starved core.

### P2 — root-move stability / PV hysteresis  [`CHESSATHON_STABLE=1`]
(a) **Idea.** search_root currently adopts `iter_move` of every completed
iteration unconditionally — the last iteration always wins, so the
reported move flips with whatever the budget happened to complete (r70 p28:
Rb8@1s / c4@5s / Bg7@25s; r71 p16: Rg1 appeared at *no* tested budget —
the real box's nps picked it). Fix: carry the previous iteration's move;
adopt the new iteration's move only if it is (i) the same move, or (ii)
its score exceeds the incumbent by `STABILITY_MARGIN` (10–20 cp), or
(iii) it is a mate score. Effect: play is a *stable* function of the
position, not of the host's nps — the exact Quirk-2 complaint, which the
sims flagged as "fix direction = root-move stability, not eval".
(b) **Evidence.** sims README Quirk 2 (all of it), plus the divergence
probe reproduces the flips at 1/5/25 s. r71's Rg1 "at NO budget" proves
environment-dependent personality — this probe is the direct fix.
(c) **Implementation sketch.** In `search_root`, previous `best_move` /
`best_score` from the last completed depth; hysteresis compare in the
depth loop; the anti-shuffle effective-score logic already lives in
`_root_iter` and is untouched. Optional half (separate toggle): a
hard-convergence early stop (`move unchanged for N iterations` → stop)
is NOT recommended yet — with no budget re-allocation it just wastes
time; ship hysteresis only.
(d) **Effort 4–6 h (the hysteresis rule + margin need A/B tuning). Risk:
MEDIUM** — a real late breakthrough can be delayed one iteration when its
score jump is under the margin; worst case is a one-iteration lag, not a
hard error. The margin is the only free parameter; sweep 8/12/16/24 cp on
the 500 ms gate.
(e) **Test regime: 500 ms gate PRIMARY + real-clock confirmation.**
Flips reproduce at 1 s (probes), so the gate sees them; the r70 p28
sweep becomes a PASS assertion (no flip at ≥ 5 s budgets within ± 20 cp).
Real-clock: 8–16 games via local_game.py to confirm no stagnation
personality appears.
(f) **Verdict: YES.** Fixes the reproducibility defect (the thing that
makes ladder replays diverge) and removes nps-lottery moves; second-tier
upside vs P1, but the highest *robustness* gain.

### P3 — TT enlargement to 256 MB (2^24)  [`CHESSATHON_TT_MB=256|512`]
(a) **Idea.** 64 MB / 4.19 M entries with ~1.5–1.8 M nodes written per
move = ~40 % churn per move, worse late game. 2^24 = 16.7 M entries
(268 MB) or 2^25 (537 MB) cuts churn to ~10 % / ~5 %.
(b) **Why.** Depth-instability and midgame quality both degrade when the
previous iteration's bounds are evicted mid-game; the sims' "TT thrash at
~2 M nodes/move on 64 MB" is documented in the brief. Search results
(nodes/depth) stay identical until a hit rate change — it's a pure
capacity probe, zero eval/search semantics change.
(c) **Implementation sketch.** `TT.make(n)` already takes the count; the
caller (`agent.py`) passes the constant. Check `tt._idx` shift constants
(the two slots use key-shift + mask — shifts must scale with the larger
mask to keep slots decorrelated). Both keys/vals arrays are uint64; mask
math (`np.uint64(len-1)`) unchanged. Env toggle at import.
(d) **Effort 1–2 h. Risk: VERY LOW** (memory: 268 MB table + process
~200–400 MB peak — measure peak RSS in the gate; 2 GB box is safe; test
512 MB variant with `ru_maxrss` before committing to it).
(e) **Test regime: real-clock PRIMARY** (churn only matters at real node
counts; at 500 ms the table never thrashes) + 500 ms null-check for
regression. Cheap: reuse the r70-B 2.6 s probe and compare nodes/depth/
score at 64 vs 256 MB.
(f) **Verdict: YES as a cheap insurance probe.** Expected Elo gain modest
but the cost is ~1 h and near-zero risk; pair it with P1/P4 week if time.

### P5 — aspiration windows with *widening* re-search at real TC  [`CHESSATHON_ASP=1`]
(a) **Idea.** Phase-3 retest, not a new idea: full-window root + window
[prev−40, prev+40] from depth 2; on fail-low/high re-search with delta
doubling (40→80→160) instead of one full-window jump, plus a budget
guard: if time remaining < 15 % of the move budget → full window (the
Phase-3 failure mode was re-search burning the budget at 500 ms).
(b) **Why.** D5/§5#3: the rejection was measured at 500 ms where the
re-search is the whole budget; at 3.2 s the amortization is 10× better.
Sanctioned follow-up, code pattern already existed (reverted cleanly).
(c) **Implementation sketch.** Re-add `_root_iter` window param from the
reverted commit `f621ba1` (git history holds it), change the re-search
from full-window to widening, add the time guard. Toggle env-gated.
(d) **Effort 3–4 h. Risk: LOW–MEDIUM** (revertable; fixed-depth parity
must be re-proven byte-exact like Phase 3 did).
(e) **Test regime: real-clock ONLY** (settled-negative regime at 500 ms)
+ fixed-depth parity. 16–24 games ≈ 2 h wall.
(f) **Verdict: maybe.** Cheapest "second spin" of a documented idea;
run only if real-clock sim infrastructure is already warm.

### P6 — volatile-score time-spending  [`CHESSATHON_VOLATILE=1`]
(a) **Idea.** Budget is a fixed curve. When the last completed
iterations disagree (move or score swing > 40 cp), spend ×1.5 next move
(within existing never-flag clamps); when rock-stable, spend ×0.8 and
bank. Spends where the position is sharp, saves where it is not.
(b) **Why.** Quirk 2: instability *is* the signal that the move needs
more depth; today the engine spends the same 2.6–3.2 s on a dead-even
Ruy Lopez and on a queen-in-the-middle mess. The sims recorded V5 with
66.8 s unused in r70 — the banked time exists.
(c) **Implementation sketch.** search_root returns per-iteration
(best_move, score) history (small return addition); agent.py computes the
volatility signal from the last 3 iterations of the *previous* move and
scales next `budget_ms`; time.py clamps stay authoritative (never-flag
invariant is the shipped guarantee — do not touch its math, only its
input). Toggle env.
(d) **Effort 4–5 h. Risk: MEDIUM-LOW** — budget changes are isolated but
flag risk is the safety property; must be proven at BOTH clock shapes
(120 s+0.5 s and the 2 s+0.1 s harness shape).
(e) **Test regime: real-clock ONLY** + a flag-fuzz at the 2 s harness
shape. 16–24 games ≈ 2 h.
(f) **Verdict: defer.** The signal only means something once the
stability probe (P2) defines the baseline; run after P2 lands.

### P7 — pondering by idle TT-fill  [no env toggle; agent.py thread]
(a) **Idea.** The box allows own-core after get_move returns. Spawn a
background thread that keeps searching the *current* position (deepening
from where the move search stopped, sharing the module-level TT), and
kill it (deadline = now) the instant the next get_move arrives. No move
is committed — the bonus depth just re-seeds the table. The next move's
search then starts several plies deeper for free.
(b) **Why.** §5#2 (stored since Phase 4); the opponents burn 5–20 s
(ladder clocks: r70's opponent 7–20 s opening burn); every 2–3 s of
pondering ≈ +1 depth on our next move. On a node-starved engine this is
the cheapest depth money can buy.
(c) **Implementation sketch.** agent.py: `threading.Thread` +
`search_root(nodes=0, deadline=“until stop”)` on a *copy* state (the
thread must NOT mutate the live `st` — it gets its own parse_fen state,
shares only TT/globals); a stop event sets deadline=now; get_move
releases it before parsing. numba is not thread-safe for concurrent
compilation — the ponder search must re-use already-compiled functions
(always true post-warmup). Watch TT growth: 64 MB default is fine, but
do NOT combine with P3-512 MB without measuring memory under the
checker's 2 GB.
(d) **Effort 4–6 h + harness time. Risk: MEDIUM** — threading near the
freeze + the harness must be extended (an opponent that actually waits,
so our ponder window is real: local_game.py with base 120000/inc 500
already does that).
(e) **Test regime: real-clock ONLY.**
(f) **Verdict: defer (see §4).** Highest *ceiling* of the menu but the
most moving parts and the closest to the freeze; it must not land the
day before upload.

### P8 — eval compensation fixed-point audit  [tools/fixedpoint_eval.py]
(a) **Idea.** A regression harness, then (only if the harness passes)
one surgical term fix. The harness: ~20 hand-picked FENs from OUR ladder
(r70-B, r64 plies 76–90 and 181–183, r68 plies 55–61, plus clean
knight-down baselines and true-compensation cases); assert
`|static_eval − material| ≤ 120 cp` whenever `|material| ≥ 200 cp` and
phase ≤ 16 (the regime measured in §2). The decomposition script I used
(texel feature_vector + hand params, per-group printout) IS the audit
tool — it exists and runs.
(b) **Why.** The measured mechanism (§2) is a calibration defect: black's
advanced-pawn PST (+260 cp at phase 11) cancels a real 220 cp material
edge; the static reads −26 where truth is −220..−320. r70's loss was
played "believing" near-equal. NOT a retune (Phase-2 lesson: tuning is a
settled negative); this is a fixed-point check on a specific term class.
(c) **Implementation sketch.** Tools-only first (no eval change): the
harness + per-group decomposition on every member FEN, committed to
results/. Then, if the band fails, one candidate fix (e.g. reduce the
advanced-rank pawn PST credit when the side is ≥ 1 minor down and phase
≤ 16 — a compensation-aware clamp), gated by env toggle, measured by the
harness + 500 ms gate.
(d) **Effort 5–6 h (harness 2–3 h, fix candidate 2–3 h). Risk: MEDIUM**
(eval changes wash at 500 ms — the gate may say null even when the
harness says fixed; the real-clock sims decide).
(e) **Test regime: fixed-point harness + 500 ms gate + real-clock
confirmation.** Regime-neutral but historically noisy; the harness is the
deliverable.
(f) **Verdict: build the harness now, defer the term fix.** The harness
is cheap, permanent, and makes every future eval probe honest.

---

## 4. TOP-3 for this week (each ≤ 6 h, ranked by Elo×1/risk×fits)

1. **P4 — dynamic null-move R (2→3 at depth ≥ 6).** ~2–3 h, 500 ms gate.
   Depth on a node-starved engine is the cheapest correct gain; smallest
   blast radius of any probe; the LMR gate is the proof the 500 ms gate
   discriminates this class.
2. **P1 — SEE ordering first, then SEE pruning in qsearch.** ~5–6 h,
   500 ms gate + eg_check + leak-suite. Directly attacks the r64/r68
   loss mechanism (the only losses besides r70); ordering half alone is a
   safe intermediate ship.
3. **P2 — root-move stability/hysteresis.** ~4–6 h, sweep STABILITY_MARGIN
   8–24 cp on the 500 ms gate + r70 p28 replay assertion. Kills the
   nps-lottery personality (Quirk 2); makes every ladder replay
   reproducible, which is the project's own evidence standard.
   *If the week tightens: run P3 (TT 256 MB, ~1 h) before P2 — it is the
   nearly-free insurance.*

Deferral logic (ONLY after the above weak spots are proven fixed):
- **P7 (pondering)** — the ceiling play; must land with ≥ 24 h of
  buffer, a harness extension, and a memory check. Revisit after P1+P2
  show the core is tactically sound (banking depth into a leaky search
  is wasted depth).
- **P6 (volatility time-spend)** — the signal is meaningless until P2
  defines stability; also flag-safety must be proven at both clock
  shapes, which costs 2 h of wall it doesn't deserve this week.
  (P8's harness is NOT deferred — build it as part of P1's leak-suite
  infrastructure; the term fix itself waits.)

## 5. One-line verdicts

P4 now (safe depth) · P1 now (kill the loss family) · P2 now (stable
personality) · P3 if a free hour exists · P5 when real-clock sim infra is
warm · P6/P7 after the core is proven fixed · P8 harness now, fix later.