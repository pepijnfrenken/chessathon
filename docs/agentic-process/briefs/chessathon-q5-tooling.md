# chess-q5 — TOOLING: validate the quality-A/B instrument (quality_ab.py)

You are a tooling-validation builder for the AI Chessathon engine repo.
Repo: /home/pino/projects/chessathon (branch main, clean at 89971a6). Local
dev python that mirrors the venue box: /tmp/chessbench/bin/python (has
python-chess, numba, numpy). SF19 referee binary: ~/.local/bin/stockfish.

## Mandatory reading first (10 min, in order)
1. ORIGINALITY.md — the competition's originality law. Everything committed
   must be code written in this repo during the event.
2. CLAUDE.md + PROCESS.md — master log; you will append ONE short entry.
3. tools/quality_ab.py — the instrument you are validating (committed
   89971a6, ~360 lines). Read its docstring fully.

## Mission context
We are pre-freeze (uploads freeze Sep 11 11:00 UTC). The ship bar for any
engine change will now include a LOCAL QUALITY A/B: replay a candidate
build against REAL ladder games (results/matches/round-*.pgn) with exact
%clk clocks, SF19-referee both the real game (shipped V5) and the replay
(candidate), and classify V5's blunder/mistake plies as retained / avoided
/ replaced-worse / unreached. quality_ab.py implements this. Your job:
prove the instrument trustworthy (self-test), fix any bugs it exposes
(minimal diffs), and document it.

## Step 1 — self-test, single game (the decisive check)
Run (from repo root):
  /tmp/chessbench/bin/python tools/quality_ab.py --candidate HEAD \
    --game round-74-vs-rohan.pgn:white --out results/quality_ab/selftest-r74
Expectation: candidate == HEAD means the replay should reproduce the real
game — fidelity (matched/our_moves) >= 90% using the exact %clk clocks
embedded in the PGN — and the SF19 bucket stats for V5 vs candidate must be
~equal. The tool prints a SELF-TEST line. If fidelity is low or stats are
wildly different, diagnose: is the replay diverging because of budget
overruns on this machine (machine artifact) or because of a TOOL BUG?
Debug candidate list (in order): (a) exact-clock extraction/alignment
(off-by-one, book-FEN games where black moves first), (b) replay PGN
construction (headers/SetUp-FEN, recorded moves), (c) review caching path
(results/leak_reviews/*.sf16.json reuse), (d) leak-classification k-index
alignment. Fix with MINIMAL diffs, keep the CLI stable, commit as
"[qa] ...". Do not redesign the tool.

## Step 2 — full corpus self-test
Run all 7 corpus games (each is a real ladder game; side = the side OUR
engine played in the real match):
  /tmp/chessbench/bin/python tools/quality_ab.py --candidate HEAD \
    --game round-64-vs-snake.pgn:black \
    --game round-68-vs-rook-and-roll.pgn:black \
    --game round-70-vs-kingsguard.pgn:black \
    --game round-74-vs-rohan.pgn:white \
    --game round-71-vs-magnus.pgn:white \
    --game round-72-vs-stocked-fish.pgn:black \
    --game round-73-vs-skylab.pgn:black \
    --out results/quality_ab/selftest-corpus
The tool reuses results/leak_reviews/<game>.sf16.json when present (a
parallel battery has been writing these all day; 7 exist or are about to —
round-64/68/70/71/72/73/74-vs-*.sf16.json). If one is missing: poll up to
15 min (its battery may still be writing — check file mtime is fresh); if
it never appears, let the tool regenerate it (review_sf at depth 16, slower
but safe). Never run two review_sf processes concurrently on purpose; the
reviews are CPU-heavy (Threads=6 each).

## Step 3 — document + log
1. tools/QUALITY_AB.md: usage (one command block), interpretation of the
   verdict checks, and LIMITS (proxy opponent follows the PGN; per-move
   scoring at fixed depth; replay divergence = machine artifact when a move
   overruns its budget). Commit "[tools] QUALITY_AB.md ...".
2. Append ONE dated section to PROCESS.md under the tooling/evidence area:
   "quality_ab instrument validated (self-test fidelity per game)" with the
   numbers. Do NOT restructure PROCESS.md.

## Constraints (baked in)
- PY=/tmp/chessbench/bin/python for everything that imports python-chess
  or agent/engine code.
- One CPU-heavy job at a time (no gates, no parallel SF reviews). SF
  reviews and replays are real-clock/load-sensitive.
- Never touch ORIGINALITY.md, agent.py semantics, engine/ code, or the
  eval — this mission is TOOLING ONLY.
- Local commits only, no pushes, no network uploads. Commit evidence files
  (REPORT.md, report.json) that a commit message references.
- Time budget ~3-4h. If a step is stuck >20 min, write a PARTIAL
  deliverable (what ran, what you found) into results/quality_ab/ and
  commit; never claim a run you did not complete. Every number in your
  final summary must trace to a file on disk.
- The brief is self-contained — do not ask questions; decide and document.

## Deliverables / final summary must include
- fidelity fractions per game (both runs) + paths of the REPORT.md files
- every bug found + fix commit hash (or "no bugs found")
- tools/QUALITY_AB.md path
- git log --oneline -3
- One-line verdict: "instrument ready for candidate A/B" or what blocks it.

<!-- source session: 2026-09-09T07-22-50-451Z_01a0850c -->
