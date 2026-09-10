# Night2 re-audit, codex4

## Verdict

**SHIP-AFTER-FIX-X. X is release identity and gate-evidence reconciliation, not a speculative engine patch.**

The preserved source snapshots support the intended null-sign + minor-count + pawn-PST correction chain. The completed L1 results are encouraging. I found no new demonstrated defect in the pawn flip or null correction that justifies rolling back to V5.

I cannot sign off on “all gates verified, upload as-is.” The located shuffle output has a threefold failure absent from its located V5 control. It does not match the supplied 10/12 parity record. The reported determinism/KBN/parity outputs were not located. Most importantly, the working source is already night3, while the on-disk agent.zip is still the older V5 archive. Neither is the audited night2 artifact.

Required before upload:

1. Resolve the shuffle evidence discrepancy against the authoritative completed run. Preserve the exact log and source identity. If the located KRvK-close threefold is the applicable result, treat it as a failed shuffle gate, not clean parity. Either establish that it is an accepted baseline/load limitation with applicable evidence or withhold release under the existing gate rule. Do not infer a new pawn bug from this one run.
2. Attach the reported 493,820-node determinism result, KBN +875/zero reproduction, and post-flip decomposition parity evidence to the exact night2 source. Preserve the night gate command/config and source hashes. The supplied reports may describe valid additional runs; the accessible files do not certify them.
3. Package the frozen night2 source, excluding night3 root ordering. Verify archive contents and perform the existing clean-environment init/legal-move check in an authorized quiet window. Do not upload the current agent.zip or blindly rebuild from the working tree.
4. Reconcile BUILD.md/PROCESS.md with the night records and explicitly record any waived/replaced standing quality_ab or real-clock gate. The inspected files still end at the COMPCLAMP episode.

This audit performed no engine import, search, game, replay, gate, upload, git operation, or repository write. The only output written is this requested scratch report. Lightweight computation parsed source bytes, JSON, PGN headers, and saved text results. No engine CPU was used while the gate was active.

## 1. Source chain integrity

I compared every shipped Python source file across the preserved trees. These are snapshot comparisons, not authenticated commit-object inspection. Commit IDs aebee58, 3c06692, f5ce5de, 5458b48 and a1feaf5 come from the brief. Their precise commit metadata cannot be certified under the no-git-operations rule.

| Transition | Observed shipped-source difference | Finding |
|---|---|---|
| /tmp/chessathon_v5ref -> /tmp/chessathon_n1base | engine/search.py only | Null child negation after TIMEOUT handling, then compare/return null_score. No guard or reduction changes. |
| /tmp/chessathon_n1base -> /tmp/chessathon_n2base | engine/eval.py only | Count knights as minors and replace the old two-part draw zeroing with total minors <= 1. |
| /tmp/chessathon_n2base -> /tmp/chessathon_n3base | engine/eval.py only | Reverse pawn MG and EG rows at hand assembly; also remove one selfcheck assertion and its two FEN fixtures. |

All shipped Python files in /tmp/chessathon_n1base match /tmp/chess-v6-nullfix.zip byte-for-byte. That corroborates the V6 baseline identity used in the r90 audit. The zip SHA-256 is 71c172ee28a72ae3db0ec3731a2d33b8e8cb5b22b6c39a5fb82a0762346d4322.

### Null correction

engine/search.py:573-605 restores board state, checks TIMEOUT, computes `null_score = -child`, and compares/returns that value. This implements the round-1 runtime finding without changing null eligibility. The prior experiment actually reached wrong-sign cutoffs; this is not merely a stylistic correction.

### Minor zeroing

engine/eval.py:533-543 counts both knights and bishops. Lines 695-699 zero only pawnless/majorless positions with at most one total minor. KBN-v-K and KNNN-v-K no longer enter the forced-zero branch. This is broader than a KBN special case, appropriately so. The old second condition also incorrectly zeroed other minor combinations.

The mirror was updated consistently in tools/texel_tune.py:193-202,299. The only differences in that mirror between the first two night snapshots are knight counting and the matching forced-zero predicate.

This remains a conservative, incomplete insufficient-material recognizer. For example, multiple bishops restricted to one square color can describe a dead position not covered by `mins <= 1`. That is a known limitation of this predicate, not evidence that KBN should be restored to zero. Nonzero KBN evaluation also does not prove reliable bishop-and-knight mate conversion; the standard eight-case eg_check does not exercise KBN.

### Pawn orientation

engine/eval.py:289-311 reverses the eight rows of _PAWN_MG and _PAWN_EG once during hand-parameter construction. It does not reverse individual ranks horizontally, change numerical weights, flip king/rook tables, or touch pawn/shelter masks. The consumer at :477-480 still uses White direct indexing and Black xor-56 indexing. Both colors receive the same corrected relative-rank profile. Tuned parameters remain separate; hand is the shipped default at :422-428.

There is one additional non-runtime change. The night2 diff removes the selfcheck comparing doubled c2/c3 pawns with split d2/c3 pawns. That full-evaluation inequality also changes PST and passer effects, so it does not isolate a doubled-pawn penalty. Its deletion is not by itself evidence of a concealed shipping failure, but “only two assembly assignments changed” would be literally incomplete. The advancement check remains.

### eval_decompose limitation

The tool reads E.EVAL_PARAMS, so its PST totals consume the corrected hand vector without requiring another flip. Its forced-zero mirror is consistent with the engine. However, tools/eval_decompose.py:39-50,118-135 does not assert equality or assemble a complete final score including mate-drive. It prints the real engine result beside component data. The enriched /tmp/q5b_decomp_full.json includes fields such as mate_drive that this checked-in tool does not emit.

The saved 45-row decomposition belongs to the earlier orientation investigation. It is not a located post-night2 runtime parity certificate. Do not equate source consistency or printing an engine score with an executed bit-parity assertion. No new parity run was attempted during the active gate.

## 2. Gate records

### L1 arithmetic and scope

I recomputed results from individual game lines using the alternating candidate-color mapping in tools/gate_match_tree.py:62-84.

| Saved result | Recomputed W-L-D | Score | Flags |
|---|---:|---:|---|
| results/gate_q5fix1_vs_v5.log | 16-6-2 | 0.708 | Every game [] |
| results/gate_night1_egfix_vs_v6.log | 12-6-6 | 0.625 | Every game [] |
| results/gate_night2_pstflip_vs_n1.log | 24-0-0 | 1.000 | Every game [] |

The alternating 1-0 / 0-1 night2 results really do mean 24 candidate wins, not a mistaken color tally. All 24 end before the 300-ply cap. The source imports the requested tree before engine imports, warms search, and supplies explicit hand:1111 settings with experimental toggles off. I found no source-level side-selection bug that explains the sweep.

The night1 file includes its command configuration and baseline path. The night2 results file is identical to /tmp/q5b_out/gate_n2.log and contains only stdout game lines plus the summary. It lacks the header that the current gate script normally writes. The earlier r90 process observation independently identifies the night2 command against /tmp/chessathon_n2base, but the results file alone is not a reproducible build manifest. No per-game PGNs or process/source hashes accompany it.

“Zero flags” has a narrow meaning here. tools/sprt.py:93-139 checks process errors, UCI legality, unexpected null moves, and a coarse game timeout. It does not enforce the competition's 120s+0.5s clock or measure a 60-second import deadline. The read from a child is blocking. The fixed-500ms engine worker bypasses agent.py time allocation. These logs therefore do not certify absence of venue clock flags or production init overruns.

### L2 corrected corpus

Verified by lightweight JSON/header parsing:

- 78 corpus rows.
- Zero mismatches between row side, FEN side to move, and En Passant Labs' color in the saved PGN headers.
- Every ID/FEN in both /tmp/q5b_chunks/n2_0..3.json and cand_0..3.json matches the corrected corpus exactly, excluding WARMUP.
- All 78 score/move/depth comparisons in results/probe_night2_pstflip_diff.txt match raw /tmp/q5b_out/n2_c0..3.txt and cand_c0..3.txt.
- Mean candidate-minus-baseline score change is -95.884615cp. There are 34 changed moves and one score decline of at least 300cp.

The “V5” column is the comparator's hard-coded label. Its rows match the saved q5cand/nullfix outputs, not the raw v5 outputs. Preserve the actual baseline identity rather than relying on that printed label.

The one flagged row is r68 relative ply 41. The old internal score is 0, candidate -771, and cached referee evaluation before the move is -1276 (results/leak_suite/fens.json:202-210). The candidate internal estimate is closer to that cached referee estimate. This supports treating the -771 delta as recalibration in a lost position, not automatically a 771cp move regression.

Crucial limitation: /tmp/q5b_analyze.py:24-31 only subtracts each engine's own searched score. It never asks an independent referee to compare their chosen moves from the same parent FEN. Thus neither “mean -95.9 toward truth” across the entire corpus nor “zero independently measured move-quality regressions” follows from this output. The flagged row's closeness does not establish that g6f5 is better than e7e5. The worker uses fresh TT/history per FEN and empty pre-root history, not ladder state. These are diagnostic probes, not a real-clock replay gate.

### Endgame, shuffle, determinism and box state

- /tmp/q5b_out/eg_item1_300.txt and eg_item2_300.txt each contain eight wins, including KPK-b. These corroborate the reported eight-case outcomes. They were not found under results/ and do not embed source hashes or invocation metadata.
- /tmp/q5b_out/shuffle_item2_2000.txt has **11 wins, one draw**. Line 9 reports KRvK-close strong-as-white, ply 150, with third occurrences at plies 139-144 and `THREEFOLD`.
- /tmp/q5b_out/shuffle_v5ctl_2000.txt also has **11 wins, one draw**, but its draw is KPK-white and it has no third occurrence. It wins KRvK-close-white.
- These are not the supplied 10/12-parity artifacts. Equal aggregate wins would not erase the change in failed case or the threefold. The checker treats failed conversion of a must-convert case as failure (tools/shuffle_check.py:172-178). Existing timing flakiness is a plausible explanation, not a proven dismissal.
- I did not locate the reported 493,820-node twin-process result or the KBN +875 runtime probe in results/ or the identified scratch output directory. /tmp/det_head.txt instead contains an older 1,686,741-node baseline. This is an evidence gap, not a claim that the reported checks were never run.
- No historical quiet-box attestation was located for the night runs. Current process inspection found the active **night3** gate against /tmp/chessathon_n3base and both engine workers. I did not interfere. Current activity cannot prove or disprove historical contention.

## 3. Shipping interpretation

The r90 verdict still supports keeping V6 rather than restoring the proven null-sign bug. The completed night2 L1 sweep satisfies the earlier report's pending-L1 condition. It does not establish that the pawn flip saves 39...Nf8 or 46...Kg2. The prior report correctly distinguishes the earlier collapse from a later detected-mate transition.

Night2's L1 opponent was night1, not ladder-active V6. Night1 itself scored 0.625 against V6 in a separate small sample, so it is not established to be weaker than V6. It is the weaker side in the night2 match. Strength is not transitively quantified by these scores. Neither multiplying scores nor interpreting 24/24 as an expected ladder win probability is valid.

All three are 24-game fixed-seed screens, not broad Elo estimates. The gate samples from eleven openings, selects a fresh opening inside each color leg rather than guaranteeing same-opening pairs, and retains killer/history arrays between games even though it clears TT/game keys. Repeated openings and persistent heuristic state further limit independence. The sweep is substantial evidence against that sibling in this harness, but its magnitude can overstate general gain against V6 or the ladder pool.

The repository's earlier standing policy called for quality_ab and, for eval changes, a real-clock referee bout (PROCESS.md:377-398; docs/research/07-pst-phantom-decomposition.md:129-134). No night2 completion of those was located. L2 internal-score comparisons are not a substitute. If the operator intentionally replaced that policy with the night gate chain, record that decision explicitly rather than silently declaring the old policy satisfied.

## 4. Release identity and freeze risks

The current working tree differs from the preserved night2 tree only in shipped engine/search.py. It now passes `best_move` into root ordering instead of zero. That is the separately staging night3 change. This audit does not approve it.

The current repository agent.zip has SHA-256 6abb1ca1affa559bfbcc0539979385941bbc26bc40246168b25f89a36b3c970c. Its search.py and eval.py differ from night2. The frozen V6 zip also differs from night2 in eval.py. No inspected zip is the complete audited night2 build.

For a byte-level release check, the preserved night2 /tmp/chessathon_n3base shipped sources have these SHA-256 values:

| File | SHA-256 |
|---|---|
| agent.py | c67cefd50b040191c655526d9ca96b2ac228793eaf26e43b78dec2fdbe2bf296 |
| engine/search.py | b917b93997498c3c5bf551d821561fff21a23c72c07a0120268b82d625ecba0c |
| engine/eval.py | b1dd2413e9485fce0148d5d55c50af3ae765048ae2f86f09a877bf69229fc63d |
| engine/board.py | c36229c95986b2ab5d44872c06a0cd24049cc0d90bf732c1448a0dcec258d814 |
| engine/tt.py | c42fd2300577777b35b2994fb78cb4eeac5f4e0ce68285029ca75b58cc07562b |
| engine/time.py | 258de7ae09cd4a6b92ddd5923390817f685ed6bf886bb2918953a68cb10239ae |
| engine/__init__.py | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |

These hashes identify inspected bytes, not an authenticated mapping to f5ce5de. Release ownership must bind that mapping and the gate records before upload.

No reason emerged to bundle king/rook PST changes, COMPCLAMP, new null reductions, time management, or a speculative r90 mate patch. Resolve the evidence and artifact issues, preserve the three-fix scope, and use the stated Sep 11 10:00 UTC cutoff rather than ambiguous older local-time prose. The planned pre-07:00 UTC upload is a scheduling target, not a reason to label an unresolved gate clean.
