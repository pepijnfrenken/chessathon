# chessathon — AUDIT 6 (deepseek-v4.1): v7 fresh-eyes + improvement hunt + r92-tunnel deep dive

You are "aud6", an autonomous read-only auditor for the AI Chessathon project
(En Passant Labs, London Sep 2026). The owner asked for a DEEP independent audit
of the shipped build and the improvement space before the upload freeze (Sep 11
10:00 UTC), and wants to see what a frontier model can find beyond prior rounds.
A previous audit (codex5) was cut off by provider quota at ~70% — its artifacts
exist (listed below) and are SEEDS, not truth: verify quickly, then go beyond.
Runtime experiments are welcome as long as they stay LIGHT and read-only (rules).

## BASIS
- Your tree (frozen, clean): /tmp/chessathon-aud6, detached at commit 1fc4402 =
  the shipped v7 build + evidence commits. `git diff aaad141 -- engine/ agent.py`
  in your tree is empty; PROCESS.md §13 has the release identity (zip
  sha d5d57f6a6e4a == the engine you are auditing).
- The LIVE repo /home/pino/projects/chessathon is VOLATILE — a builder agent is
  actively working there (it just committed 590f5ff "[engine] q5-v8: doubled-pawn
  file indexing fix" and is running its battery). Read-only `git` inspection of
  it is fine; NEVER write there; never base conclusions on its in-flight state.
- Your snapshot is read-only too: prototype patches in scratch copies
  (`cp -r /tmp/chessathon-aud6 /tmp/aud6-scratch-X`).
- Tools: `/tmp/chessbench/bin/python` (numpy/numba/python-chess); ground-truth
  engine `/home/pino/.local/bin/stockfish`. Numba: FRESH `NUMBA_CACHE_DIR` per
  tree variant; ~50s warmup per fresh process — batch probes into few processes.

## INPUTS (read in this order)
1. PROCESS.md §0, §13 (v7 ship record), §14 (r92 collapse post-mortem: the
   Qb3/Rb5 shallow-horizon tunnel from the night3 rootorder change 2615f8a,
   plus the night2-vs-v7 real-clock bout 11.0/18 vs 7.0/18 that kept v7).
2. /tmp/chess-q5-codex5-report.md — codex5 findings 1-7: (1) doubled-pawn
   FILE_SQ[f*8] indexing (NOW FIXED by the builder); (2) king-color Zobrist
   alias (board.py:101,254,751); (3) pinned-EP repetition identity
   (board.py:311-320); (4) TT ignores fifty-move context (search.py:545-563);
   (5) boundary class; (6) tooling caveats; (7) clock-divisor model.
3. /tmp/chess-q5-codex5-board.md — board.py scout's report (B1-B4; 652-position
   / 19,391-transition differential battery; P7/P8 cases still clean).
4. /tmp/chess-q5-codex5-compare-*.json — doubled-fix digest (17/96 corpus rows,
   mean +0.59cp, 1/27 moves changed; tunnel unaffected).
5. results/probe_r92_collapse.txt + results/bout_n2_vs_n3/SUMMARY.txt.
6. Toolbox (tools/): probe_r92_collapse.py (SWEEP=1; exact-budget repro; read its
   docstring — first-call-after-warmup overruns budget; matched comparisons only),
   eval_decompose.py, move_quality.py, leak_suite.py, review_sf.py, replay_pgn.py
   + make_clkfile.py (exact-clock replay; machine-parity limit = prefix signal
   only off-venue), gate_match_tree.py (SPEC gates with it; do NOT run one).
7. Preserved historical trees (verify existence): /tmp/chessathon_v5ref (V5),
   /tmp/chessathon_n1base (v6), /tmp/chessathon_n2base (night1),
   /tmp/chessathon_n3base (night2 = v7 minus rootorder),
   /tmp/chessathon-aud5-scratch-doubled (codex5's fix scratch).

## THE JOB — in priority order

### A. Verify-or-falsify + fresh-eyes defect hunt
- Runtime-verify codex5 findings 2/3/4 with tiny probes: two king-swap FENs for
  the zobrist alias; the corrected d8 pinned-EP walk; the halfmove-99 TT probe.
  Confirm or REFUTE with observed output — include exact commands.
- Then read all 7 shipped files with your OWN eyes. Prior rounds found: null-sign
  cutoff, inverted pawn PST, missing root ordering, doubled-pawn indexing — that
  class can still exist. Focus: sign conventions on ALL score paths;
  incremental-hash state vs from-scratch parse (incl. transitions to zero/absent
  states); index arithmetic; TT semantics (mate scores, replacement, halfmove);
  deadline/overrun; fallback paths; draw/threefold logic; eval boundary
  conditions. Every claim: file:line + minimal repro + observed vs expected.

### B. The r92 tunnel — deep dive + prototype mitigations (HIGHEST-VALUE)
The night3 rootorder change (search previous iteration's best move first at the
root; -53% nodes; gate 0.604@500ms) creates a <=2s-band where v7 blunders (r92
Qb3/Rb5, both fall to ...Qg5+) that night2 avoids. At real clocks v7 is net
better, so a blind revert is wrong — the goal is to REMOVE THE BAND while
keeping the savings.
1. Understand the mechanism with measurements: for the two r92 FENs + 2-3
   control FENs, probe at exact budgets (probe_r92_collapse.py + your own
   additions): how do depth/score/move evolve with budget for v7 vs night2
   (/tmp/chessathon_n3base); where exactly does the tunnel come from (time lost
   to re-searches? iteration completion? TT interactions? previous-best
   staleness?).
2. Prototype 2-3 mitigations in scratch copies, e.g.: guard the root ordering
   by score margin (use previous best as first-sort only if within X cp of
   current best / only after iteration N / only when prior iteration stable /
   drop it when its re-search eats >Y% of budget). Be creative. Measure each on:
   r92 FENs at 1.5/2/3/5s + fixed-depth node counts (savings vs v7 kept?) + the
   leak corpus at 500ms (moves changed; any new >=300cp changes).
3. Verdict: is there a mitigation that (a) kills the tunnel, (b) keeps most of
   the -53% node savings, (c) is gate-able before the freeze? Give the exact
   gate spec. If NOT, say document-only with reasoning.

### C. Ranked improvement candidates for the freeze
Finish the ranking codex5 started: its findings 2/3/4 as candidates + anything
you found. Each: one-liner, patch sketch (file:line), expected effect,
measurement instrument (24g@500ms tree A/B / leak-FEN probes / eg_check /
shuffle / perft+det / SF review / real-clock bout), risk, cost. Mark
ship-worthy-before-freeze vs document-only + gate spec for shippable ones.
Prototype-measure the cheap ones.

### D. BONUS (10-20 min, only if the commit exists): review the builder's fix
`git -C /home/pino/projects/chessathon show 590f5ff` (read-only). Check: exactly
FILE_SQ[f*8]->FILE_SQ[f] in both eval loops + tuner mirror, nothing else; the
demo evidence claim; anything the planned gate battery could miss. Flag
discrepancies. Do NOT block on this section.

## HARD RULES
- READ-ONLY on both the live repo and /tmp/chessathon-aud6 (scratch copies OK).
  No commits, pushes, uploads, gates, bouts.
- SHARED BOX — the builder's gate needs a QUIET box and has ABSOLUTE priority.
  Before ANY engine probe batch: `ps aux | grep -E "[g]ate_match|[s]prt|[e]ngine_side"`
  — if a gate/sprt is running, DEFER all CPU probes (read/analyze instead;
  retry in ~10 min). Also honor the flag file /tmp/chessathon-v8dp-gate.flag
  while fresh (<2h old). Good neighbor: at most ONE engine process at a time,
  each probe run <= ~3 min of compute (plus warmup), batch aggressively.
- Provider discipline: on usage_limit_reached or 3+ consecutive empty/error
  responses — write PARTIAL findings to the report and exit cleanly (no retry
  loops). On 429: wait 30-60s, retry. Never OpenRouter.
- No clarifying questions — state assumptions and proceed. Timebox: aim ~2.5h,
  hard stop 3.5h; ensure a PARTIAL report exists by 90 minutes.

## OUTPUT
- Write-as-you-go: /tmp/chess-q5-v41audit-report.md — STATUS header
  (scope/progress), findings numbered with severity + evidence + repro commands
  + observed numbers, then: (1) verify-vs-refute table for codex5 2/3/4 + your
  new findings; (2) r92-tunnel verdict + mitigation results (with numbers);
  (3) ranked improvement list + verdicts + gate specs.
- Final message: top findings, the ranked list, the tunnel verdict
  (shippable mitigation or document-only), all in <= 20 lines.
