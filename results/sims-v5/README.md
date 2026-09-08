# V5 simulation / quirk investigation — r70 + r71 (2026-09-08)

Method: exact-clock replay of both V5 ladder games through the shipped V5
engine (replay_pgn.py + clkfiles from PGN %clk) + fixed-budget probes at
every divergence/decision point (1s/5s/25s) + fixed-depth eval probes.

## Core hygiene — CLEAN
- No illegal moves, no flags, no threefold/repetition events in either
  full-game replay. Core V5 behavior (stateful anti-threefold, P7/P8 keys,
  legality) defect-free under exact-clock conditions.
- Time management by design: R/45 geometric decay, never-flag. r70 ended
  with 66.8s unused (deliberate).

## Quirk 1 — EVAL SKEW on material compensation (fix candidate, most important)
At B (after the Na2/Qxb2 skirmish resolved, black a clean knight down) V5's
eval says only **-92..-104 cp** (depth 6-10). A knight deficit should read
≈-250..-350. Before the skirmish (A) it played Na2 at every budget with
eval -21..-81 — i.e. V5 *believed* the line was near-equal and the
post-line position only ~-1 pawn. The eval is over-crediting compensation
(doubled rooks on c-file / c5-c4 pawn / Bf6 pressure / bishop pair?) by
~200cp in this structure. This is why r70's loss looked "deliberate":
V5 did not know it was losing. CONCRETE next-build target: audit the
mobility/activity/pawn-structure terms vs material in semi-closed
piece-down positions (hand-eval legacy; the tuned-eval dud candidate was
burnt earlier — this skew may be in the SAME family of terms).

## Quirk 2 — SHARP-POSITION DEPTH INSTABILITY (move flips with budget)
- r70 ply 28: Rb8 @1s, c4(=real) @5s, Bf6g7 @25s — non-monotonic.
- r71 ply 16: Be2 @1-5s, Nce2 @25s — the real game's Rg1 appears at NO
  budget (real ~2.7s budget shouldn't have played Rg1 either → the real
  box's nps/depth environment picked it; environment-dependent persona).
- Consequence: V5's middlegame move choice varies with CPU speed of the
  host — replays diverge from real games at sharp points. Fix direction:
  search-stability measures (PV-preserving root move selection across
  iterations, aspiration/窗口 discipline), NOT eval.

## Quirk 3 — plays-on in lost positions (NOT a bug)
- Kxh5 (ply 44) depth-stable at all budgets; eval probe C shows V5's own
  eval = -394..-416 at depth 8-10 → it KNOWS it's lost; Kxh5 is best-of-
  bad defense, same for the instant Rf5 (ply 58, TT-cached forced line).
  Classified as correct desperation, not defect.

## Artifacts
- tmp/replay_r70.log, tmp/replay_r71.log (replays; r70 14/25, r71 7/11)
- tmp/probe_v5_divergences.log (budget probes)
- tmp/probe_v5_evals.log (depth eval probes)
- scripts: tmp/probe_v5_divergences.py, tmp/probe_v5_evals.py
