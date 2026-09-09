# Chess builder: P4 — dynamic null-move reduction (R=3 at depth >= 6)

## Mission
Implement ONE search-structure feature on the V5 engine (HEAD = e760ed8
era, working tree includes ladder records through r74, clean), validate it,
gate it, commit + update BUILD.md. Brief from the brainA probe report
(/tmp/chess-brainA-report.md §P4). You may read that report's P4 section
for the full rationale, but the implementation contract below is
authoritative.

## Rules (never bend)
1. ORIGINALITY.md is LAW — read it first. Everything you write is your own
   code in this repo. No third-party engine code, ever.
2. ONE feature. Do NOT touch eval.py, time.py, board.py, agent.py policy,
   or any other search feature. Do NOT "fix" anything else you notice —
   note it in the commit message/BUILD.md instead.
3. Never edit code while a gate/SPRT runs. Before starting gates:
   `ps aux | grep -E "sprt|engine_side|gate_match"` must be EMPTY; kill
   orphans with bracketed patterns (`pkill -f "[s]prt.py"` — plain
   patterns SIGTERM your own shell).
4. PY = /tmp/chessbench/bin/python. Fresh NUMBA_CACHE_DIR per tree
   variant if you test side-by-side snapshots.
5. Commit checkpoint as you go; leave the tree committed + known-good.
6. Model/provider hiccups: wait 20-60 s, retry; never guess. If a command
   fails, read the error and adapt.

## Implementation contract
- engine/search.py null-move section: today NULL_R is a fixed global (2)
   with guards (beta > 0; zugzwang guard _count_nonpawns >= 2 — leave all
   guards untouched). Add, next to the existing env toggle
   CHESSATHON_NULLR (accepts 2|3|4 as the BASE reduction), a new import-
   time toggle CHESSATHON_NULL_DEEP (default 0 = off): when on, at
   depth >= CHESSATHON_NULL_DEEP_MIN (default 6) use a DEEPER reduction
   NULL_R_DEEP (default 3). All as module globals baked at import (numba
   compiles globals — same pattern as existing toggles; verify with a
   print at import in the A/B process).
- Nothing else changes. No eval changes, no window changes, no qsearch
   changes.
- Docstring update in search.py header feature list.

## Validation + gates (in order, all must pass before commit)
1. Perft parity d1-d4 (tools/perft_check.py or your own perft vs
   python-chess on 3 FENs incl. an en-passant FEN) — feature OFF must be
   byte-identical node counts to HEAD; feature ON must ALSO be perft-clean
   (perft counts move generation, not search — it validates no movegen
   damage).
2. Determinism: same position, feature ON, 2 fresh processes → identical
   move + score.
3. eg_check 8/8 (SHIPPED config — read the skill notes: default args A/B
   eval configs; you need tools/eg_check.py --strong hand:1111 --weak
   hand:0000 semantics; verify the tool's usage first) — the null-deep
   change must not break endgame conversion (zugzwang guard must hold:
   KQvK/KRvK/KPK all 8 cases WIN).
4. NPS bench: feature OFF vs ON, fixed depth, node counts equal (identical
   nodes expected — null changes TREE only when ON; OFF must equal HEAD
   exactly, node-for-node at fixed depth d8: 1,030,699 nodes on the
   standard bench position — if OFF differs from that, stop and diagnose).
5. THE GATE: tree A/B 24 games @500ms, `tools/gate_match_tree.py` with
   both sides hand:1111 — side A = your new tree (feature ON), side B =
   git snapshot of HEAD (feature OFF). Read the .stdout header + final
   `score:` line. Zero flags required. Verdict rules: score >= 0.55 =
   ship candidate; 0.45-0.55 = null band — report honestly, do not spin;
   < 0.45 = revert (feature OFF must remain the default). Note: the
   official score line counts from side A's perspective — trust it, not
   manual tallies. Mid-gate polls are NOT verdicts; run to completion.
6. Real-clock sanity (if time permits): 2 games @120s+0.5 vs HEAD side B
   (local_game.py), zero flags.

## Deliverables
1. Commit: engine/search.py + BUILD.md phase entry + evidence files
   (perft/determinism/eg_check logs + the gate .log AND .stdout) — commit
   EVERY evidence file the message references.
2. One-line BUILD.md entry: what, why (brainA P4: node-starved engine,
   depth is the cheapest correct gain; LMR gate precedent proves 500ms
   gates discriminate search-structure changes), gate result.
3. Final report to stdout: feature state, gate score line verbatim, files
   committed.
