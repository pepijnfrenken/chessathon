# CHESSATHON BUILD — Phase 2 FINISH (SPRT tuned eval, gates, ship)

Context: Phase 2 tooling + data are DONE and committed. What remains is the
final validation and ship. A prior agent (p2cont) built everything but died
before: (a) running SPRT on the TUNED eval, (b) running the gate checks,
(c) rebuilding agent.zip, (d) committing. Your job is ONLY the finish —
do NOT rebuild what exists.

## MANDATORY FIRST
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW.
2. `/home/pino/projects/chessathon/BUILD.md` — read the Phase 2 entry fully
   (it documents the eval parameterization, gating envs, tuner verification,
   SPRT #1 pending).
3. Inspect current state: git log, engine/eval.py (EVAL_PARAMS, gating envs
   CHESSATHON_EVAL_CONFIG / CHESSATHON_EVAL_GATE, TUNED_PARAMS patch block),
   tools/* (sprt.py, gate_match.py, eg_check.py, common.py, engine_side.py),
   data/ (positions_selfplay.npz 17MB, tuned_params_*.npy).
Acknowledge ORIGINALITY.md in your final summary.

## What to do (in order)

### 1. Load the tuned params into the eval
- The tuner produced `data/tuned_params_20260907_111011.npy`. The eval has a
  TUNED_PARAMS block that the shipped agent defaults to (`tuned` config).
  Verify the tuned params are actually wired in / loadable — check how
  engine/eval.py expects them (patch block? file path? env override?). If
  there's a mechanism to point the eval at the tuned .npy, use it. If the
  tuned params need to be embedded/copied into engine/eval.py as the default,
  do that (keep the .npy as provenance). The shipped agent must run with the
  tuned eval by default (CHESSATHON_EVAL_CONFIG=tuned or embedded default).

### 2. SPRT: tuned eval vs hand eval (the FINAL gate)
- Run tools/sprt.py: side-a = tuned eval, side-b = hand eval (f4e13e4
  hand-tuned values, config hand:1111). Same protocol as SPRT #1: 300ms/move,
  elo0=0 elo1=10, alpha=beta=0.05, our openings, max ~300 pairs.
- Log to results/sprt_phase2_tuned_vs_hand_<ts>.log. REPORT the verdict:
  accept/reject + final LLR + score (wins/losses/draws) + pairs played.
- IMPORTANT: if tuned does NOT beat hand (reject or inconclusive), ship the
  HAND eval (it's already the f4e13e4 default) and say so honestly — do not
  force a losing eval. The hand eval already passed SPRT #1 conceptually
  (rich eval > flat), so hand is a safe fallback.

### 3. Run the gates (quick)
- perft parity: 2 positions d1-4 (tools/perft_check.py) — confirm still exact.
- nps bench (tools/bench_nps.py) — report (expect ~500-650 knps with richer
  eval; must be >= ~400).
- Endgame conversion spot-check (tools/eg_check.py exists): KQvK, KRvK, KPK,
  KRPvK-ish — engine must WIN (report the games/verdicts).
- gate_match vs 1b flat eval (tools/gate_match.py): 20+ games, 0 flags, report
  score. Expect >= ~60% with the tuned eval.

### 4. Rebuild + verify agent.zip
- Run make_zip.sh. Verify zip = agent.py + engine/ only (data/ and tools/ are
  DEV-only — do NOT ship them; tuned params must be embedded in engine/eval.py
  or a small engine/weights file, NOT data/ at repo root).
- Unzip in clean dir with python-chess, get_move legal + fast, import+JIT
  < 60s. Confirm the shipped agent uses the tuned (or hand) eval — print which.

### 5. Commit + BUILD.md
- Commit granularly: SPRT log + verdict, gate results, eval wiring change,
  rebuilt zip (if you commit the zip — optional), BUILD.md Phase 2 COMPLETION
  entry: SPRT verdicts (#1 rich-vs-flat if you have it, #2 tuned-vs-hand),
  final nps, endgame results, gate score, zip size/init, which eval shipped
  (tuned or hand + why), data provenance (17MB selfplay, ~N positions).

## Time budget
This is a SHORT mission (SPRT may take ~20-40 min to converge; that's fine).
If you truly can't finish SPRT, ship the hand eval + document, but try to let
SPRT run to a verdict — it's the whole point.

## Done when
Eval shipped (tuned or hand), SPRT verdict recorded, gates pass, zip rebuilt +
verified, everything committed, BUILD.md updated. Final summary: verdicts +
numbers + which eval shipped + risks/notes for next phase (pondering/aspiration
polish or the gated net sprint — INDEX.md B3).

<!-- source session: 2026-09-07T12-01-00-437Z_01a07bbe-3e15-7000-b625-ef00fd2dde55.jsonl -->
