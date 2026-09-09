# Chess builder: P1 — SEE in qsearch (ordering first, then pruning)

## Mission
Implement static exchange evaluation (SEE) in qsearch on the V5 engine,
ONE mechanism in TWO independently-gated toggles (never stacked before
measurement), validate, gate, commit + BUILD.md. Two features in this run
are allowed ONLY because each gets its own isolated gate (attribution
stays clean): (1) CHESSATHON_SEE=1 — capture ORDERING by SEE in qsearch;
(2) CHESSATHON_SEEPRUNE=1 (requires SEE ordering) — skip SEE<0 captures
when not in check. Baseline from brainA report (/tmp/chess-brainA-report.md
§P1 — read it; implementation contract below is authoritative).

## Rules (never bend — Pino: "make sure you're right")
1. ORIGINALITY.md is LAW — read it FIRST. Everything is our own code in
   this repo. No third-party engine code, ever.
2. Scope discipline: touch ONLY search.py qsearch + module globals + doc
   header. NOT eval.py, NOT time.py, NOT agent.py policy, NOT board.py.
   Anything else you notice → note in BUILD.md, don't fix.
3. Never edit code while a gate runs. Before ANY gate:
   `ps aux | grep -E "move_quality|review_sf|run_vs_stockfish|stockfish"` 
   must be EMPTY (background analysis chains from the orchestrator are
   still finishing — sleep-poll until clean; do NOT start gates while
   they run, the 500ms gate is load-sensitive).
4. PY = /tmp/chessbench/bin/python. Fresh NUMBA_CACHE_DIR per tree
   variant in A/B snapshots (stale numba caches validate the wrong code).
5. Commit checkpoints; leave the tree committed + known-good at the end.
6. Provider hiccups: retry 20-60s; never guess. Read errors, adapt.
7. Gate verdict rules (TRUST-NOTHING): read the FINAL `score:` line in
   the .stdout (side A perspective); mid-gate polls are NOT verdicts;
   ≥0.55 ship candidate / 0.45-0.55 null (report honestly, no spin) /
   <0.45 revert that toggle. Zero flags required in every gate.

## Implementation contract
- New jitted `see(st, from_sq, to_sq)` in search.py (~40-60 lines, OUR
  code): 0x88/attacker-walk least-valuable-attacker recursion over the
  capture chain; standard SEE semantics (>= 0 = winning/losing trade).
  Unit-test it on a small hand-made battery vs brute-force swap-value
  (write the test; assert exact values on ~10 positions incl. pinned
  pieces / x-ray / en-passant-free simple cases — EP legality in SEE:
  handle or explicitly ignore with a comment).
- qsearch, non-check nodes: when CHESSATHON_SEE: order captures by SEE
  desc (MVV-LVA as tiebreak); when CHESSATHON_SEEPRUNE: skip captures
  with SEE < 0 (never while in check). QCAP depth cap unchanged. All
  guards/phases untouched.
- Toggles read at import (numba bakes globals) — same pattern as
  CHESSATHON_LMR/NULL_DEEP; default OFF (ship default = V5 behavior).
- IMPORTANT: mate-drive endgames must stay 8/8 — SEE ordering must never
  reorder KILLING lines out of view (only demote clearly-losing captures,
  keep best-response ordering; if eg_check regresses, that's a bug in
  the see() sign/ordering logic — diagnose, don't ship).

## Validation + gates (IN ORDER, each before the next)
A. Perft d1-d4 vs python-chess on 3 FENs (incl. en-passant FEN): OFF and
   ON must both be perft-clean (movegen untouched).
B. Determinism: same position × 2 fresh processes, SEE on → identical
   move + score.
C. Fixed-depth node parity: feature OFF @d8 on the standard bench
   position == 1,030,699 nodes exactly (else stop: tree changed with
   toggles off).
D. see() unit battery passes.
E. eg_check 8/8 (SHIPPED config semantics: --strong hand:1111 --weak
   hand:0000 — check the tool usage first).
F. GATE 1 (ordering only): tree A/B 24g @500ms via gate_match_tree.py,
   hand:1111 both sides; side A = HEAD+CHESSATHON_SEE=1, side B = git
   snapshot of HEAD (feature OFF). Logs → results/gate_see_order_*.log
   + .stdout. Verdict per rule 7.
G. GATE 2 (pruning): same harness: side A = HEAD+SEE+SEEPRUNE, side B =
   HEAD+SEE (isolates the pruning toggle against the ordering base).
   Logs → results/gate_see_prune_*.log + .stdout.
H. Leak-suite (regression asserts): the r64/r68/r74 loss-class positions
   — preferred source: the SF19 reviews now being produced
   (results/vs_sf/round-7*-sfreview.json list our blunders with plies;
   extract FENs around those plies from the PGNs; ply parity via
   board.turn while walking mainline, never assume white=odd). Assert:
   with SEE on, the search at 2.6s budget sees the transition loss >=2
   plies earlier than V5 HEAD (compare both sides on identical FENs +
   budgets; same process discipline, fresh numba cache per tree). If the
   review JSONs aren't ready, extract the FENs from the PGNs directly at
   the known leak plies (r64 ~76-90/181-183, r68 ~50-61, r74 ~84-108).
I. Real-clock sanity (if time permits): 2 games @120s+0.5 vs HEAD,
   zero flags.
J. Ship decision: per-toggle verdicts. Default stays OFF unless a
   toggle's gate is >=0.55 with zero flags AND leak-suite green AND
   eg_check 8/8.

## Deliverables
1. Commits: search.py + BUILD.md phase entry (what/why/gate numbers) +
   ALL evidence files (.log AND .stdout, see() unit test, leak-suite
   results) — commit every file the message references.
2. BUILD.md: honest arc incl. the 0.438 P4 null reference (search
   features discriminate at 500ms; a null = don't ship).
3. Final stdout report: toggle states, both gate score lines verbatim,
   leak-suite asserts, files committed.
