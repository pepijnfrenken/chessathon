# Null-sign and extra-time experiment

## Verdict

**The null-score sign defect reproduces at runtime. Correcting it saves search work, but this experiment does not show a meaningful move-quality improvement. Doubling baseline time does not repair any of the eight sampled r83 positions.**

No repository change or upload was made. This was an isolated diagnostic experiment, not a ship gate.

## Execution

The process check found no active Stockfish, gate, replay, or engine worker before launch. The supervised job `q5-null-experiment` completed with exit code 0 in 8m12s. Workers ran sequentially, pinned to one available CPU. Stockfish ran afterward, also with one thread.

All engine copies, instrumentation, scripts, caches, and outputs are under `/tmp/chess-q5-codex1-experiment`. Engine source SHA-256 hashes before and after are identical. No git operations were used.

The batch ran 182 search probes over 13 positions:

- Eight correctly sided r83 positions, relative plies 21/29/31/35/39/41/75/77.
- The actual r70 B position, relative ply 24.
- Four good-move controls from r71/r73. One control, r73 ply 43, has only one legal move and returns depth zero. It is a forced-move control, not a useful strength discriminator.

Every search checked that its move was legal and the board state was restored. All 182 passed. All three engine specializations were warmed before timed searches. TT, killers, history heuristic, and scratch arrays were cleared for each probe. Actual pre-root game keys were reconstructed from the PGNs, up to the engine's 32-ply window. Thus repetition context was present, but venue TT/heuristic state was not reproduced.

Arms:

- Baseline, with diagnostic counters only.
- Null branch disabled.
- Only null child negation corrected, with the same diagnostic counters.
- Baseline at twice the position's nominal clock-derived budget.

Each engine ran depth-6 and depth-8 probes. Each timed arm ran twice, reversing position order for the second pass. Variants themselves ran in a fixed sequence, so this is not a fully randomized timing study.

## 1. Runtime reproduction

Before r83 18...Qd8, relative ply 21, the baseline depth-8 search recorded:

```
null_completed = 3732
old_accept = 9
correct_accept = 2975
first_old_accept = {beta: 149, child: 232, depth: 2, ply: 3, stand: 156}
```

The node accepted opponent child +232 as our +232 cutoff score against beta 149. Its correctly negated null value is -232, which cannot justify that cutoff. This is a reached search node, not a synthetic arithmetic example.

The 2,975 `correct_accept` events count null results that met the correctly negated cutoff condition but were rejected by the old sign check. These are sign-condition observations, not a claim that heuristic null pruning equals exhaustive minimax.

Across all depth-8 probes, baseline accepted 141 wrong-sign cutoffs and rejected 23,308 results meeting the corrected sign condition. Wrong-sign acceptances appeared in all 12 positions with an actual search. The thirteenth position had one legal move and no search.

In the corrected tree, 17,782 corrected-sign cutoffs were accepted. Its counter also observed 81 cases meeting the old sign condition, but that obsolete condition no longer controls acceptance. These counts come from different trees and should not be treated as paired cutoff events.

## 2. Search cost

Twelve positions reached depth 8. The forced-move control returned depth zero in all arms.

| Arm | Total nodes in depth-8 probes | Total measured search time |
|---|---:|---:|
| Baseline | 9,008,407 | 18.173s |
| Null disabled | 8,637,620 | 16.430s |
| Sign corrected | 7,195,857 | 15.033s |

The correction reduced nodes by **20.12%** and measured time by **17.27%**. Instrumentation is included in these timings. Disabling null preserved every depth-8 root move and score. Correcting the sign changed two root moves and additional scores.

At equal wall time, excluding the forced-move control, mean completed depth was:

| Arm | Mean completed depth |
|---|---:|
| Baseline 1x | 8.333 |
| Baseline 2x | 8.792 |
| Null disabled 1x | 8.208 |
| Sign corrected 1x | 8.375 |

The fixed-depth savings did not translate into a substantial completed-depth gain at these discrete deadline boundaries.

## 3. Paired referee results

Stockfish identified itself as **Stockfish 19**. It analyzed 31 distinct position/move pairs at depth 16 with Threads=1 and Hash=128. Each candidate was searched from the identical parent FEN with a forced root move and cleared hash. The unrestricted best move was also included. No analyzed score was in the mate region.

The table uses descriptive centipawn regret against the best observed comparable score at that parent, including the unrestricted reference and forced-root searches. It is not the older cached review's consecutive-position cp_loss. This avoids both unmatched populations and mate-clamp arithmetic. Fixed-depth referee scores still have noise, and selecting the best observed score can inflate absolute regret. Paired move-score differences are more useful than exact threshold labels.

Each arm has 26 timed observations, two per position. They are repeats of 13 positions, not 26 independent samples.

| Arm | Mean regret | Median regret | >160cp | >300cp | Positions changing move across repeats |
|---|---:|---:|---:|---:|---:|
| Baseline 1x | 99.62 | 45 | 8/26 | 2/26 | 1 |
| Baseline 2x | 99.85 | 45 | 8/26 | 2/26 | 0 |
| Null disabled 1x | 105.38 | 49 | 9/26 | 2/26 | 2 |
| Sign corrected 1x | 100.92 | 45 | 6/26 | 2/26 | 0 |

Corrected versus baseline mean difference is **+1.31cp**, effectively no evidence of an overall quality gain in this small set. The lower mistake count reflects a boundary crossing in one position repeated twice, not two independent rescued mistakes.

The eight r83 positions alone have mean regret 149.625cp for baseline 1x, 149.625cp for baseline 2x, and 148.375cp for the correction. That is a **1.25cp mean improvement**, not a leak-family fix.

### Positions that explain the result

- **r83 22...O-O-O, ply 29.** Every arm still castles queenside. Its referee score is -231cp, versus approximately -70cp for kingside castling.
- **r83 23...Bg5, ply 31.** Every arm still chooses Bg5. Regret is 218cp. Double time reaches depth 9 but does not change the move.
- **r83 before 27...Rhd8, ply 39.** Baseline chooses Kb8, referee -165cp. The correction chooses Kc7, -191cp. Correction is 26cp worse here.
- **r83 28...Kc7, ply 41.** Baseline chooses Kc7, -220cp. The correction chooses Kb8, -184cp. Correction is 36cp better here. This accounts for the repeated >160cp count improvement.
- **r83 45...Bxe5, ply 75.** Every arm still chooses Bxe5, referee -570cp with 457cp regret. Doubling time fails to repair the central tactical collapse, including a repeat that completed depth 9.
- **r70 B, ply 24.** Baseline 1x alternates between Rfc8 (-498cp) and Rac8 (-504cp). The correction consistently picks Ra7 (-528cp). Extra completed depth does not improve the referee's opinion here.
- **r83 plies 21 and 35.** The cold-TT baseline already chooses different moves from the actual game. Those positions cannot be credited as rescues by the correction or extra-time arm.
- All four win controls retain the same move in every timed arm.

## 4. Evaluation evidence strengthened by the runtime probes

The r70 B static score is exactly **-26cp** in every arm, reproducing the saved static measurement. The correction leaves evaluation unchanged and does not cure its compensation skew.

The r83 Black static scores before the sampled moves are:

| Relative ply | Full move | Static, Black POV |
|---|---|---:|
| 21 | 18... | +78 |
| 29 | 22... | +90 |
| 31 | 23... | +99 |
| 35 | 25... | +181 |
| 39 | 27... | +145 |
| 41 | 28... | +205 |
| 75 | 45... | +164 |
| 77 | 46... | +318 |

These are now actual engine outputs, not the referee values used in the initial audit. In particular, before 46...Qd5 the evaluator reports Black +318 while the saved referee already reports Black -545. Both the corrected sign and double-time arms still play Qd5.

The experiment supports a separate evaluation/horizon problem. It does not prove which evaluation term is responsible, nor rule out a horizon beyond twice the current budget.

## 5. Decision and next action

1. **Null sign is a proven correctness defect.** The isolated fix is a credible candidate for a controlled strength gate, but this position experiment does not establish a strength win. Do not present the 20% node reduction as an Elo result.
2. **Do not prioritize a blanket time increase on this evidence.** Twice the time repaired none of the eight sampled r83 positions and left the 45...Bxe5 collapse intact. That does not rule out adaptive allocation or much deeper search, but the simplest time-only hypothesis did not pay off here.
3. **Next diagnostic priority is the pawn-PST orientation ablation.** Keep null behavior fixed within each A/B. First test the rank-orientation issue identified in the audit, with positional term decomposition and same-parent referee scoring. Test king-PST orientation separately rather than bundling it into a large retune.
4. **Leave COMPCLAMP OFF.** No result here rescues its negative gate or validates its flattened material band.

No gates, full games, PST modifications, or further engine changes were launched. They require a separate experiment or shipping decision.

## Artifacts

- `run.py`. Reproducible preparation, sequential worker batch, and referee runner.
- `positions.json`. Correctly sided FENs, original clocks, saved review rows, and pre-root history.
- `baseline.jsonl`, `disabled.jsonl`, `corrected.jsonl`. All search results, counters, and completed-iteration traces.
- `referee-id.json`, `referee.jsonl`. Referee identity and all move evaluations/PVs.
- `summarize.py`, `summary.json`, `scored-searches.json`. Paired analysis and derived data.
- `source-hashes.json`, `source-hashes-after.json`. Identical repository engine source hashes.

Original read-only audit remains at `/tmp/chess-q5-codex1-report.md`.
