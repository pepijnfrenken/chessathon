# chess-q5 — BUILD ROUND: doubled-pawn file-indexing fix (v8 candidate) + gate battery

Repo: /home/pino/projects/chessathon. Read ORIGINALITY.md first, then PROCESS.md
§0/§13/§14, BUILD.md, and the audit report /tmp/chess-q5-codex5-report.md
(finding 1 = this mission). Protocol model: the fix1 round brief in
docs/agentic-process/briefs/chessathon-q5-fix1.md.

LIVE-COMPETITION state: **v7 (night3) is the uploaded/live build** (sha
d5d57f6a6e4a, ACTIVE). HEAD dbf8958 = v7 + docs/evidence commits only
(`git diff aaad141 -- engine/ agent.py` is empty). Uploads freeze **Sep 11
10:00 UTC**. An improvement that passes gates today can still play today's
rounds (hourly 07:00-21:00 UTC). ≤6 uploads/day, slots available.

## The defect (audit codex5, finding 1 — code-verified by the orchestrator)

`engine/eval.py:597-603`: the doubled-pawn loop samples `FILE_SQ[f * 8]`.
`FILE_SQ[s]` is the mask of square s's FILE, and `f*8` = a1,a2,...,a8 — **all
twelve lines of the loop sample the a-file**: every doubled pawn on files
b-h scores ZERO penalty, and a-file doubled pawns are penalized 8x.
A ready-made fixed copy exists at `/tmp/chessathon-aud5-scratch-doubled/`
(diff its engine/eval.py against the repo to see the exact change).

## Mission A (primary): the fix, gated alone

1. **Fix**: `engine/eval.py` — `FILE_SQ[f * 8]` → `FILE_SQ[f]` in BOTH the
   white and black loops (2 subscripts). Mirror the same correction in
   `tools/texel_tune.py:253-257` (2 subscripts; dev tool, not shipped).
   NOTHING ELSE: no other eval terms, no search changes, no agent.py changes.
   One focused commit (message style: `[engine] q5-v8: doubled-pawn file
   indexing fix — FILE_SQ[f*8]->FILE_SQ[f] ...`).
2. **Demonstrate the fix is live in the jitted path**: construct two FENs
   (white doubled pawns on a-file vs b-file; assert both now report the
   doubled feature/penalty; pre-fix behavior: a-file 8x, b-file 0). Show
   jitted `E.evaluate` numbers, not just the Python decomposition.
3. **Battery (before the gate, all on candidate)**:
   - eval_decompose parity: `tools/eval_decompose.py` must still reconcile
     EXACTLY to `E.evaluate()` (total mg/eg) on a sample of FENs incl. leak
     FENs. KNOWN ISSUE (do not fix): eval_decompose.py:75-84 mixes interleaved
     MG/EG indices in some PER-TERM display rows (mobility/king-safety) —
     reconcile on TOTALS, ignore those per-term displays.
   - perft: `tools/perft_check.py` ALL PASS.
   - determinism: fixed-depth node-identity x2 (fresh process + fresh
     `NUMBA_CACHE_DIR` per run) — same build same output. Node counts WILL
     differ from v7 (eval change shifts cutoffs) — determinism means
     run1==run2, not v7-identity.
   - eg_check: `tools/eg_check.py --strong hand:1111 --weak hand:0000`
     (8 cases x both colors) @300ms — must match v7's last record (8/8, incl
     KPK-b). If a case differs, re-run at 2000ms before classifying.
   - shuffle: `tools/shuffle_check.py` — report count + threefolds; compare
     to v7 (KRvK-close-w is a documented 2-3-attempt boundary flake — repeat
     before calling a regression).
   - r92 tunnel probe: `tools/probe_r92_collapse.py` (candidate cwd, SWEEP=1)
     — audit predicts NO change to the Qb3/Rb5 tunnel; report what you get.
4. **L1 gate**: 24 games @500ms, both sides `hand:1111`, tree A/B:
   ```
   mkdir -p /tmp/chessathon-v7ref && git archive dbf8958 | tar -x -C /tmp/chessathon-v7ref
   python tools/gate_match_tree.py --side-a hand:1111 --side-b hand:1111 \
     --side-b-root /tmp/chessathon-v7ref --games 24 --move-ms 500 --seed 7 \
     --log results/gate_v8dp_vs_v7.log
   ```
   Run it as a background process and poll (do not sit on it). **The 0.45
   decision line is SOLO-CALIBRATED: the box must have no co-load.** Check
   `ps aux | grep -E "[g]ate|[s]prt|[e]ngine_side|[s]tockfish"` is empty
   (besides your own gate) before starting; the orchestrator runs nothing
   heavy. Expect ~2h.
   Bands: **≥0.55 positive / 0.45-0.55 neutral (correctness-call) / <0.45
   revisit**. Report the number; do not spin on re-runs (one re-run max).
5. **L2 leak-FEN probes**: run the committed leak tooling (see
   `tools/leak_suite.py` header for usage) on CANDIDATE and on v7ref
   (/tmp/chessathon-v7ref) over `results/leak_suite/fens.json` (98 rows) at
   2.6s; per-row compare our engine score vs the row's SF16 `eval_before`
   (referee truth — check the sign convention by reading the tool; our-side
   POV). Report: mean delta candidate-vs-v7, moves changed, and any NEW
   >=300cp rows on our side. Also run the mate stratum separately as
   diagnostic. Non-regressive = passes.

## Out of scope (do NOT do, even if tempting)
- King-color Zobrist alias / pinned-EP / TT-halfmove findings (audit 2/3/4) —
  separate future rounds.
- Real-clock SF bout, quality_ab, COMPCLAMP, NULL_DEEP, time-policy changes.
- **NO UPLOAD.** Stage only: `make_zip.sh` → verify the zip loads
  (unzip to temp, `cmp` all 7 shipped files vs tree; sha256 it) → save to
  `/tmp/night-candidates/chess-v8-dpfix.zip`.
- No edits to /tmp/chessathon-aud5 or scratch copies (read-only reference).

## Commits + records
- Commit 1: the fix + demonstration outputs.
- Commit 2: battery evidence (logs under results/, e.g.
  results/v8dp_eg_check.log, v8dp_det.log, v8dp_shuffle.log, v8dp_perft.log,
  v8dp_decompose.json, v8dp_leak_probe_*.log).
- Commit 3: gate result + PROCESS.md §15 (round record: defect, fix, L1
  number, L2 verdict, battery table, ship recommendation) + BUILD.md note.
- Final summary message: L1 score vs 0.45, L2 verdict, battery results,
  zip path + sha, and an explicit ship/hold recommendation for v8-dpfix.

## Rules
- Originality firewall: everything ships = our own code, written here.
- ONE engine workload at a time; gate only on a quiet box.
- Timebox ~3h. If the gate wedges: note it, kill it, re-run ONCE.
- Provider: you run on commandcode/deepseek-v4.1-flash (orchestrator-pinned).
  On 3+ consecutive empty/error responses: write your progress to
  /tmp/chess-q5-v8dp-progress.md and exit cleanly — never error-loop.
  On 429s: wait 20-60s, retry.
- No clarifying questions — make reasonable calls, note assumptions.
