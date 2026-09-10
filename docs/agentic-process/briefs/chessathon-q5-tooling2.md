# chess-q5 — TOOLING validation, RESUME (q5-tooling2)

You are resuming a tooling-validation mission for the AI Chessathon engine
repo (/home/pino/projects/chessathon, branch main). The previous run
(q5-tooling, deepseek model) worked ~10 min then died at 07:33 UTC to
provider errors — it made NO commits, NO repo changes, and produced NO
output in results/quality_ab/. Its only artifact: /tmp/qa_pass1_check.py
(a clock-coverage checker it wrote; you may reuse or discard it). Start
from scratch on the mission below — nothing is done yet.

## Mandatory reading first (10 min, in order)
1. ORIGINALITY.md — the competition's originality law.
2. CLAUDE.md + PROCESS.md — master log; you append ONE short entry at the end.
3. tools/quality_ab.py — the instrument you validate (committed 89971a6).
   Read its docstring fully before running anything.

## Mission context
Pre-freeze (uploads stop Sep 11 11:00 UTC). Ship bar for engine changes
will include a LOCAL QUALITY A/B (tools/quality_ab.py): replay a candidate
build against REAL ladder games with exact %clk clocks, SF19-referee the
real game and the replay, classify V5's blunder/mistake plies as
retained/avoided/replaced-worse/unreached. Your job: prove the instrument
trustworthy (self-test), fix bugs it exposes (minimal diffs), document it.

## Repo state note (changed since the original brief was written)
- results/matches/ was refreshed at 07:41 UTC from the official dashboard:
  rounds r48-r76 now all present as PGN+log (including the previously
  missing r51-r60, r75 = WIN vs Prophylaxis, r76 = LOSS vs MCAI played
  09:09 07:30 UTC). For r61-r74 the moves are byte-identical to before
  (verified); headers were normalized. Corpus games for this mission are
  UNCHANGED in content.
- results/leak_reviews/ now contains all 7 SF16 review JSONs
  (round-64/68/70/71/72/73/74-vs-*.sf16.json, written 07:15-07:29 UTC) —
  quality_ab reuses them; do not regenerate unless missing.

## Steps
1. SELF-TEST single game (the decisive check) — run from repo root:
     /tmp/chessbench/bin/python tools/quality_ab.py --candidate HEAD \
       --game round-74-vs-rohan.pgn:white --out results/quality_ab/selftest-r74
   Expectation: candidate == HEAD reproduces the real game — fidelity
   (matched/our_moves) >= 90% on the exact %clk clocks — and SF19 bucket
   stats V5 vs candidate are ~equal. The tool prints a SELF-TEST line.
   If fidelity is low or stats differ wildly, decide: machine artifact
   (a move overran its budget on this box under CPU load → RETRY the run
   once when the box is quiet before suspecting the tool) vs TOOL BUG.
   Debug candidate list (minimal diffs, keep the CLI stable, commit as
   "[qa] ..."): (a) exact-clock extraction/alignment (off-by-one, book-FEN
   games where black moves first), (b) replay PGN construction
   (headers/SetUp-FEN, recorded moves), (c) review caching path, (d)
   leak-classification k-index alignment. Do NOT redesign the tool.
2. FULL CORPUS self-test (same expectations; all 7 games):
     --game round-64-vs-snake.pgn:black --game round-68-vs-rook-and-roll.pgn:black
     --game round-70-vs-kingsguard.pgn:black --game round-74-vs-rohan.pgn:white
     --game round-71-vs-magnus.pgn:white --game round-72-vs-stocked-fish.pgn:black
     --game round-73-vs-skylab.pgn:black
     --out results/quality_ab/selftest-corpus
3. Write tools/QUALITY_AB.md (usage, interpretation of verdict checks,
   LIMITS: proxy opponent follows the PGN; per-move scoring at fixed
   depth; replay divergence as machine artifact when a move overruns its
   budget). Commit "[tools] QUALITY_AB.md ...".
4. Append ONE dated section to PROCESS.md (tooling area): quality_ab
   instrument validated with per-game self-test fidelity numbers. Do NOT
   restructure PROCESS.md.

## Constraints
- PY=/tmp/chessbench/bin/python for anything importing python-chess/agent.
- One CPU-heavy job at a time; SF reviews spawn Threads=6 each — sequential
  only. No 500ms gates, no parallel review_sf. Replays are real-clock:
  if the box feels loaded (another process was killed before you started;
  nothing else should be heavy now), a low-fidelity self-test should be
  retried ONCE before being called a bug.
- TOOLING ONLY: never touch ORIGINALITY.md, agent.py semantics, engine/,
  or the eval. Local commits only; no pushes. Commit evidence files a
  commit message references. Time budget ~3-4h; if stuck >20 min write a
  PARTIAL deliverable into results/quality_ab/ and commit; never claim a
  run you did not complete — every number must trace to a file on disk.
- Self-contained brief: do not ask questions; decide and document.
- FreeInference API: on 429/empty/error responses wait 20-60s and retry
  (up to ~10 attempts with backoff); if the model returns empty content
  3+ times in a row, STOP and report rather than looping.

## Final summary must include
- fidelity fractions per game (both runs) + REPORT.md paths
- every bug found + fix commit hash (or "no bugs found")
- tools/QUALITY_AB.md path; git log --oneline -3
- one-line verdict: "instrument ready for candidate A/B" or what blocks it.

<!-- source session: 2026-09-09T07-47-15-915Z_01a08522 -->
