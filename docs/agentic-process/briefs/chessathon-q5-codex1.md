# chess-q5 — QUICK FRESH-EYES CODEX AUDIT (cheap: thinking low, ~1-1.5h)

Independent audit of the AI Chessathon engine at /home/pino/projects/
chessathon. Goal: fresh eyes on ONE question — the "leak family": the
engine loses games not by single blunders but by bleeding 160-300cp
errors across whole games in positions where its eval hovers near-equal
while it is actually materially worse. Six losses so far (r64/68/70/74/
76/83), every one mistake-dense (5-20 SF-visible bad moves per loss vs
0-3 in wins). r83 was the worst: 12 mistakes + 6 inaccuracies + 2
blunders, 57-FEN corpus in results/leak_suite/fens.json.

## Your job — see if you can SEE something the rest of us missed
Read-only analysis. Deliver ranked, evidence-backed hypotheses + a
concrete recommended next experiment. Specifically address:
1. WHY does the eval hover near-equal in losing positions? A
   compensation clamp was tried (commit 2a115cd, CHESSATHON_COMPCLAMP,
   default OFF — READ IT + BUILD.md P8 + its gate results in PROCESS.md):
   L1 24g@500ms = 0.417 (NEGATIVE). The clamp band: phase≤16 ∧
   |material|≥200 → static eval pinned within 120cp of material. Theory
   says the masking is real (advanced-pawn PST credit +260 vs −220
   material); the fix failed its gate. Is the theory wrong, the band
   wrong, or is the real mechanism elsewhere (search horizon, pruning
   inaccuracies, qsearch, time management)? Point at code lines.
2. The time-management angle: the engine idles roughly half its clock
   (measured: KingsGuard spends ~2×). Could the loss signature be a
   TIME symptom (shallow searches mid-game on easy moves, deep on hard
   ones?) rather than an eval symptom? Look at the time-allocation code
   + the %clk traces in results/matches/round-83-vs-404-not-found.pgn.
3. Rank 2-4 fix directions for a 120s+0.5s competition clock with a
   42-hour freeze (Sep 11 11:00 UTC deadline): expected value × cost ×
   risk. Be concrete: file/line + what changes.

## Context files (read in this order)
- ORIGINALITY.md (compliance — read-only rule: everything shipped must
  be code written in this repo; classical search only)
- PROCESS.md (full history incl. the audit-correction block)
- BUILD.md (design log; P8 = the clamp writeup)
- /tmp/chess-q5-audit2-report.md (the ship-gate audit — F1-F9)
- tools/QUALITY_AB.md + QUALITY_AB.md (replay tooling)
- engine/ (search + eval), agent.py (time management)
- results/leak_suite/fens.json, results/leak_reviews/*.sf16.json,
  results/matches/round-83-vs-404-not-found.pgn (the worst loss)

## HARD RULES
- READ-ONLY: no repo writes, no git operations, no commits. Scratch
  files only in /tmp. You may run python one-liners / tiny reads, but
  NO engine runs, NO replays, NO gates: a real-clock SF19 bout is
  running on this box until ~19:10 UTC — do not touch the CPU with
  engine work. Code reading costs nothing; respect that.
- Competition firewall: never modify anything that ships.
- Provider: codex quota may hit mid-run. If provider errors persist
  ~10 min: write partial findings to /tmp/chess-q5-codex1-report.md
  and exit clean. Never OpenRouter.
- Output: /tmp/chess-q5-codex1-report.md + a chat summary. Verdict
  lines: what you SAW (hypotheses ranked by evidence from the code),
  what you did NOT see, the recommended next experiment.

<!-- source sessions: 2026-09-09T17-08-03-885Z_01a08724 + 2026-09-09T17-11-11-108Z_01a08726 (main run, completed) -->
