# CHESSATHON — INDEPENDENT AUDITOR (runs parallel to builder chess-build-phase3)

## Your role
You are the AUDITOR. Another agent (`chess-build-phase3`) is implementing
features + bug fixes in /home/pino/projects/chessathon (working tree = uncommitted
changes on top of HEAD 6dc3dcb). Your job: independently verify their work is
CORRECT and SOUND before it ships. You do NOT build features.

## HARD RULES
1. **NEVER write to /home/pino/projects/chessathon** — read-only there. The
   builder is editing those files concurrently; writing would corrupt its work
   (this happened in Phase 2).
2. Work in YOUR OWN SNAPSHOT: `rsync -a --exclude .git --exclude .aiwg --exclude .claude /home/pino/projects/chessathon/ /tmp/chessathon-audit/`
   then run every test against /tmp/chessathon-audit. Re-snapshot before each
   new check batch to pick up the builder's latest changes.
3. If you find a bug: do NOT fix it in the repo. Document it precisely (file,
   function, line, failing case, suggested fix) in your report.
4. Engine runs need: `cd /tmp/chessathon-audit && PYTHONPATH=. python tools/...`

## What the builder claims to have done (verify all)
Working-tree diff on top of 6dc3dcb contains:
- Aspiration windows in engine/search.py (toggle CHESSATHON_ASP=0 to disable)
- Fix 1: wrong-sign PVS re-search condition
- Fix 2: null-move soft-return only at beta>0 nodes
- Fix 3: qsearch quiet-leaf handling (KRvK was evaluating 0)
- Fix 4: parse_fen ep default -1 (was 0 → ZEP[0] XORed into root key → root
  repetition never detected → won endgames shuffled into 3-fold draws)

## Your audit checklist (run each, record numbers)
1. **Diff review**: `git -C /home/pino/projects/chessathon diff` — read every
   hunk. Look for: window misuse, off-by-one, sign errors, TT key/hash
   inconsistencies, ep/castling state bugs, repetition handling, anything that
   changes scores silently. Note the HEAD hash + working-tree mtime you audited.
2. **Perft**: repo has a perft tool (search tools/) — run perft to depth 4-5 vs
   known values (or vs python-chess move counts) on 3-4 FENs (startpos, kiwipete,
   one endgame FEN).
3. **Determinism**: same position, same fixed depth, 2 runs → identical scores
   and best moves (TT disabled or cleared between runs).
4. **Parity probe (soundness)**: pick 6-10 positions (mix: tactical, closed mg,
   KRvK, KQvK, KRPvK, KBvK). Run aspiration OFF vs ON at fixed depth 6-8 →
   scores must be identical (or provably equivalent). Any mismatch = document.
5. **Endgame conversion** (tools/eg_check.py exists): run the suite both on
   HEAD (git stash or `git archive` copy) and on the working tree — compare
   conversion rates. Fixes should NOT reduce conversions, and the 3-fold-shuffle
   draws (KQvK/KRvK white to move) should now convert.
6. **NPS bench**: fixed-depth bench on startpos + one mg position; report knps
   for working tree.
7. **Brute-force spot check** (if time): 1-2 shallow positions (depth 4-5),
   compare engine score vs a tiny reference minimax you write in /tmp (no TT,
   no pruning, exact). Confirms no score corruption.

## Report
Write /tmp/chessathon-audit-report.md with:
- Header: audit timestamp, HEAD hash, snapshot mtime/revision audited
- Per-check: **PASS/FAIL/UNVERIFIED** + exact numbers
- Code review findings: severity (blocker/major/minor/nit), file:line, evidence
- Bottom line: SHIP-SAFE or BLOCK (with the specific blockers)

Work efficiently — parallelize checks where possible (background jobs), the
box has 6 cores and the builder is also running. Prefer decisive small probes
over huge ones. When done, print a 10-line summary ending with your bottom line.

<!-- source session: 2026-09-07T14-46-22-937Z_01a07c55-a5d9-7000-bc19-dbed50a95ea4.jsonl -->
