# chess-q5 — codex re-AUDIT of the night build (round 2 final, cheap: thinking low)

Read-only fresh-eyes audit of the NIGHT'S accumulated changes in
/home/pino/projects/chessathon. Your q5-codex2 dispatch failed on a pane
conflict; you are the replacement (q5-codex4). Same mission, updated state.

## Build chain to audit (each link gated; verify records + sources)
Chain: V5 (shipped baseline) → v6 = V5 + null-child-negation fix (aebee58)
→ night1 = v6 + insufficient-material zeroing fix KBN-v-K (3c06692, gates
5458b48: L1 24@500ms 12W-6L-6D=0.625 vs v6-HEAD, eg_check 8/8 incl KPK-b,
KBN static +875 was 0) → night2 = night1 + PST pawn-row flip at
hand-assembly (f5ce5de; gates a1feaf5: **L1 24@500ms vs night1 24W-0L-0D
= 1.000**, L2 corrected 78-FEN corpus: leak scores drop mean -95.9cp
toward referee truth, 1 nominal >=300 row is a lost position where the
candidate is CLOSER to truth, eg_check 8/8 @300ms incl KPK-b, shuffle
10/12 = V5 control parity, det identical 493,820 nodes r83-p21 d8).

## ALSO READ (context you must reconcile)
- /tmp/chess-q5-codex3-r90-report.md — the r90 loss verdict (keep V6, do
  not roll back; PST flip conditional on completed gate evidence — which
  now EXISTS: the a1feaf5 record above).
- /tmp/chess-q5-codex1-report.md + /tmp/chess-q5-codex1-experiment/REPORT.md
  (your round-1 findings: H1 null sign, H2 PST orientation, §7 endgame bugs)
- docs/research/07-pst-phantom-decomposition.md (PST spec, item 1 = the flip)
- PROCESS.md latest sections + results/gate_night*.log if present.

## Questions
1. Chain integrity: does each commit implement exactly its record's claim
   (KBN zeroing fix; pawn rows flipped at hand-assembly ONLY — not king/
   rook tables, no color asymmetry, both MG+EG, eval_decompose parity)?
2. Are the gate records sound? (L1 0.625 then 1.000 — zero flags; L2 on
   the CORRECTED 78-FEN corpus; eg_check/shuffle/det; box quiet? verify
   logs exist under results/ and match the claims.)
3. Shipping decision for the night2 build (null-fix + KBN + PST flip) as
   the next upload: ship-as-is / ship-after-fix-X / don't-ship. Consider:
   the L1 gate was vs night1 (a weaker sibling), NOT vs the ladder-active
   v6-HEAD — flag any risk that 1.000 overstates the gain vs what the
   ladder currently plays. Also flag: 24-game gates are small samples.
4. Anything new you see that would block shipping night2 before uploads
   close Sep 11 10:00 UTC. We plan to upload night2 before 07:00 UTC so
   Sep 10's first round plays it.

## HARD RULES
- READ-ONLY: no repo writes, no git ops, no engine-vs-engine games, no
  uploads. Scratch in /tmp only. Light CPU checks fine (eval_decompose
  parity probes are short); no gates/replays — the box may be running
  fix1's staging work; if a gate is active, do not touch the CPU.
- Provider: codex quota dies fast with two audits — if provider errors
  persist ~10 min, write partial findings to /tmp/chess-q5-codex4-report.md
  and exit clean. Never OpenRouter.
- Output: /tmp/chess-q5-codex4-report.md + chat summary with verdict.

<!-- source session: 2026-09-09T22-57-35-118Z_01a08864 -->
