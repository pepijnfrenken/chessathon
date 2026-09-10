# chess-q5 codex1 fresh-eyes audit

## Verdict

**SAW.** A wrong-sign null-move cutoff, PST coordinates that reward home pawns and forward middlegame kings, no previous-best root ordering, and a leak corpus containing 14 opponent positions. These are stronger leads than another compensation clamp. Their existence is established from source/data. Their contribution to the six losses is not yet measured.

**DID NOT SEE.** Evidence establishing one common compensation mechanism across all six losses, evidence that r83 was lost because the opponent searched longer, or runtime proof of how often the null-sign defect fires. No engine evaluation or search was executed in this audit.

**NEXT EXPERIMENT.** After the current bout finishes and the box is released, first compare unchanged search, null disabled, and null-sign corrected on the same correctly sided pre-collapse positions. Hold eval and budgets fixed. Instrument null cutoffs and completed iterations. Include a separate baseline 1x/2x-time comparison. Do not enable COMPCLAMP or ship any candidate from this report alone.

## Scope and evidence discipline

Read ORIGINALITY.md, all of PROCESS.md, all of BUILD.md, `/tmp/chess-q5-audit2-report.md`, `tools/QUALITY_AB.md`, active search/eval/time/agent sections, relevant saved probes, the corpus, and saved PGN/review data. Root `QUALITY_AB.md` is absent; the read tool resolved it to `tools/QUALITY_AB.md`.

No repository writes, git operations, engine imports, engine runs, replays, or gates. Scratch files only under `/tmp`. Computation was limited to JSON/PGN parsing, literal-table arithmetic, and clock arithmetic. The PGN parser was python-chess 1.11.2, not a chess engine. `/tmp/chess-q5-codex1-data.py` aligns all 144 r83 PGN moves with the saved review and computes raw material. It ran in 0.23 seconds with `python -B`.

Commit `2a115cd` was supplied by the brief. I examined its current COMPCLAMP implementation and design record, not a git diff. The current PROCESS.md ends at line 398 and contains no compensation-clamp gate entry. The actual saved gate is `results/gate_compclamp_vs_head.log:1-27`, 8W-12L-4D, 0.417, zero flags. That corroborates the user-reported negative result.

All line references below refer to the source read during this audit. No changes were applied.

## 1. Ranked hypotheses

### H1. Null-move search has an unnegated child score

**Source defect, high confidence. Loss attribution, unmeasured. Highest-priority correctness experiment.**

`engine/search.py:573-600` enters null search when not in check, depth >=2, ply >=1, beta >0, at least two nonpawns on the board, and static eval >=beta. It flips side at 585, searches the opponent window `[-beta, -beta+1]` at 590-592, restores state, handles TIMEOUT, then executes:

```
if child >= beta:
    return child
```

`child` remains the opponent's score. Ordinary move search explicitly negates it at 650; root search does so at 757; qsearch does so at 508. The null branch does not.

With beta=100, opponent child=-150 represents a null value of +150 for us. The current code refuses that cutoff. Opponent child=+150 represents -150 for us. The current code accepts that cutoff and returns +150. This algebra was checked without executing engine code.

The second case can produce false optimism at an interior node. The first wastes work by missing a valid null cutoff. Both are plausible contributors to unstable depth and tactical scores. I did not measure occurrence counts on the leak positions. Null pruning itself is heuristic, so a corrected branch need not match exhaustive search in every position.

The `beta > 0` restriction does not repair the missing negation. The comment at 565-572 saying null move was effectively dead in full-window search is not a reliable description of current execution. Descendants and PVS siblings receive finite windows, notably 634-640 and 737-743.

**Concrete candidate.** After the TIMEOUT check, compute `null_score = -child`, compare it to beta, and return it on cutoff. Isolate this from changes to reduction, guards, or evaluation. Use a null-disabled scratch control as well. Do not retry NULL_DEEP before resolving this defect. Its 0.438 gate measured deeper reduction on this same sign convention, not a clean null implementation.

### H2. Compensation is real locally, but the pawn-PST explanation is backwards

**Coordinate behavior, high confidence. Intended orientation, strongly supported by table shapes and design prose. Strength effect of correction, unmeasured.**

`engine/board.py:122-124` defines a1=0 through h8=63. `engine/eval.py:471` indexes White PSTs directly and Black PSTs with `^56`. The literal tables at 200-286 have these consequences:

| White square | Pawn MG | Pawn EG | King MG |
|---|---:|---:|---:|
| e2 | 50 | 80 | -50 |
| e4 | 25 | 30 | -50 |
| e7 | -20 | 0 | 0 |
| e1 | 0 | 0 | -50 |
| g1 | 0 | 0 | -40 |
| e8 | 0 | 0 | 0 |
| g8 | 0 | 0 | 30 |

Thus home pawns receive the supposed advanced-pawn bonuses. The MG king table rewards g8 much more than g1 for White, despite BUILD.md:74-76 describing a castle-back middlegame king. The data rows look rank-8-first; the consumer is rank-1-first.

This is color-symmetric, not a White/Black sign bug. A mirrored-color parity test can pass while both sides receive bad incentives.

**The recorded r70 B position gives a precise counterexample to the existing narrative.** The FEN is `results/sims-v5/probe_v5_evals.log:9`. Material is White +220, phase 11. Literal-table sums, White POV, are:

| Component | MG | EG |
|---|---:|---:|
| All PSTs | -140 | -220 |
| Pawn PSTs only | -105 | -185 |
| Home-pawn difference only | -150 | -240 |
| Remaining pawn PST difference | +45 | +55 |

Black has b7/e7/f7/h7, each worth 80 EG PST cp. White has only f2 at that home rank, worth 80. The home-pawn difference alone gives Black 240 cp. The remaining pawn placements favor White by 55 EG cp, partially cancelling that credit. Black's f6 piece in this FEN is a bishop, not the pawn listed in `results/sims-v5/README.md:21-23`.

This supports masking in that position, but not the attribution to an advanced c5/d6/f6/g6 pawn phalanx. The stored depth-6/8/10 scores of -92/-92/-104 remain real evidence (`probe_v5_evals.log:10-12`). They are searched values, not raw static decomposition.

**The r68 flagship measurement also needs a POV audit before reuse.** BUILD.md:788-795 calls r68 Kh6 material -1020 and static +1100 in mover POV. The exact corpus FEN at `results/leak_suite/fens.json:158-162` has White material +1020 and Black to move. Its total White PST contribution is only -35 MG/-90 EG. Material plus tapered PST is +955 White; the king drive adds another +50 White. There are no black advanced passers capable of explaining a +2120 Black compensation claim. I did not run evaluate() to obtain its final score, so a POV/sign mix-up is a strong suspicion, not a measured replacement score. Do not use the +2120 claim to set another clamp threshold without reproducing its sign and position identity.

**Concrete candidate.** Normalize PST row order to the documented coordinate convention, once at hand-table assembly (`engine/eval.py:289-305`), not in the shared pawn masks. Audit each asymmetric table, including king and rook tables. Start with a pawn-table-only diagnostic ablation, then test the full intended orientation separately. Do not reverse `PASSED_W` or shelter masks, which are explicitly constructed in a1-based coordinates at 151-162.

### H3. Iterative deepening does not prioritize its previous best root move

**Source behavior, high confidence. Wasted completed-depth opportunity, plausible but unmeasured.**

`engine/search.py:810-822` keeps `best_move`, but calls `_order_moves(..., ttmove=0, ..., ply=0)` on every iteration at 813. It never passes the prior iteration's winner into the existing top-priority ordering slot (`_score_move`, 393-394). Root iterations also do not update root killers/history or store a root TT entry here.

Later root contenders receive zero-window search and potentially an expensive full re-search at 737-743. Any timeout sets `iter_move=0` at 754-756. The caller then discards the whole incomplete iteration at 818-819. The last completed iteration is a sensible safe fallback, but omitting prior-best ordering makes it harder to complete useful work before that fallback.

This mechanism fits the saved budget-sensitive move changes in `results/sims-v5/README.md:34-42`. It is not proof that any particular r83 move came from a stale iteration. The PGN has no per-iteration trace.

**Concrete candidate.** At 813 pass `best_move` into the existing ordering slot instead of zero. Keep full windows and last-completed-iteration fallback. Do not combine this small change with aspiration or partial-result adoption. LMR and persistent TT/history make even ordering changes behaviorally significant, so gate it.

### H4. The fixed clock schedule can starve critical positions, but does not explain r83 alone

**Fixed allocation and spend, measured from code and clocks. Benefit of extra time, unmeasured.**

`engine/time.py:16-27` uses remaining/45 + increment with caps. `agent.py:148-154` sets one hard deadline. Nothing in allocation depends on legal-move count, score drop, root instability, tactical complexity, or game phase. Search stops early for one legal move (`search.py:798-799`) or a mate score (823-824), not for stable easy positions generally.

The code therefore does not deliberately search easy moves shallow and hard moves deep. It allocates essentially equal wall time at equal remaining clock. Complex trees may complete fewer plies within it; actual completed depths are not in the PGN.

See the clock measurements below. Extra thinking time remains a valid experiment, particularly for r70, but not a demonstrated fix. The wrong null cutoff and PST incentives also mean that more search is not guaranteed to improve the answer.

## 2. Why COMPCLAMP's negative gate does not settle the theory

The implementation at `engine/eval.py:679-698` is a one-sided bound on compensation, not an absolute `|static-material| <=120` band. For White material +220 it floors the pre-tempo White score at +100. For -220 it caps it at -100. Already more-extreme advantages or disadvantages remain untouched. Tempo is added after the clamp, so the stated 120-cp band would not even be literal at the returned-score boundary.

Three reasons the experiment can fail despite real local miscalibration:

1. **It flattens choices instead of correcting their cause.** With material -220, static scores -90, 0, and +150 all become -100 before tempo. Their positional ordering disappears. Real compensation from a passer or attack is also suppressed. Losing leaves can become indistinguishable exactly where accurate defensive ranking matters.
2. **Its thresholds are not a model of the initiating error.** The cutoff is two pawns, not necessarily a minor piece. It switches at phase 16/17 and material 190/200, can fire transiently during search exchanges, and operates on every qualifying leaf, not just the named root deficits. Root corpus coverage says little about that tree-wide distribution. In r83, the first six mistakes and 45...Bxe5 all begin at equal material.
3. **It leaves search-score defects and reversed incentives intact.** It does not fix the null sign, PST orientation, previous-best ordering, or budget allocation. It can even change pruning frequency through static eval without addressing the faulty cutoff.

The 24-game result is a negative ship gate, not strong statistical proof that compensation cannot matter. Leave it OFF. Do not merely widen the band and rerun it as the next priority.

## 3. The diagnostic corpus is not currently an adequate leak-family gate

**57 entries exist, but 14 belong to the opponent.** Comparing each entry's side against its game's En Passant Labs header gives:

| Game | Our side | Entries on opponent side |
|---|---|---:|
| r77 | Black | 5/5 |
| r78 | Black | 3/3 |
| r80 | Black | 3/3 |
| r83 | Black | 3/3 |

All other represented games passed that side check. Correctly sided total is 43/57. This checks attribution, not completeness or labeling quality.

r83's three rows are White's g3 at relative ply 32, Ke3 at 116, and Rf8 at 130 (`fens.json:488-513`). Our black errors are not represented at all. In particular, neither 45...Bxe5 nor 65...Ka8 is in this alleged worst-loss corpus. A successful clamp probe on these three FENs says nothing direct about our r83 move selection.

The saved r83 review itself correctly contains both colors. `tools/review_sf.py:115-134` writes all rows to JSON regardless of the output-side filter. Any downstream collector must filter explicitly. I did not locate or establish which writer introduced the bad corpus entries.

**The mistake-dense label also includes already-lost mate play.** Black's saved counts are exactly 12 mistakes, 6 inaccuracies, 2 blunders. Four of those 20 >90-cp events already have `|eval_before| >=20000`, including three of the 12 mistakes. Those are not ordinary 160-300cp positional leaks. The referee maps mate distance into 100-cp steps (`review_sf.py:43-45`). Separate them rather than summing them into a pre-collapse explanation. This agrees with audit2 F1/F5; it does not erase the genuine earlier mistakes.

`tools/leak_probe.py:39-54` also creates fresh TT/history per FEN and passes empty game history. It is an isolated-position test, not the venue's persistent search state. Its first search has no explicit warmup before the timed call. Future experiments should warm the exact specialization before timing and label history conditions. Do not equate identical engine cp scores with equivalent move quality under an independent referee.

## 4. Time-management evidence

Clock arithmetic uses previous same-side post-move clock +0.5s minus current post-move clock. Initial clocks are 120s. PGNs use nonstandard starting positions; plies below are relative to PGN movetext, not fullmove numbers.

| Game/side | Moves played | Total spent | Mean spent | Final clock |
|---|---:|---:|---:|---:|
| r70, us Black | 30 | 67.717s | 2.257s | 67.283s |
| r70, KingsGuard White | 31 | 131.084s | 4.229s | 4.416s |
| r83, us Black | 72 | 128.026s | 1.778s | 27.974s |
| r83, 404 Not Found White | 72 | 63.968s | 0.888s | 92.032s |

KingsGuard spends 1.94x our total, or 1.87x per move. In r83 **we** spend 2.00x the opponent's total. These clocks do not measure pondering or engine efficiency.

For r83 black relative plies 3 through 131, actual spend exceeds the integer budget formula by only 1-4ms, median 2ms. First move spends 4.239s against a 3.166s nominal budget. Later forced-mate/forced-move behavior spends less. The main-game trace follows the crude allocator almost exactly; it does not show a hidden difficulty-aware scheduler.

Selected r83 evidence, all Black POV:

| Move | Relative ply | Raw material before | SF before | cp_loss | Clock before | Spend |
|---|---:|---:|---:|---:|---:|---:|
| 18...Qd8 | 21 | 0 | -51 | 190 | 94.956s | 2.613s |
| 22...O-O-O | 29 | 0 | -54 | 190 | 86.784s | 2.431s |
| 23...Bg5 | 31 | 0 | -174 | 210 | 84.853s | 2.386s |
| 25...Qa6 | 35 | 0 | -53 | 166 | 81.121s | 2.305s |
| 27...Rhd8 | 39 | 0 | -43 | 188 | 77.551s | 2.226s |
| 28...Kc7 | 41 | 0 | -44 | 175 | 75.825s | 2.187s |
| 45...Bxe5 | 75 | 0 | -124 | 421 | 51.722s | 1.651s |
| 46...Qd5 | 77 | +100 | -545 | 107 | 50.571s | 1.625s |
| 65...Ka8 | 115 | -230 | -1386 | 390 | 32.967s | 1.234s |

The first six mistakes are not positions where we are already materially down. Opponent errors repeatedly return the referee score close to equality. At 45...Bxe5 the major tactical collapse starts before any raw-material deficit. By 65...Ka8 the referee already calls the position far worse than its 230cp material deficit. A material-centered clamp is not a direct model of either transition.

Without overhead or early exits, the schedule leaves `120*(44/45)^n` seconds after n moves, approximately 61.15s at 30 moves, 48.84s at 40, and 31.16s at 60. Half a clock remaining in a short loss is largely built into the policy. It is not proof that half the granted move budgets were unused.

**Conclusion.** There is an opportunity to spend more on critical decisions, not evidence for replacing the whole diagnosis with time management. r83 proves a stronger/faster opponent can beat us while spending less. Code correctness and useful work per allocated second are the first priorities.

## 5. Four fix directions for the freeze window

Expected value is qualitative and conditional, not an Elo forecast. Test changes separately.

| Rank | Direction and exact site | Expected value | Implementation/validation cost | Risk |
|---|---|---|---|---|
| 1 | Correct null child negation, `engine/search.py:597-600`; compare with null disabled | High if faulty cuts occur in critical trees; fixes a concrete sign error | Tiny source change; focused branch reproduction plus equal-budget position tests and gates | Medium. Changes both pruning correctness and effective depth |
| 2 | Correct intended PST row orientation at hand assembly, `engine/eval.py:289-305`; pawn-only diagnostic first | High plausible structural gain; directly explains home-pawn compensation and king incentives | Small code change, broad behavioral validation | High near freeze. Existing weights and move choices were developed around current tables |
| 3 | Pass prior `best_move` to root ordering at `engine/search.py:813` | Moderate plausible gain in useful completed search | One-site change; fixed-depth/equal-time comparisons | Low-medium. LMR/order/TT interactions can change values and choices |
| 4 | Trial remaining/30 + increment instead of /45 at `engine/time.py:20`, preserve safety caps | Moderate only if same-FEN extra-time tests improve moves | Tiny allocator change; full 120s+0.5s games required | Medium. More early spend, less late reserve; no automatic quality gain |

For direction 4, /30 gives 4.5s initially versus 3.166s, without blindly doubling every budget. Approximate reserves become 43.4s after 30 moves and 15.7s after 60 before overhead. Test long games and low-clock behavior. A soft/hard deadline driven by root instability is a later, larger change in `agent.py:148-154` and `search.py:810-824`, not the first freeze-safe experiment. Pondering and aspiration are not recommended as initial fixes here.

Do not combine these four into one gate. If source correctness fails in an isolated reproduction, do not conceal it with a time multiplier or eval clamp.

## 6. Concrete recommended next experiment

Run only after explicit release of the currently occupied box. Nothing in this section was executed.

### Preparation without engine compute

1. Rebuild a scratch position list from PGN headers and cached review rows. Select our side explicitly. Keep opponent moves as separately labeled controls, not our leaks.
2. Include r83 relative plies 21/29/31/35/39/41/75/77, the r70 B FEN, and a small matched set of good moves from wins. Keep later lost/mate-range positions in a separate diagnostic stratum.
3. Preserve FEN, actual side, fullmove and relative ply, PGN pre-root history, clock-derived budget, and review score regime. Do not compare unmatched replay prefixes.

### First executable batch

Use isolated scratch variants, fresh processes with the same warmup and reset policy, one engine process at a time on the allotted core:

- A. Unchanged baseline, COMPCLAMP/SEE/NULL_DEEP left OFF.
- B. Same code with the null branch disabled.
- C. Same code with only null-score negation corrected.

Run a focused branch reproduction before strength tests. Record beta, returned opponent child, corrected null value, and whether a cutoff fired. Demonstrate that current acceptance and corrected acceptance differ on a reached node; do not claim full exhaustive-search equivalence for heuristic null pruning.

Then run identical FENs at fixed depth, followed by equal wall-time budgets derived from the PGN. Log completed depth, nodes, move, root score, null attempts/cutoffs, and completed iteration winners. Fixed-depth differences identify selectivity effects; equal-time comparisons measure the correctness/depth tradeoff. Keep cold-position and reconstructed-history results separately labeled. Warmup must finish before deadlines start.

For a time-only control, run A at 1x and 2x each position's recorded nominal budget, with identical state initialization. A short repeat with reversed run order separates timing-boundary noise from a stable change. Independent referee analysis should score candidate moves from the **same parent FEN**, with consistent resources. Keep cp and mate outcomes separate; use paired deltas and counts crossing 160/300cp rather than raw whole-game means.

### Decision rules

- If C removes bad cutoffs and improves the same-FEN choices without regressions on controls, advance it alone to the controlled gate and real-clock games.
- If B helps but C does not, do not conclude that the old sign was correct. Examine guard/selectivity behavior in the corrected implementation; null-off is a diagnostic control, not automatic ship policy.
- If A at 2x reliably fixes the early errors while B/C do not, prioritize direction 4, then test full-clock games rather than extra-time isolated positions alone.
- If moves and losses remain despite deeper/corrected search, advance the PST orientation ablation. Measure terms and chosen moves, not whether scores were forced nearer material.
- Root ordering is the next small independent candidate. Keep last-completed-iteration fallback intact.

Use the existing 500ms gate as a short-clock regression screen, not proof of a time allocator, then actual 120s+0.5s paired games for a ship decision. Preserve init/legality/shuffle checks. Audit2 F1-F9 still apply. quality_ab's raw aggregate PASS/FAIL and the current 57-FEN corpus are not sufficient deciding instruments.

## 7. What remains open

- No runtime activation frequency or strength measurement for the null sign, PST orientation, or root ordering.
- No own-engine score/depth trace for r83. The near-equal values in this report's r83 table are the saved referee's values, not our engine's internal belief.
- No measurement separating pondering, NPS, branching factor, and evaluator strength between opponents.
- No proof that SEE or qsearch is cleared as a family. With SEE toggles OFF, qsearch still has capture-only stand-pat and a 12-ply cap (`search.py:448-473`). The prior SEE experiments do not test adding quiet threats/checks to that horizon, and their replay coverage was weak per audit2 F8.
- Additional concrete but probably non-family defect. `eval.py:527-536` increments `mins` for bishops, not knights; 689-693 can return zero for pawnless/majorless KBN-v-K and KNNN-v-K. That deserves a separate correctness reproduction, not another item mixed into the leak gate.

Bottom line. The engine has observable search and evaluation-shape defects, and the diagnostic set misattributes the newest loss. Correct attribution and null-score algebra first. Treat the home-pawn PST reversal as the strongest evaluation lead. Keep COMPCLAMP OFF and demand same-position evidence before choosing time versus eval as the next strength change.
