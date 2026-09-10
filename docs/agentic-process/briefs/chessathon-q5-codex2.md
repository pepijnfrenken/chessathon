# chess-q5 — codex RE-AUDIT of the night build (round 2, cheap: thinking low)

Read-only fresh-eyes audit of the NIGHT'S changes in
/home/pino/projects/chessathon, accumulated since your round-1 audit
(/tmp/chess-q5-codex1-report.md + /tmp/chess-q5-codex1-experiment/REPORT.md).

## What changed since round 1 (verify each against source + records)
1. `aebee58` — null-child-negation fix (your H1). SHIPPED as v6 (active on
   the ladder since ~20:45 UTC Sep 9). L1 24g@500ms = 16W-6L-2D = 0.708;
   L2 clean on the corrected 78-FEN corpus (ef9ac72). r90+ ladder games
   will be its first real evidence.
2. Leak-suite rebuilt: 78 our-side FENs from PGN headers, 160cp
   threshold, mate-range split (9f108a4) — your contamination finding.
3. NIGHT QUEUE (q5-fix1, ongoing until ~06:30 UTC; git log HEAD will show
   which landed): (a) endgame-eval fixes — your §7 suspects: zero eval for
   pawnless KBN-v-K / KNNN-v-K, and the minors-counter asymmetry at
   eval.py:527-536; (b) PST PAWN-FLIP — your H2: pawn PST rows flipped at
   hand-assembly (eval.py ~289-305) so rank-1-home reads correctly
   (advanced pawns rewarded). Check it is implemented as specified in
   d237640 + docs/research/07-pst-phantom-decomposition.md: pawn rows
   ONLY (king/rook tables untouched this pass), no color asymmetry, no
   shared-mask changes; (c) possibly H3 root-ordering (search.py:813
   best_move into the ordering slot).

## Your job — audit the auditability
1. Read each night commit + its gate record (PROCESS.md latest §, gate
   logs under results/, probe logs). Is the change what the record says?
   Is the gate evidence sound (L1 vs the 0.45 line, L2 on the CORRECTED
   corpus, eg_check/shuffle/determinism, no confounds: box quiet, zero
   flags, correct side pairing)?
2. Check the PST flip for implementation errors: table orientation vs
   documented intent (BUILD.md), color symmetry (White and Black reads),
   the ^56 path, hand-assembly site vs shared masks, EG + MG both flipped.
   Run tools/eval_decompose.py parity checks if cheap (read-only, light
   CPU — a real-clock bout may be running on the box: do not run engine
   games, decomposition probes are fine and short).
3. Endgame fixes: do the crafted KBN-v-K / KNNN-v-K positions now eval
   as wins? Any new edge cases introduced?
4. Anything NEW you see that would block shipping the night build
   (v6.1/v6.2) before uploads close Sep 11 10:00 UTC.
5. Rank: ship-as-is / ship-after-fix-X / don't-ship, with the sharpest
   evidence for each.

## HARD RULES
- READ-ONLY: no repo writes, no git ops, no engine-vs-engine runs, no
  uploads. Scratch files only in /tmp. Engine source hashes before/after
  must match — record them.
- Provider: codex quota may die mid-run — if provider errors persist
  ~10 min, write partial findings to /tmp/chess-q5-codex2-report.md and
  exit clean. Never OpenRouter.
- Output: /tmp/chess-q5-codex2-report.md + chat summary with verdict.

<!-- source session: 2026-09-09T20-55-29-788Z_01a087f4 (aborted at launch; superseded by codex3/codex4) -->
