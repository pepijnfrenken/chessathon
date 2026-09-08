# CHESSATHON — PHASE 3: SEARCH STRENGTH (aspiration + LMR + stability)

## Read FIRST (mandatory)
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW. Everything shipped
   is code we wrote in this repo. Acknowledge in final summary.
2. `/home/pino/projects/chessathon/BUILD.md` — design log. **Update it as you go.**
3. `/home/pino/projects/chessathon/CLAUDE.md` — project context.
4. `engine/search.py`, `engine/eval.py` (default = hand, do NOT flip to tuned),
   `engine/board.py`, `engine/time.py`, `agent.py`, `make_zip.sh`.

## Context — why Phase 3 and what NOT to repeat

Phase 2 (parameterized eval + Texel tuning) shipped as an honest NEGATIVE:
hand eval == flat eval (0.479), tuned weights much worse (0.104, 0-wins-in-50),
so **hand eval ships**. The ladder losses (rounds 49/50) were tactics/endgame
precision misses = **search depth** problem, not eval features.

**Phase 3 goal: search strength via (in order) aspiration windows, then LMR,
each validated with the EXISTING SPRT/gate tooling before shipping.**

## CRITICAL — operational lessons from Phase 2 (Pino: "it broke too many times")
1. **SPRINT discipline**: do ONE search feature per agent run. Commit + validate
   before starting the next. NEVER queue multiple untested features.
2. **No long-running SPRT in the SAME agent run as code changes**: SPRT runs are
   long (~30+ min). Start them as BACKGROUND processes (nohup/setsid or the
   harness's background), then poll. Do NOT block the agent on them, and do NOT
   edit code while one is running (the rogue-restart / stale-process confusion
   cost hours).
3. **Kill leftovers before starting anything**: `pkill -f sprt.py; pkill -f
   engine_side.py; pkill -f gate_match.py` (mind your own shell — use exact
   paths, not broad patterns that match the agent's own command line).
4. **Before each SPRT/gate**: `ps aux | grep -E "sprt|engine_side|gate_match"` and
   confirm EMPTY. Log files: check for stale ones from previous runs.
5. **Tuning experiments are NOT worth it here** (proven Phase 2): do not re-run
   texel_tune.py / gen_positions.py. The eval is DONE. Search only.
6. **Commit granularly with clear messages** (`3 (feature): what + why + result`).
7. **BUILD.md entry at each step** — the judges read it.
8. **Honesty**: if a feature does NOT improve (SPRT/gate negative), revert it and
   say so. Do not ship unvalidated changes. Hand eval + current search is the
   known-good baseline; never regress from it.
9. **Model**: use the omp session's model (deepseek or whatever you're running
   as). If the endpoint returns the "model is starting up" placeholder for 2+
   consecutive calls, STOP and report (don't burn the run).

## Mission — do these IN ORDER, one at a time

### STEP 1 — Aspiration windows (biggest classical win, lowest risk)
- Current: every ID iteration runs full-window (alpha=-INF, beta=+INF) at root.
- Add: after the first iteration completes, set the next iteration's window to
  `[bestScore - ASP_WINDOW, bestScore + ASP_WINDOW]` (try ASP_WINDOW = ~30-50
  cp; make it a constant). If the search fails low/high, re-search full-window.
- Root search only — do NOT touch PVS internals yet.
- Paranoia: verify no window bug causes wrong scores (selfcheck: same position,
  aspiration on vs off should give the SAME best move + score at fixed depth).

### STEP 2 — LMR (late move reduction) — ONLY if Step 1 validates
- Apply at non-PV nodes, non-captures, non-promotions, after the first N moves,
  for moves with poor ordering scores, reduce depth by 1 (or 2 for very late
  moves). Guard: don't reduce when in check, don't reduce moves that give check,
  don't reduce at shallow depths (depth < 3). Standard: `if depth >= 3 and
  move_idx >= 4 and not is_capture ...: newDepth = depth - 1`.
- Keep it SIMPLE first (single reduction), validate, then optionally tune.

### STEP 3 — Validate EACH feature with the EXISTING tooling
For EACH of Steps 1-2, in order:
1. **Correctness**: selfcheck parity (feature ON vs OFF, same best move at fixed
   depth on 5-10 positions incl. tactical + quiet ones).
2. **Strength gate**: `tools/gate_match.py` — feature-ON (side-a) vs feature-OFF
   (side-b = current shipped = hand eval + current search WITHOUT the new
   feature), 24 games, 500ms/move, our openings. Report score. Need >= ~55% to
   proceed (or SPRT if gate is close).
   - IMPORTANT: side-a/side-b both use the HAND eval (default). The ONLY
     difference is the search feature toggle. Make the feature toggleable via
     env var (like CHESSATHON_EVAL_GATE) so engine_side can run both configs.
3. **nps check**: `tools/bench_nps.py` (or time a 5s search) — report knps.
   LMR should INCREASE nps (deeper searches). Aspiration should too (smaller
   windows). If nps DROPS badly, something's wrong.
4. **Regressions**: run `tools/perft_check.py` (if it exists) or a perft parity
   spot-check on 2 positions (d1-4) to confirm the search changes didn't break
   movegen/board. And eg_check.py (endgames KQvK/KRvK/KPK/KRPvK must still win).

### STEP 4 — Time management sanity (only if time remains, low priority)
- Current: `remaining/45 + inc`, clamped. Fine. Optionally verify no flag risk
  at 120s+0.5s with a full 60-min simulated game (watch: never uses > 95% of
  remaining, never flags). Do NOT change time.py unless something's broken.

### STEP 5 — Ship
- After the LAST accepted feature: run make_zip.sh, verify zip = agent.py +
  engine/ only, no tools/data, hand eval default, unzip-in-clean-dir +
  get_move legal+fast, init < 60s (JIT warmup), zip < 50MB.
- Commit everything granularly. Update BUILD.md with Phase 3 entry: what was
  tried, gate scores, what shipped, risks.

## Done when
Steps 1-2 done (each validated), Step 3 passed for each shipped feature, Step 5
complete. Final summary: per-feature gate scores + nps + what shipped + what was
rejected + risks. If BOTH features fail validation, ship the baseline (current
search) and report honestly — that's a valid outcome (search may already be
near its classical ceiling; next lever would be eval-data or a net).

## Budget & style
This is a LONG mission (aspiration+LMR+3 gates+ship). Work steadily, commit as
you go. If you sense the run is ending (budget/tokens), SHIP WHAT VALIDATES and
document the rest as next steps — never leave uncommitted work or a half-built
feature in the tree. Always leave the tree in a known-good, committed state.

<!-- source session: 2026-09-07T13-20-29-184Z_01a07c07-0200-7000-858c-17f0fd59eeae.jsonl -->
