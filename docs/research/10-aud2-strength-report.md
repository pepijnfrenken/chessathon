# AUDIT 2-B — STRENGTH SKEPTIC — report (working, updated as evidence lands)

## Environment / rules compliance
- Read ORIGINALITY.md first (repo law). Read-only audit: working tree untouched;
  all work on snapshot `/tmp/chess-aud2-strength` (git archive HEAD @ `b320e3a`,
  engine files = shipped `49c4c0e` per audit brief).
- Probes run with `/tmp/chessbench/bin/python` (python-chess 1.11.2, numba 0.67.0).
  Each fresh process ≈ 45–50 s JIT warmup — probes batched.

---

## 1. The r64 loss — verdict with evidence

**Game shape** (PGN + replay): r64 vs Snake, we were White, start from a set
FEN at move 8, lost by checkmate at ply 224 (112 moves). No flag, no illegal
move. Clock profile: we averaged 1.41 s/move (vs 2.0–2.8 s in the other four
rounds) because the game ran 112 of our moves — time management tracked
budget the whole game (see §2).

**Material timeline around the decisive phase** (replayed from PGN):

| after ply | move | material (P=1,N=B=3,R=5,Q=9) | position |
|---|---|---|---|
| 85 | 49.Rxc3 | W22 B20 (we just won a piece back) | sharp |
| 86 | 49...Bd3?? no — 49...Qxa2? see PGN: 49...Bd3 | W17 B20 | we dropped 5 |
| 87 | 51.Qxa5 (queen taken!) | **W17 B11** | **we are +6** |
| 88 | 51...Bxe4 | W14 B11 | +3 |
| 89 | 52.fxe4 | W14 B8 | **+6 again** |
| 90 | 52...e1=Q | W14 B16 | **−2 (Q+R vs Q+3P)** |

Correction of my own earlier reading: the engine won the enemy QUEEN at ply 87
(51.Qxa5) and was material-up (+6 after 52.fxe4) *despite* the earlier
Rh3/Nxh3 exchange loss. The game only turned lost when Black promoted
(52...e1=Q, ply 90) because White never stopped the e-pawn while chasing
checks.

**Was Rh3/Kh2 a "search-depth artifact of the fast clock"?** Probe evidence
(engine = shipped build, budgets from the real %clk):

- Position before 45.Kh2 (ply-74 label in probe = after 44...Nf2+): budget
  1.52 s → best **h1h2 (Kh2!) score +126 depth 8**. At 3× budget (4.6 s)
  → **same Kh2, +123, depth 10**. More time does NOT change the move: this is
  an EVAL blind spot, not a depth artifact. The engine believes +126 standing
  with K on h3 and N on f4 while the e-pawn runs — the passed-pawn eg weights
  (P_PASSED_EG rank-3=15 … blocked +30) plus mobility noise swamp the threat.
  Snake's Nf2+/Nxh3 fork then converted.
- Position after Rh3 (ply-75 probe): engine best f2h3 = the fork itself,
  −123 (from White's view) at depth 8 — consistent.
- Perpetual-check region (ply-90 probe, after e1=Q): budget 1.30 s → best
  **a5d5 (+0) depth 8**; 3× budget → a5d5 +0 depth 9. The engine scores its
  own checking spree as 0 (draw) — honest given Q vs Q+R — and kept checking
  ~40 times (plies 91–161, counted from PGN) hoping for repetition. No
  position occurred 3× in the real game (Black varied: Kh7/Kg8/Kf7 + Rc8
  blocks); four positions occurred exactly 2×. The check-spree was not a
  threefold draw by force; it burned ~25 s of clock for nothing, and 90.e5
  (the pawn break) came 40 checks too late to matter (Black was +2 material
  by then and converted Q+R vs Q+3P — a *won* endgame for Black, well played).

**Root causes, ranked:**
1. **Horizon/eval blind spot on passed pawns under attack** — the +126 at the
   fork decision is a static-eval failure (passed pawn + blocked-pawn bonus
   for the *defender*, no "enemy passer about to promote" penalty); more time
   provably doesn't fix it (same move at depth 10).
2. **The check-spree plan had no termination test**: once checks run out
   (Black blocks with Rc8 / king walks), the engine had no alternative plan
   except e5 — it lacked any eval signal to switch earlier (no repetition
   pressure available since no position repeated 2× until plies 99–123, and
   its own score was already 0).
3. **Time management did NOT cause the loss**: spend tracked R/45+inc all game
   (see §2), never flagged, still had 14 s at move 112. The ~1.3–1.6 s budgets
   late in the game gave depth 8–9 — enough to *see* the fork line at +126,
   i.e. the info was there; the eval misread it.

**One-off tactical miss?** Partly — every engine blunders at depth 8 — but
the *class* of miss (defender's passer undervalued, mate-chase without plan
switch) matches the documented KQvK/KRvK/KPK technique gap. It is a leak, not
noise. It is NOT a Phase-4 (stateful) regression: the repetition machinery
behaved correctly (defense-side repetition was avoided; no 3rd-occurrence
position was ever available to White).

## 2. Time management — clock-profile numbers (r61–65)

Reconstructed per-move spend = prev_clk − clk_after + 0.5 s from %clk:

| round | our moves | avg spend | first | last clk | spend/budget (mean) |
|---|---|---|---|---|---|
| r61 D | 13 | 2.79 s | 3.09 s | 88.7 s | 1.00 (all moves ≈ exact budget) |
| r62 W | 39 | 2.04 s | 3.09 s | 57.8 s | 0.87 (last 5 moves ≈ 0 — mate found early) |
| r63 D | 47 | 2.13 s | 3.09 s | 41.3 s | 1.00 |
| r64 L | 112 | 1.41 s | 3.09 s | 14.9 s | 0.93 |
| r65 W | 41 | 2.03 s | 3.09 s | 55.1 s | 0.88 |

- Spend = budget almost exactly (ratio 1.00 median everywhere). The zero-spend
  tails are forced mates (search stops at MATE−32). **Never flagged in 252
  engine-moves across 5 rounds.**
- Budget decay table (engine/time.py, 120 s + 0.5 s): 3.17 s (move 1) →
  2.68 s (move 10) → 2.24 s (move 20) → 1.61 s (move 40). After a *typical*
  40-move game the engine still holds ~49 s — half its clock.
- **Is it leaving points on the table?** Yes, mechanically: R/45 leaves ~50 %
  of the clock unspent in games that end near move 40. A R/30 shape spends
  4.5 s on move 1 and still keeps ~31 s at move 40, ~8 s at move 80 — the
  geometric-decay never-flag property is divisor-invariant (any R/k+inc decay
  is), so the flag risk of R/30 is NOT structurally higher; the reserve is
  just thinner (see sim: R/25 leaves 1.25 s at move 112 — r64-class games get
  twitchy).
- **Would more time per move have helped r64?** No — Kh2 was chosen at depth
  8 *and* at depth 10 (3× budget). The failure was eval, not depth.
- Testability before freeze: a divisor change is a 1-line env-gated change and
  A/B-able at 500 ms gate TC... but at 500 ms the divisor barely binds
  (500 ms gates don't exercise the 120 s curve). A *real-clock* A/B (the
  documented §5 #6 idea) costs ~2 games/hour at gate convention — 24 games
  ≈ 2 days. Not realistically gateable before the 11 Sep 11:00 freeze on this
  box (also per PROCESS §8: no long SPRT in the same run as code edits).

## 3. Known gaps — cost-benefit for ONE pre-freeze change

### (a) KPK technique (both colours)
- **Fresh probe (this audit, engine vs itself, 2.7 s/move = real-clock budget
  shape, no game-history window in probe harness):** KPK-w threefold at ply 14;
  KPK-b threefold at ply 40 (queen promoted, then shuffled into repetition!).
- **BUT the probe harness under-represents the shipped agent**: the shipped
  agent feeds a 32-key game-history window into every search and its root
  anti-shuffle penalizes 2nd occurrences (Phase 4, gate 0.750) — my probe ran
  stateless. With history, third-occurrence moves are scored 0 outright. The
  documented Phase-4 gate: **eg_check 8/8 @300 ms incl. KPK both colours**,
  shuffle suite 11/12 @2 s (only KPK-b defender-held-opposition residual).
  A stateless rerun showing threefolds is expected to differ.
- Ladder exposure: none of r61–66 reached a KPK. The Phase-4 fix already
  targets exactly this; the *residual* (KPK-b @2 s, defender holds opposition)
  is a technique problem (opposition recognition) that the Phase-3.1 family
  already failed to buy with search/eval changes (gates 0.417/0.396).
- **Verdict: do not touch.** The evidence base (Phase 3.1 × 3 config variants
  all regressed; my probe contradicts the Phase-4 gate only because it strips
  the shipped history machinery) says the expected value is negative.

### (b) Cheap eval terms (tempo / king safety / passers)
- Eval already has: tempo 10, shelter, open file, passed/blocked/doubled/
  isolated, mobility, mate-drive. Phase 2's SPRT said richer ≈ flat at short
  TC (0.479 wash, 24 games) and tuned < hand decisively (0.104). PROCESS §5 #7
  already records: "eval features aren't the bottleneck; search/endgame are."
- r64 shows a *specific* shape the eval misses (defender's blocker pawn gets
  +30 *blocked* bonus while the promoting passer gets nothing beyond its rank
  weight; no direct "distance-to-promotion vs defender-king-distance" race
  term). A hand term `promoter race` is cheap to write — but that is precisely
  the eg-term family that regressed 3/3 in Phase 3.1, and per §5 #7 it needs
  NEW evidence first. My r64 probe (Kh2 at depth 10 = +123) is one position;
  n=1 doesn't clear the bar set by three failed gates.

### (c) Search config (LMR margins, null-window R, check extensions)
- LMR kept on gate 0.542 — touching its margins is gambling a positive-gate
  feature with zero new evidence.
- NULL_R=2 with the beta>0/endgame guards is standard; no observed pathology.
- **Check extension is unlimited (`depth += 1` at every in-check node).**
  r64's 40-check spree is the pathological shape for it, and the budget is
  time-based so explosion = fewer completed depths. Measured probe nps in the
  perpetual region: 431–500 knps, depth 8 @1.3 s — the search was NOT
  visibly exploding there (the sprees were in check-answer sequences the
  search resolves quickly). No node-count evidence of a real cost.
  A cap (e.g. extension budget per path) is textbook-safe but is still a
  search-behaviour change requiring the same 24-game gate — with no measured
  pathology to justify spending the remaining gate slots on it.

## 4. Verdict

**HOLD.** No surgical change clears the repo's own bar (≥0.55 on a 24-game
500 ms gate) with the evidence available before the 11 Sep 11:00 freeze:

1. Every candidate family has already burned its gate: aspiration 0.438,
   egfix 0.417/0.396/0.417, tuned eval 0.104. The last positive gate was the
   stateful fix (0.750) — protect it.
2. The r64 loss is explained by an eval blind spot that MORE TIME DOES NOT
   FIX (proved: same losing move at depth 8 and depth 10) — so time
   management and search-config changes do not address it.
3. The budget divisor (R/45 → R/30) is the one change with a plausible
   mechanical win (~+1 depth in the opening/middlegame where budgets are
   2–4.5 s), and it CANNOT be gate-tested properly at 500 ms — the gate clock
   doesn't exercise the curve. An ungated ship violates D11 (freeze policy).
   Post-freeze (final Swiss 12 Sep) is the right place to re-test it with a
   real-clock A/B if a gate slot exists.
4. Ladder reality: v3 line since the stateful fix is W D D L W W (3W-2D-1L,
   all wins conversions; the one loss a won-position leak, now root-caused as
   eval-side). The engine is converting, defending, and never flagging.
   Expected Elo gain from any single pre-freeze hack is below the regression
   risk it carries.

### What WOULD justify a change (pre-freeze)
Only a fix whose harm is provably zero and gain positive at 500 ms — none of
the audited candidates qualifies. If Pino insists on shipping *something*,
the least-risk candidate is the **budget divisor 45→38 + wider no-flag clamp**
(1-line, env-gated, decay property preserved), gated with the standard 24-game
match but explicitly accepted to be unmeasurable at that TC — i.e. it ships
on argument, not gate. Recommendation stands: hold.

## Appendix — probe logs
- Budget table + r64 probes + first KPK run: `/tmp/aud2_probe_out.txt`
  (P0/P1 exact numbers quoted above; P2 invalidated by stateless harness).
- Corrected KPK stateless run: `/tmp/aud2_kpk_out.txt`.
- Probe scripts: `/tmp/chess-aud2-strength/probes.py` (snapshot only; repo
  untouched).
