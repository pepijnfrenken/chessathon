# chess-q5 — FIX ROUND: null-sign correction + PST diagnostic (v6 candidate prep)

Repo: /home/pino/projects/chessathon. Read ORIGINALITY.md first, then
PROCESS.md (§8 operating rules, §11 COMPCLAMP close, §10 audit), BUILD.md.
LIVE-COMPETITION firewall: NEVER modify agent.py / engine files that
currently ship in a way that changes V5 behavior OUTSIDE this experiment;
candidate work only, gate before ship. Everything ships = our own code.

## Mission A (primary): null-child-negation fix, gated alone
Codex audit (read /tmp/chess-q5-codex1-report.md §H1 + the runtime
experiment /tmp/chess-q5-codex1-experiment/REPORT.md, artifacts in
/tmp/chess-q5-codex1-experiment/) proved `engine/search.py:597-600`
compares the opponent's un-negated child score against our beta:
- It accepts invalid cutoffs (opponent +232 read as our +232 vs beta 149)
  and rejects ~23k valid ones in a 12-position probe set; wrong-sign
  acceptances appeared in all 12 positions with real search.
- Correcting the sign (null_score = -child, then compare/return it)
  cut nodes 20.1% / time 17.3% at fixed depth-8, changed 2 root moves,
  with no measured move-quality regression (13-position paired referee).

YOUR JOB:
1. Implement the correction IN THE REPO at search.py:597-600 (the
   exact-site fix ONLY: negate the child score before the beta compare
   and before returning it on cutoff; nothing else — no reduction
   changes, no guard changes, no NULL_DEEP revival, no eval changes).
   One focused commit. Expect the tree/node counts to differ from V5 —
   that is the point; determinism = same-input-same-output per build,
   not identity with V5.
2. Gate A (L1): 24 games @500ms vs the V5 baseline (HEAD~1 or the
   shipped build via the repo's dual-engine gate harness, hand:1111
   both sides, seed 7 — follow the exact pattern in the last gate log
   results/gate_compclamp_vs_head.log + BUILD.md P8 description).
   Decision line 0.45 (same as P8).
3. Gate B (L2): leak-suite probes on the CORRECTED corpus
   results/leak_suite/fens.json (78 real our-side FENs, rebuilt today
   from PGN headers; NOT the old contaminated 57 — do not regenerate
   it, do not use the old file). tools/leak_probe.py or the P8-era
   probe tooling at 2.6s budget; compare candidate vs V5: no new
   ≥300cp regressions on our-side moves; report per-FEN eval/move
   deltas. Also probe the mate_stratum.json rows separately as a
   diagnostic stratum (label them clearly).
4. Sanity gates: perft/shuffle pass (existing tooling), eg_check 8/8
   or 7/8 matching the V5 control exactly, legality + init checks,
   no crashes. 60s init under 60s.
5. NO real-clock SF bout tonight (box allocation + time budget) — L3
   comes tomorrow before any upload decision. Do NOT upload anything.

## Mission B (diagnostic prep, light CPU only): PST orientation terms
Codex audit H2: PST tables look vertically inverted vs documented
intent (home pawns e2/e7 credited 50/80 EG, advancing punished; MG
king g8 +30 vs castled g1 -40). The runtime experiment showed the
engine's own static eval says Black +78..+318 before the r83 leaks
while the referee says -545..-174 — the evaluation has a large blind
spot, but nobody has decomposed WHICH terms produce the phantom.

YOUR JOB (pure eval calls + arithmetic, no engine-vs-engine games):
1. Reuse the experiment's positions (/tmp/chess-q5-codex1-experiment/
   positions.json) + results/leak_suite/fens.json + r70-B FEN from
   results/sims-v5/probe_v5_evals.log. Decompose our static eval on
   the pre-leak FENs (r83 relative plies 21/29/31/35/39/41/75/77,
   r70 B, r64/r74/r76 loss FENs): material, pawn PST, piece PST,
   king PST (MG+EG separately per side), pawn-structure terms,
   mobility/activity, tempo. Term-by-term tables, White AND Black POV.
2. Identify which terms carry the phantom +318-style credit and what
   positional feature they reward. Specifically test: does the king
   PST (as read for each color after ^56) reward a king on its OWN
   back rank, the enemy back rank, or the side it should not? Does
   the pawn table punish advancement consistently?
3. Write a ranked list of the TOP eval-term suspects with numbers and
   table coordinates, as the spec for tomorrow's PST ablation
   (pawn-only first, king separately — do NOT change eval code today).
4. Sanity-check BUILD.md's documented intent (e.g. castle-back king
   prose at BUILD.md:74-76) against the measured coordinates.

## Output
- Commits: (A) fix + gate logs; (B) diagnostic writeup under
  results/sims-v5/ or docs/research/ (append-only, follow repo layout).
- PROCESS.md §12 entry + BUILD.md note for the fix round.
- Final summary: L1 number vs 0.45, L2 verdict, determinism/sanity
  results, and an upload-recommendation for the null-fix candidate
  (v6) — plus the ranked PST suspects for tomorrow.

## Rules
- One engine process at a time on the box; check emptiness
  (ps aux | grep -E 'stockfish|gate|replay') before every gate run.
- No COMPCLAMP. No NULL_DEEP. No time changes. No agent.py behavior
  changes. No uploads. No OpenRouter. GLM lane only.
- Commit after every milestone. Append PROCESS/BUILD at the end.
- Timebox: ~3h. If a gate wedges, note it, kill it, re-run once.

<!-- source session: 2026-09-09T18-33-00-740Z_01a08771 (night queue; final commit 2026-09-10 01:19Z) -->
