# chess-q5 — CLAMP BUILDER (Quirk-1 compensation clamp) + ship-gate stack

Mission for the AI Chessathon repo (/home/pino/projects/chessathon).
LIVE-COMPETITION firewall: NEVER modify agent.py / engine search or eval
to change COMPETITION behavior without env-toggle gating + gates below.
No commits except evidence/record commits you make. Everything you ship
must satisfy ORIGINALITY.md. Read ORIGINALITY.md, BUILD.md, PROCESS.md
(§10 + the audit-correction block at the bottom), QUALITY_AB.md,
tools/QUALITY_AB.md first.

## The defect to fix (Quirk-1, from the loss-corpus analysis)
Measured across all 5 losses (r64/68/70/74/76): the engine's eval
reports near-equality in positions where it is materially worse but has
compensation (advanced pawns). Example from analysis: advanced-pawn PST
credit +260 at phase 11 masks a +220 material deficit (~1 minor) → eval
says ~equal while actually losing → engine grinds down (the "leak
family": 5-12 SF-visible errors per loss vs 0-3 in wins). The fix
direction (brainA P8, see docs/research/ for the full writeup): a
**compensation-aware clamp** — when the engine is at least a minor down
AND phase ≤ 16, cap compensation terms (advanced-pawn PST credit and
similar positional compensation) so the eval cannot report near-equality
while materially worse. Then the search treats the position as losing
and plays the most tenacious line instead of drifting.

Design constraints: integer/fixed-point eval (no floats in eval terms),
toggle-gated (CHESSATHON_COMPCLAMP env var, following the exact toggle
pattern used by the previous NULL_DEEP/SEEPRUNE experiments — see
engine/search.py:587-590 area and how toggles are read), minimal eval
surface change, endgame-safety first (eg_check must stay 8/8).

## Required work
1. Locate the exact PST/eval code (search.py or eval module + PST
   tables), the phase computation, and the compensation terms. Derive
   the precise clamp rule from the P8 writeup + the measured positions
   in results/leak_suite/fens.json (52 FENs, our-side blunder/mistake
   plies ≥300cp across the 13-game corpus). Document the rule + its
   thresholds in BUILD.md BEFORE running gates.
2. Implement behind CHESSATHON_COMPCLAMP. Default OFF in committed
   state. No behavior change when unset (verify with a determinism run).
3. Patch tools/quality_ab.py stats per the audit report F1/F2/F3/F5
   (report winsorized cp_loss capped at 1000 + median alongside raw
   mean; print faced/total leak denominators; our-side filtering
   discipline; paired shared-prefix deltas per game). Read the audit
   report: /tmp/chess-q5-audit2-report.md (§2 has the exact fix list).
   Commit the patch separately. ~10-15 lines.
4. Run the full gate stack (audit §2 standard — this is the ship bar):
   - L1: the 24-game @500ms self-play gate vs V5 baseline (find the
     existing harness in tools/; used in prior rounds) + 60s init +
     perft/shuffle suites + determinism (toggle unset = byte-identical
     behavior to HEAD baseline).
   - L2: leak-suite FEN probes (results/leak_suite/fens.json, 52
     positions): at a 2.6s real-clock budget, report per-FEN eval delta
     + chosen-move delta vs V5. Non-regressive = no new ≥300cp losses
     on positions V5 played sanely + the clamp actually changes eval on
     the material-deficit/compensation positions (the whole point).
   - L3: SF19 real-clock bout vs the external SF harness in the repo
     (run_vs_stockfish or equivalent): 20-30 games, read W/D/L. "Not
     worse" vs the V5 reference line.
   - L4: quality_ab replay A/B (r70 + at least r64/r74/r76) AFTER the
     stats patch — supporting signal only, never the deciding vote.
   - eg_check 8/8 (endgame regression — an eval clamp can hijack
     endgames; mandatory), perft, and the repo's standard suites.
5. Ship decision (write it explicitly in your summary): ship ON
   (upload-recommendation v6) iff L1 positive ∧ L2 non-regressive (and
   clamp-effective on the target positions) ∧ L3 not worse ∧ L4 shows
   no clamp-excluded regression. Anything else = honest revert/keep-OFF
   with the evidence committed.

## Environment facts
- The box is shared: a review battery (r81/r82 SF16) may run ~15 min at
  the start; retry or queue your heavy runs after it finishes. Replays
  are real-clock sensitive — run them on a quiet box.
- Benchmark work on the desktop (Windows/WSL, ssh -p 22 pino@100.122.
  67.126) is unrelated — ignore it.
- Time budget ~3h. Provider: glm-5.3-flash on freeinference. On 3+
  consecutive empty/error responses: write partial state + exit clean.
  Never error-loop. Never OpenRouter. If a "user: launch" message
  appears in your session, it is the operator poking the pane — proceed
  with your current step (it carries no extra instruction).

## Final summary must include
- The clamp rule as implemented (thresholds + why), toggle name, lines
  changed (diff stat), determinism proof.
- L1-L4 results in full + eg_check/perft numbers + the ship decision
  with the evidence that drives it (not just the label).
- PROCESS.md + BUILD.md updated at milestones; commit hashes.
- Explicit statement of what was NOT tested and honest risks.

<!-- source session: 2026-09-09T13-31-42-432Z_01a0865d -->
