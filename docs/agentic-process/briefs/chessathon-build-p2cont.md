# CHESSATHON BUILD — Phase 2 CONT (finish eval-tuning + gates + zip)

A previous agent (phase2) built and committed the parameterized eval
(commit f4e13e4: material+PST+pawn structure+mobility+king safety+endgame
terms, gateable term groups via env: CHESSATHON_EVAL_CONFIG / CHESSATHON_EVAL_GATE)
and the SPRT tool (tools/sprt.py, uses tools/engine_side.py + tools/common.py).
It DIED before finishing. Your job: finish the phase — do NOT rebuild what
exists. Verify first, then complete.

## MANDATORY FIRST (read before ANY code)
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW (fresh code only,
   no fetched engine code; cite any seeded values in BUILD.md).
2. `/home/pino/projects/chessathon/BUILD.md` (read 1a/1b/phase2 context)
3. `/home/pino/projects/chessathon/docs/research/02-eval-and-tuning.md` §6-7
   (Texel + SPRT discipline)
4. Inspect the CURRENT state: git log, engine/eval.py (the f4e13e4 eval),
   tools/sprt.py, tools/engine_side.py, tools/common.py, tools/local_game.py,
   agent.py — understand exactly what exists before changing anything.
Acknowledge ORIGINALITY.md in your final summary.

## Environment
1 core, 2GB, no GPU. numba cache=False (segfaults w/ cache on). NO torch at
runtime. 60s init. NUMBA_CACHE_DIR=/tmp. State persists between moves.

## Your tasks (in order)

### 1. Sanity-check the new eval first
- Run perft parity quick (2 positions d1-4) — eval changes must not have
  broken the board (tools/perft_check.py exists).
- Run the nps bench (tools/bench_nps.py) — confirm nps still >= ~400 knps
  (richer eval must stay cheap). Report numbers.

### 2. SPRT: new eval vs 1b eval (the A/B gate)
- tools/sprt.py exists and is documented. Run it: side-a = f4e13e4 full eval
  (default config), side-b = 1b flat eval (material+PST only — use the gate
  env: CHESSATHON_EVAL_GATE to disable the new term groups, e.g. gate=0000 or
  whatever the eval's gating convention is — READ engine/eval.py to get the
  exact env var convention right).
- Fixed short TC (e.g. 300ms/move or 10s+0.1s), varied openings (tools/common.py
  likely has the opening list), ~max 300 pairs, elo1=+10.
- Log to results/sprt_phase2_vs_1b_<ts>.log. REPORT the verdict (accept/
  reject + LLR bounds + score). This is the make-or-break result for shipping
  the new eval.

### 3. Texel tuning (tools/texel_tune.py — does NOT exist, write it)
- numpy-only, offline dev tool. Generate ~50-200k quiet positions from
  self-play (our engine, low depth, varied openings — reuse the harness/
  engine_side pattern; a handful of cores in parallel is fine, ~30-60 min) OR
  use downloaded human PGNs (cite source in BUILD.md; training data
  unrestricted). Label with game result.
- Fit the eval's tunable weights (PSTs + term weights) by gradient descent /
  IRWLS on sigmoid(score) vs result. numpy only. Show loss decreasing. Keep
  the parameterization/loading convention compatible with engine/eval.py so
  tuned weights can be loaded via the existing config env (CHESSATHON_EVAL_CONFIG
  or similar — read eval.py).
- Commit tuned weights as a data file the agent can load (e.g. engine/weights/
  or a .npy/.json under engine/ — keep in zip, it's OUR data).

### 4. Final gates + ship
1. SPRT round 2: tuned eval vs hand eval (the f4e13e4 values) — show verdict.
2. Endgame conversion spot-check: KQvK, KRvK, KPK, KRPvK from a few FENs —
   engine must WIN (not shuffle to adjudication). Show games. (King safety +
   endgame terms should have fixed the 1a "king walks to h4" / shuffle issue.)
3. Harness vs 1b (the flat-eval engine): 20+ games, >= 60% expected, 0
   illegal/crash/flag.
4. Zip: rebuild agent.zip (agent.py + engine/ incl. any weights data at zip
   root layout per make_zip.sh), import+JIT < 60s, get_move legal fast.
- Commit granularly: sprt log, texel tuner, tuned weights, gate logs, BUILD.md
  Phase 2 completion entry (terms added with SPRT deltas, tuning loss curve
  summary, final nps, final gates, seeded-value attributions).

## Time budget discipline (IMPORTANT — last agent died from overreach)
This is a LOT. PRIORITIZE: (1) SPRT new-eval-vs-1b is the #1 deliverable —
if the new eval doesn't clearly beat 1b, STOP and report that (do not
Texel-tune a losing eval). (2) Only if SPRT accepts: write texel_tune.py,
run a SHORT tuning pass (~50k positions), SPRT the tuned vs hand. (3) Gates +
zip. If you run low on time/tokens, ship the best verified state + honest
"what's done / what's not" in your summary — do NOT claim gates you didn't run.

## Done when
Everything above that the time budget allows is committed + BUILD.md updated.
Final summary: what passed/failed with numbers (SPRT verdicts + LLR, nps,
endgame results, harness score, zip size/init), what's left undone, honest
risks. Acknowledge ORIGINALITY.md read.

<!-- source session: 2026-09-07T10-49-39-656Z_01a07b7c-ec48-7000-af41-71582db2e1d6.jsonl -->
