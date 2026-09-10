# chess-q5 — READ-ONLY AUDITOR (audit round 2): the ship-gate instrument + its first verdicts

Independent audit for the AI Chessathon engine repo (/home/pino/projects/
chessathon). LIVE-COMPETITION framing: uploads freeze Sep 11 11:00 UTC.
tools/quality_ab.py is now the STANDING SHIP GATE (PROCESS.md §10) and it
has already produced two candidate verdicts (SEEPRUNE NULL, NULL_DEEP
NEGATIVE) that keep toggles OFF. Your job: find every way the gate and
those verdicts can lie, before a real engine change is judged by them.
Different model family from the builders — your read is the independent
check. ~2h budget; partial reports fine.

## HARD RULES
- READ-ONLY: never write the repo. Work in a snapshot:
  `cd /home/pino/projects/chessathon && git archive HEAD | tar -x -C /tmp/chess-q5-audit2/` (rm -rf + re-archive before each check batch).
- Read ORIGINALITY.md first (the law). Then PROCESS.md §10, tools/quality_ab.py,
  tools/QUALITY_AB.md, and the git log (b95e052, 84815a4, 5472968, 051a2cf).
- PY=/tmp/chessbench/bin/python. Fresh NUMBA_CACHE_DIR per engine run.
- One CPU-heavy job at a time; SF reviews Threads=6. A review battery may be
  running on the box — if your empirical run is slow, that's why; retry once.
- API errors (freeinference): wait 20-60s, retry ≤10 backoff. NEVER OpenRouter.

## Audit questions — numbered findings with severity + repro

A. TOOL STATE: confirm the final committed quality_ab.py matches what
   produced the A/B evidence (git log — any tool changes after 051a2cf
   besides docs? Compare tool code at HEAD vs 051a2cf). Re-spot-check the
   two claimed fixes (--game path bug; Headers object) are correct and
   complete.

B. VERDICT 1 — SEEPRUNE "NULL": evidence at results/quality_ab/ab-seeprune/
   (commit 84815a4). Claim: retained 1 / avoided 0 / replaced-worse 0,
   mean cp_loss 55.7, "matches the 0.458 gate null". Scrutinize: which
   game(s) had replay coverage long enough to matter? n per game? Is a
   "NULL" conclusion supported or is the evidence just thin (short replay
   prefixes + the machine-parity limitation from selftest-corpus)? Would a
   real regression have been caught by this evidence?

C. VERDICT 2 — NULL_DEEP "NEGATIVE": claim mean 845.0 (candidate) vs 768.1
   (V5) → mean_not_worse FAIL; r70 replay walked into a mating attack at
   the thinning clock: f6?? (27870cp), fxg5 (28113/28213cp), Bf5 (28878cp).
   Verify in the JSONs: (1) those plies exist, are OUR moves, and carry
   those cp_loss values; (2) the means are computed over comparable move
   sets (same games, similar n both sides — watch for short-prefix bias);
   (3) the causal story ("R=3 at deep nodes skips the refutation horizon")
   is consistent with the engine code (engine/search.py NULL_DEEP toggle —
   read the actual reduction logic, not the narrative); (4) is 845-vs-768
   over the available n statistically distinguishable, or is the verdict
   carried by the qualitative mating-attack replay? State what the gate
   conclusion actually rests on.

D. GATE SOUNDNESS: the standing PASS bar (leaks avoided ≥1 ∧ replaced-worse
   0 ∧ b+m not up ∧ mean within +10cp). Given replay prefixes are short on
   this box (fidelity 0-25 our-moves/game), can the bar's FIRST condition
   (leaks avoided ≥1) ever fire meaningfully? Is there a regime where the
   gate would PASS a harmful change or FAIL a helpful one — and is that
   documented as a limit? Recommend the honest minimum evidence standard
   for a ship decision given these constraints (e.g., combine with the
   24g @500ms gate + leak-suite FEN probes + SF19 bout).

E. EMPIRICAL (allowed, in your snapshot): run ONE candidate A/B through the
   tool at HEAD (e.g. --candidate HEAD --game round-70-vs-kingsguard.pgn:black
   --env CHESSATHON_NULL_DEEP=1 --out /tmp/chess-q5-audit2/rerun-nulldeep)
   and check the rerun reproduces the committed ab-nulldeep numbers
   (means within ~±10%, same retained/avoided counts). If it does not
   reproduce, that is a MAJOR finding (evidence non-reproducible).

## Deliverable
Write /tmp/chess-q5-audit2-report.md AS YOU GO (numbered findings:
severity, mechanism, repro, fix direction). End with a verdict line:
"ship gate TRUSTWORTHY for candidate A/B" or "gate needs X before it
judges a real change" — and, separately, whether the NULL_DEEP/SEEPRUNE
conclusions themselves stand. Final summary: finding count by severity +
both verdict lines + anything upload-blocking.

<!-- source session: 2026-09-09T10-08-34-313Z_01a085a4 (killed by operator) -->
