# chess-q5 — AUDIT round 2 RESUME (q5-audit2b)

Resuming the read-only audit of the quality_ab ship gate. The previous
auditor (q5-audit2) was killed by the operator at ~11:25 UTC during a
provider flake after ~1h of good work. Full mission context:
/tmp/brief-chess-q5-audit2.md (read first — HARD RULES + audit questions
A-E all still apply). Its partial report file never got created; its
findings live in its session log (carryover below). Snapshot dir for you:
/tmp/chess-q5-audit2/ (re-archive HEAD before each check batch:
rm -rf /tmp/chess-q5-audit2 && mkdir -p /tmp/chess-q5-audit2 && git
archive HEAD | tar -x -C /tmp/chess-q5-audit2/ — the mkdir -p is
REQUIRED; tar -C fails without it).

## Carryover findings from the killed run (verified by it — do not redo, but you may re-check)
1. Q-A CLEAN: tools/quality_ab.py at HEAD is byte-identical to 051a2cf
   (the fix commit); between evidence commit 84815a4 and HEAD only
   PROCESS.md changed — the engine bytes that produced the A/B evidence
   are the engine bytes at HEAD.
2. NULL_DEEP code confirmed: engine/search.py:587-590 — the toggle swaps
   null-move R=2→3 at depth ≥6 inside the same guard set.
3. Referee caveat: SF19 mate scores clamp to ±30000 → mating-attack moves
   produce enormous cp_loss values that dominate means.
4. NULL_DEEP's cand mean (845, n=70) is dominated by r70 (30/70 moves,
   mean 1924.8 — the only full-game replay); all other games stopped after
   n=2-11 opening moves (means 11-68).
5. SEEPRUNE's evidence base is thinner still: only ONE V5 leak was ever
   faced pre-divergence across the whole corpus.
6. It was mid-way through verifying the specific claimed r70 plies
   (f6??/fxg5/Bf5 cp_loss values in the ab-nulldeep JSONs) and the referee
   binary's identity when killed.

## Remaining work (do this)
A. Finish question B/C verification: the claimed r70 plies + cp_loss
   values in results/quality_ab/ab-nulldeep/*.json (repo, read-only ok);
   referee binary identity (stockfish path + version used for replay
   reviews vs the cached leak_reviews — same binary?).
B. Question D (gate soundness): the standing PASS bar (leaks avoided ≥1 ∧
   replaced-worse 0 ∧ b+m not up ∧ mean within +10cp) given replay
   prefixes are short (fidelity 0-25 our-moves/game) and candidate means
   ride on 1-2 full-game replays — can the bar's first condition ever fire
   meaningfully? Would the gate PASS a harmful change or FAIL a helpful
   one? Recommend the honest minimum evidence standard for a ship decision
   (24g @500ms gate + leak-suite FEN probes + SF19 real-clock bout +
   quality_ab as supporting signal?). This feeds the next builder round's
   brief — make it concrete and decision-ready.
C. Question E (empirical rerun): run the NULL_DEEP rerun if the killed
   run's rerun output is absent (check /tmp/chess-q5-audit2/rerun-nulldeep
   and the snapshot dir first): --candidate HEAD --game
   round-70-vs-kingsguard.pgn:black --env CHESSATHON_NULL_DEEP=1 --out
   /tmp/chess-q5-audit2/rerun-nulldeep (from the repo root, PY=/tmp/chess-
   bench/bin/python, fresh NUMBA_CACHE_DIR). Compare means vs the
   committed ab-nulldeep numbers (±10%). NOTE: a review battery (r78-80
   SF16) may be running on the box — replays are real-clock sensitive; if
   the run looks distorted, retry once when quiet. A full corpus rerun is
   NOT required — r70 alone answers reproducibility.
D. Write /tmp/chess-q5-audit2-report.md with numbered findings (severity,
   mechanism, repro, fix), verdict lines: "ship gate TRUSTWORTHY for
   candidate A/B" or "gate needs X before it judges a real change", and
   separately whether the NULL_DEEP/SEEPRUNE conclusions stand.

Provider discipline: on 3+ consecutive empty/error responses, write the
partial report with what you have and exit cleanly. Never error-loop.
Never OpenRouter. ~1.5-2h budget.

## Concurrency reality (learned the hard way — READ THIS)
The provider enforces an ORG-WIDE concurrency limit of ONE active request.
Another agent (minicpm-cap1c) shares the same provider and polls it
periodically. Symptom of collision: `concurrency_limit_exceeded` /
empty-content responses / stop:error — NOT a model flake. Mitigation:
after ANY failed/empty provider response, `sleep 20-45` and retry —
do NOT hammer; the other agent's calls come in short bursts, so pacing
fills its gaps. If 5 consecutive attempts fail, sleep 120s then continue
(someone is mid-burst). Only exit (per the 3-strike rule) after ~15 min
of continuous failures. A "user: launch" message may appear in your
session — it is the operator poking the pane; interpret it as: proceed
with question E (the empirical rerun) now.

<!-- source sessions: 2026-09-09T11-36-20-297Z_01a085f4 (died) + 2026-09-09T12-03-49-452Z_01a0860d (completed) -->
