# R90 loss audit: updated Black-side deep review

## Verdict

**Keep the verified V6 null-sign correction. Do not roll back to V5 on this game. Do not describe the PST-flip candidate as approved until its gate completes.**

The evidence supports an earlier endgame collapse, followed by a loss-to-detected-mate transition at 46...Kg2. It does not establish a new V6 null-pruning defect. It also does not establish that the game was a statistical fluke, that V5 would have saved it, or that more time or the pawn flip would avoid Kg2.

The decisive earlier diagnostic position is 39...Nf8. The new referee review evaluates Black at +33cp before that move and White at +618cp afterward. Before 46...Kg2, Black is already at -1429cp. Avoiding Kg2 could prolong resistance without saving the game.

**Replay remains blocked by the active night gate.** The process check found `gate_match_tree.py --side-b-root /tmp/chessathon_n2base --games 24 --move-ms 500 --seed 7 --log results/gate_night2_pstflip_vs_n1.log` and both engine workers. No new engine, Stockfish analysis, replay, gate, upload, or source edit was started. Two read-only audit workers exhausted Codex quota; their final reports were not available. This report preserves the verified main-session analysis and explicitly marks the unavailable measurements.

## Evidence and attribution

Primary evidence is `results/matches/round-90-vs-chessbuster-9000.pgn` and `results/leak_reviews/round-90-black-deep.json`. Lightweight PGN parsing found 118 played half-moves, no parser errors, and checkmate at 67.Qc5#. All deep-review UCI moves align with their PGN-relative plies. We are Black, En Passant Labs. The JSON includes both colors despite its filename.

Black-only counts match the supplied summary: 37 best, 3 excellent, 7 good, 6 inaccuracies, 2 mistakes, 4 blunders. A printed global biggest-loss list can include White moves. `tools/review_sf.py:124-132` filters the summary by side but sorts all rows for the biggest list. Do not attribute White's f4 to V6.

| Black move | Relative ply | Black referee eval before | Reported loss | Meaning |
|---|---:|---:|---:|---|
| 37...Ne6+ | 59 | +494 | 445 | Gives up most of a substantial advantage |
| 39...Nf8 | 63 | +33 | 651 | Crosses from near equality to a large deficit |
| 44...Kf1 | 73 | -988 | 74 | Already badly losing; not the later Kf1 |
| 45...Nxd7 | 75 | -790 | 52 | Deep review no longer classifies this as a blunder |
| 46...Kg2 | 77 | -1429 | 26471 | Referee switches to a detected forced mate after the move |
| 47...Kf1 | 79 | -27700 | 500 | Already in the referee's mate-score region |

The prior SF18 review assigned the largest loss to 47...Kf1. The new deep review assigns it to 46...Kg2. This is evidence that the referee's detection boundary moves with analysis depth. It is not evidence that our engine completed any particular depth.

`tools/review_sf.py:36-46,105-117` converts mate scores to `30000 - 100*abs(mate_distance)` and computes loss from consecutive side-to-move evaluations. The new Kg2 loss is exactly `-1429 + 27900 = 26471`. Under that convention, +27900 represents mate in 21. The later Kf1 loss is `-27700 + 28200 = 500`, a mate-distance change rather than five pawns of ordinary material loss. The cached JSON has no PV or explicit mate metadata; this decoding relies on the repository's referee convention. A numerical score before Kg2 is not proof that no forced mate existed before it.

## 1. Horizon effect or evaluation error?

### What is established

The pre-Kg2 position is:

```text
8/p2B3p/1p4p1/1P4P1/8/4K3/8/5k2 b - - 0 46
```

Black has Kf1 and pawns a7/b6/g6/h7. White has Ke3, Bd7 and pawns b5/g5. This is not queen-and-rook infiltration. The played continuation is 46...Kg2 47.Bc6+ Kf1 48.Bd5 Ke1 49.Bg8 Kd1 50.Bxh7 Kc2 51.Bxg6+, followed by the g-pawn's promotion and eventual mate.

The frozen V6 source in `/tmp/chess-v6-nullfix.zip` requires at least two non-pawn, non-king pieces on the entire board before null pruning can run. See `engine/search.py:374-386,573-605`. This position has only one, White's bishop. Null pruning is therefore disabled here and throughout nonpromotion descendants. The subsequent Kf1 position is also in check. Promotion can eventually re-enable the piece-count condition, so this does not rule out every remote downstream null effect or earlier transposition-table effect. It does rule out the proposed direct null cutoff in the immediate Kg2/Kf1 endgame.

Quiescence already detects checkmate and searches all evasions in check. See `engine/search.py:446-473`. At its depth cap it returns static evaluation unless the checked position has no escape. At ordinary noncheck nodes it uses stand-pat and tactical moves rather than all quiet continuations. Quiet bishop maneuvers and pawn advances can therefore lie beyond its tactical horizon. This is a plausible limitation, not a demonstrated trace of this move.

The KBN-v-K insufficient-material bug cannot zero this position. Pawns are present, while the old zeroing branch requires no pawns and no major pieces (`engine/eval.py:477-478,689-693` in the frozen archive).

### What remains unknown

No saved record supplies V6's static evaluation, qsearch result, completed search depth, PV, root alternatives, or their scores at ply 77. The JSON's `eval_before=-1429` is the referee's searched evaluation, not V6's static evaluation. We cannot infer that V6 thought the position equal.

[INFERENCE] The most defensible mechanism class is limited endgame search combined with imperfect evaluation of pawn structure and promotion threats. The evidence does not separate those components causally. It does not justify a targeted king-safety patch or a claim that V6 introduced a new mate-recognition bug.

## 2. Would deeper search avoid Kg2?

**Unmeasured.** Greater depth could recognize the losing continuation earlier, but it could still select Kg2 in an already lost position. There is no demonstrated drawing alternative or V5 winning continuation.

The PGN gives 50.619 seconds before 46...Kg2 and 49.493 seconds afterward. With the 0.5-second increment, observed thinking time is about 1.626 seconds. `engine/time.py:16-27` gives a nominal budget of 1.624 seconds. The analogous budget before 39...Nf8 is 1.816 seconds. A generic 2.6-second replay is not the exact local budget for either position, and more wall time does not guarantee exactly one extra completed ply.

When the gate is inactive, compare the following serially, one process and one position at a time:

- Frozen V5 reference, with its shipped buggy null sign.
- Frozen V6, with the corrected sign.
- V6 with null pruning actually disabled, as a separate diagnostic condition.
- V6 at the recorded budget and a modest extra-time budget; also compare fixed completed depths N and N+1 where feasible.

Restoring V5's wrong sign is not the same as disabling null pruning. The current corrected-sign version is V6, not a third independent fix.

Prioritize ply 63, then ply 77. Record move, score, PV, completed depth, nodes, exact source hashes, and cold/warm TT and history conditions. A standalone FEN replay does not reproduce the ladder's persistent search state. Have the referee compare alternative root moves from the same parent position rather than interpreting internal score changes as playing-strength improvements.

## 3. Would the pawn flip help?

**It removes a demonstrable static bias here. Whether it avoids Kg2 is unknown.**

I parsed the pawn-table numeric literals from the frozen V6 archive without importing or running the engine. For each pawn I applied the evaluator's White-direct/Black-xor-56 indexing, then compared vertically flipped pawn rows. These are pawn-PST contributions only, not full static scores or search outcomes.

| Position | White MG pawn-PST old -> flipped | White EG pawn-PST old -> flipped |
|---|---:|---:|
| Before 39...Nf8 | -80 -> +30 | -140 -> +15 |
| Before 46...Kg2 | -120 -> +10 | -210 -> -10 |
| Before 47...Kf1 | -120 -> +10 | -210 -> -10 |

At Kg2 the correction is +130 MG / +200 EG from White's perspective. With one bishop and the source's 24-point taper, the pawn-table contribution shifts by about +197cp for White, or -197cp for Black, subject to integer rounding. At Nf8 it shifts about +151cp for White. This corroborates the existing pawn-orientation diagnosis in `docs/research/07-pst-phantom-decomposition.md`.

Crucially, Kg2 does not move a pawn. The pawn-table correction is the same immediately before and after that king move, and also across other quiet king alternatives preserving the pawn placement. It cannot directly distinguish those alternatives through an immediate pawn-PST delta. It may change search choices through later pawn advances, captures, evaluation bounds, or ordering. Only replay can show whether that helps here.

Do not equate a less optimistic static score with a demonstrated move-quality improvement. Let the active pawn-flip gate finish before making a shipping decision.

## 4. Repeatable failure mode or outlier?

The inverted pawn profile is a systematic evaluation defect, already documented on multiple positions. Its contribution here is reproducible arithmetic. Quiet endgame plans beyond a finite tactical horizon are also a general engine limitation.

The specific Kg2 choice is not yet shown to be repeatable under controlled conditions, nor V6-specific. One ladder loss cannot estimate its frequency. Even the referee's largest-blunder attribution changed between saved analyses. No numerical probability of null pruning hiding a sole mate sequence is supported. Immediate null pruning in this one-piece endgame is impossible under the guard, but that is not a frequency estimate for earlier positions with more pieces.

The new review supports earlier deterioration, not a game that remained sound until one random catastrophic move. Nf8 is the better root-cause target. The claim that V5 would also lose remains untested, as does the claim that V5 would save the game.

## 5. Keep V6 or roll back?

| Choice | Evidence and risk | Recommendation |
|---|---|---|
| Keep verified nullfix V6 | Corrects a real negamax sign error; saved L1 result is 16W-6L-2D at 500ms/move, zero flags. No demonstrated r90 regression mechanism. | Keep for now. This is not proof of real-clock superiority. |
| Roll back to V5 | Reintroduces the known wrong-sign cutoff. No r90 replay demonstrates a compensating benefit. | Not justified by this game. |
| Ship pawn flip plus endgame fix | Pawn orientation has a reproducible static defect; KBN correction fixes a separate bug. Active gate is not a completed pass, and neither fix is shown to save r90. | Conditional on completed candidate evidence and exact archive verification. |
| Add speculative mate/king-safety patch | Qsearch already recognizes immediate mate; no traced new defect. Broad changes near freeze carry uncontrolled strength risk. | Do not patch on this narrative alone. |

The V6 L1 comparison is encouraging but is a small, fixed-seed A/B experiment against V5, not a 70.8% predicted win probability against Chessbuster. The L2 comparator `/tmp/q5b_analyze.py:24-31` subtracts the engines' own searched scores. Its -5cp mean and same-move -332cp row do not constitute independent referee move-quality regressions. Keep that limitation visible.

## Build identity and queue state

The latest direct process check shows **item 2, PST flip, now gating** against `/tmp/chessathon_n2base`. Earlier in this audit item 1 was still gating; these are different observation times. No completed item-2 result was inspected. No verified item-3 completion evidence was obtained.

The requested `/tmp/chess-v6-nullfix.zip` has SHA-256:

```text
71c172ee28a72ae3db0ec3731a2d33b8e8cb5b22b6c39a5fb82a0762346d4322
```

Its inspected source has the corrected null sign but still the old insufficient-material zeroing. The supplied description that V6 includes the KBN fix may describe a later deployed revision; it is not the content of this inspected archive. No authenticated deployment manifest was inspected. For this pawn-containing position the KBN distinction does not directly change the zeroing path, but it matters for replay provenance. Do not substitute working HEAD or a filename-based guess for the actual submitted artifact.

## Scope and next action

This is a completed read-only evidence audit with a blocked experimental component, not a completed V5/V6 replay diagnosis. The main session checked PGN legality and review alignment, recomputed side-filtered counts and clock budgets, inspected frozen source, and computed pawn-table deltas without an engine import. Repository source and logs were not changed.

Once there is an explicitly quiet gate window, run the serial ply-63 and ply-77 comparisons above. Until then, keep the verified nullfix build, do not roll back based on mate-clamped loss magnitude, and do not promote the PST candidate on an incomplete gate. The missing evidence is completed-depth/PV/root-alternative data for the actual builds, not another aggregate blunder count.
