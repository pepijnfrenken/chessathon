# Chess brainstorm — AGENT A: radical search/eval engineering probes

## Mission (research/brainstorm, READ-ONLY — you NEVER write the repo)
Pino wants radical, different-approach ideas for the chess engine BEFORE the
upload freeze (Sep 11 11:00 UTC). Produce a ranked probe menu: ideas that
could actually be implemented, single-feature, and tested against the
shipped V5 engine. Ground EVERY idea in the actual code — read it first.

## Repo + rules
- Repo: ~/projects/chessathon. ORIGINALITY.md is LAW (everything shipped
  = code we wrote in-repo this event; no third-party code, no pretrained
  models; training/data may be self-generated). Classical search only.
- READ-ONLY: work in a snapshot if you must (git archive HEAD to /tmp),
  never modify the repo. Write your report to /tmp/chess-brainA-report.md
  as you go (append, so partial work survives). Report path final:
  /tmp/chess-brainA-report.md
- Model: you are freeinference deepseek. If the API hiccups (empty
  content / "model starting" placeholder), wait 20-60s and retry; never
  guess. PY for running anything = /tmp/chessbench/bin/python (python-chess
  installed).

## Read first (in this order)
1. ORIGINALITY.md (rules — before anything)
2. PROCESS.md §3 decision log, §5 ideas backlog, §6 open problems
3. results/sims-v5/README.md (V5 quirk forensics — CRITICAL context)
4. engine/search.py FULL (search core: PVS, TT, null-move R=2, LMR, qsearch
   QCAP cap, check ext, full-window root after aspiration revert)
5. engine/eval.py term groups + material tables; engine/time.py budget
   policy (R/45+500ms); engine/tt.py (64MB, 16B entries, 2-slot
   depth-preferred); engine/board.py skim (move encoding, legality)
6. tools/gate_match_tree.py usage (tree A/B vs a git snapshot),
   tools/local_game.py (real-clock sims), tools/bench_fixed_depth.py
7. results/matches/*.pgn — the ladder corpus (r48-r71); look at the LOSS
   patterns (r64, r68, r70) with a quick eye: what KIND of position keeps
   leaking material?

## What to produce — 5-8 ranked probes, at least 3 GENUINELY RADICAL
For each: (a) one-paragraph idea in engine terms; (b) WHY it attacks a
documented weakness (cite the sims quirks / backlog / your own PGN scan —
e.g. the ~-100cp knight-down eval skew, the sharp-position depth
instability, the r64/r68/r70 material-leak family, TT thrash at ~2M
nodes/move on 64MB); (c) implementation sketch (which file/function, how
the change is gated by an env toggle like existing CHESSATHON_LMR — numba
needs compile-time globals, so the A/B harness runs two processes);
(d) effort (hours), risk (regression likelihood + which gates), and the
RIGHT test regime for the feature (500ms gate vs real-clock sim — the
project learned endgame/repetition-class features pass eg-suites and fail
500ms gates while being correct at real TC; state which regime fits your
idea and why); (e) verdict estimate (worth trying before Sep 11?).

Ideas may include, but are NOT limited to: root-move stability/hysteresis
(PV commitment across iterations — attacks Quirk 2 directly); SEE-based
capture pruning/ordering in qsearch (material-leak class); TT enlargement
to 256-512MB (real-clock regime); eval compensation-term audit protocol
(Quirk 1 — but note the tuned-eval dud history, Phase 2: hand eval ships;
frame it as a MATERIAL-vs-activity audit with fixed-point checks, not
retuning); contempt/draw-shaping at real TC; time-management volatility
signals (spend where eval is unstable); alternative extension policies;
progressive deepening tweaks; anything from modern engine literature you
can argue from FIRST PRINCIPLES for a 1-core/2GB/no-GPU/2.8s-per-move
numba engine. Do NOT propose: texel re-tuning (settled negative), trained
nets (no), aspiration re-test @500ms (settled negative regime), anything
needing >1 day of implementation.

## Verdict discipline
End with: TOP-3 probes for a builder to run this week, each ≤6h
implementation+gate, ranked by (expected Elo gain at real TC) × (1/risk) ×
(fits-before-freeze). Also list 1-2 probes you'd run ONLY after V5's
evaluated weaknesses are proven fixed (deferral logic).
Write the final summary as the LAST section of /tmp/chess-brainA-report.md.
