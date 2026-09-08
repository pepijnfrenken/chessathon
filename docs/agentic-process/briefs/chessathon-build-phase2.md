# CHESSATHON BUILD — Phase 2: Evaluation & Tuning (eval terms + Texel tuning)

Context: 1a (minimal, pure-Python) and 1b (numba engine, own board+movegen,
search core: ID/PVS/TT/qsearch/null/LMR/check-ext) are shipped. 1b: ~865 knps,
depth 13 startpos, 22-0-0 vs 1a, perft-exact. NOW ON THE LADDER. This phase
makes the engine STRONGER by upgrading the evaluation and tuning it. Search
core is done — do NOT rewrite it. Focus: eval + tuning + SPRT discipline.

## MANDATORY FIRST (read before ANY code)
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW. Fresh code only.
   NO copying/adapting existing engine source or fetching code. Published
   eval concepts + VALUES (PST tables etc.) may be used with attribution in
   BUILD.md — but implement fresh, and prefer our own tuned values.
2. `/home/pino/projects/chessathon/CLAUDE.md`
3. `/home/pino/projects/chessathon/BUILD.md` (has 1a/1b entries + risks to
   address: flat eval makes endgames shuffle; no pawns/mobility/king safety)
4. `/home/pino/projects/chessathon/docs/research/02-eval-and-tuning.md` —
   THE blueprint for this phase (read fully).
5. `/home/pino/projects/chessathon/docs/research/05-chess-models-and-methodology.md`
   §B2/B3 — ROI ranking + why SPRT discipline matters.
6. Existing `engine/eval.py`, `engine/search.py`, `agent.py`, `tools/local_game.py`
   — read them first; build on them.
Acknowledge reading ORIGINALITY.md in your final summary.

## Environment reminder
1 core, 2GB, no GPU/network at runtime. numba 0.67.0, python-chess 1.11.2,
numpy preinstalled. NO torch import at runtime. 60s init (JIT warmup inside).
numba cache=False (segfaults with cache on recursive structs — 1b found this).
120s+0.5s clock. State persists between moves. Filesystem read-only at
runtime; NUMBA_CACHE_DIR=/tmp.

## What to build

### 1. Upgrade `engine/eval.py` — real eval terms (numba, keep <~4us/node)
From research doc 02 (ROI-ranked). Implement, in order of value:
1. **Pawn structure**: doubled, isolated, (backward optional), and PASSED
   pawns (with rank bonus + blocker bonuses). Most important after material/PST.
2. **Mobility**: count legal/attacked squares per piece (or pseudo-legal
   attacks from precomputed tables), small per-piece-class bonus. Keep cheap.
3. **King safety**: shield/shelter tables near the king + (simple) open-file
   penalties; pawn-storm awareness only if cheap. In endgames (<~2 queens
   off etc.), king centralization bonus instead (helps convert).
4. **Bishop pair + tempo** (1b may have these already — keep).
5. **Drawish/endgame awareness**: avoid shuffling — add a small bonus for
   pushing passed pawns / centralizing king in endgames so won games convert
   (the 300-ply material adjudication rewards holding material).
Keep the interface identical to what search.py calls (same function sig).
Tapered eval stays (mg/eg phases). Everything numba-jitted, no python objects
in hot path. Each term gated so it can be toggled for SPRT A/B.

### 2. Texel tuning (numpy, offline, NOT in the shipped agent)
- Write `tools/texel_tune.py` (dev tool, not shipped): 
  - Data: extract QUIET positions from self-play games (our engine, low depth,
    varied openings — write a small game generator or reuse harness with a
    book of ~10 varied openings you write yourself) + optionally human PGNs
    you download and cite (training data is unrestricted). Skip positions
    near mate / first 8 plies. ~50-200k positions target (fewer OK to start).
  - Label each position with game result (or our engine's search score at
    fixed depth as target).
  - Fit eval weights (PST + term weights) by gradient descent / IRWLS on the
    sigmoid-transformed score vs result. numpy only. Show loss decreasing.
- IMPORTANT: Texel-tuned weights are OUR values from OUR data — fully legal
  and original. If you seed from a published PST table, say so in BUILD.md.

### 3. SPRT / A-B test harness (dev tool)
- Extend `tools/local_game.py` (it already plays engine-vs-engine) into a
  simple SPRT loop `tools/sprt.py`: play pairs (our new eval vs current best,
  alternating colors, varied openings, fixed short TC e.g. 10s+0.1s or fixed
  nodes), stop at a bound (e.g. 95% confidence the new version is >= +10 Elo
  or <= 0), accept/reject.
- Discipline: ONLY accept eval changes that pass SPRT. No vibes. Show the
  running score + bounds in output.

### 4. Re-run gates (must pass before ship)
1. Perft still exact (quick: 2 positions d1-4) — eval changes must not break
   the board.
2. nps not collapsed: still >= ~400 knps (eval got richer but must stay cheap;
   measure and report).
3. SPRT: tuned eval vs 1b eval — show accept/reject with bounds. Expect a
   real win rate gain (target > 55% in the SPRT pairings).
4. Endgame conversion spot-check: from 3-4 won endgame FENs (KQvK, KRvK, KPK,
   KRPvKR-ish at low material), engine must win (not shuffle to adjudication)
   within reasonable moves. Show the games.
5. Harness vs 1b: 20+ games, >= 60% expected (tuned eval should clearly beat
   1b's flat eval). 0 illegal/crash/flag.
6. Zip: rebuild, import+JIT < 60s, get_move legal fast. Update make_zip.sh if
   needed (no new shipped files beyond agent.py + engine/).

### 5. Ship it
- Commit granularly (eval terms one-by-one with SPRT results where feasible,
  tuner, sprt tool, gate logs, BUILD.md entry).
- Rebuild `agent.zip`. Update BUILD.md with: what each term added (SPRT
  deltas if measured), tuning loss curve summary, final nps, final gate
  results, attribution of any seeded values.

## Done when
All gates pass, everything committed, agent.zip rebuilt. Final summary:
files, per-eval-term SPRT result (or at least the combined tuned-eval SPRT
result with bounds), nps, endgame spot-check results, zip size/init time,
notes for the next phase (time mgmt/ponder polish or the gated net sprint —
INDEX.md B3 table ranks what's next).

<!-- source session: 2026-09-07T10-28-15-844Z_01a07b69-5564-7000-95a8-f06b4e68da27.jsonl -->
