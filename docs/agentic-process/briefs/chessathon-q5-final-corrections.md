# chess-q5 — FINAL CORRECTIONS ROUND: C3 + C4 + C5 (overnight queue, freeze-eve)

Repo: /home/pino/projects/chessathon. Read ORIGINALITY.md first, then PROCESS.md
§0/§13-§16, BUILD.md, and the audit report `docs/research/18-q5-audit6-v41-report.md`
(§C3, §C4, §C5 + §A16). Protocol model: the v8dp brief
(`docs/agentic-process/briefs/chessathon-q5-v8dp.md`).

## LIVE-COMPETITION state (READ CAREFULLY — do not disturb)

- **v9k = the uploaded build, ACTIVE on the ladder** since 15:33Z today (dashboard
  submission "v8", sha `dd5a9652cc6f`). HEAD `afa4948` == v9k for shipped files.
  Tag **`v9k-shipped`** marks the exact shipped tree. **NEVER rewrite/rebuild the
  v9k zip** (`/tmp/night-candidates/chess-v9k.zip`, sha dd5a9652...) — it is in use.
- Your candidates build **on top of HEAD (v9k)** — the gate baseline is the
  **v9k-shipped tree**, NOT v7ref:
  ```
  mkdir -p /tmp/chessathon-v9k-base && git archive v9k-shipped | tar -x -C /tmp/chessathon-v9k-base
  ```
- **Uploads freeze Sep 11 10:00 UTC.** The last useful upload window is ~06:30-09:30 UTC.
  **EVERYTHING (builds + batteries + gates + staging + records) must be COMPLETE and
  reported by 06:00 UTC.** If behind: finish in priority order C3 → C4 → C5, stop
  cleanly at 06:00 with what's done, and say exactly where you stopped.
- **NO UPLOAD by you, ever** (standing rule — Pino uploads manually). Stage only.

## The queue (ONE variable per gate, in this order)

### Candidate 1 — C3: mate-vs-fifty-move rule inversion (LOW risk, ~30 min)
Audit §C3: `search.py` `_draw_score` (lines ~341-360) declares the fifty-move draw
**before** move generation, so a position that is literally checkmate at
halfmove ≥ 100 scores 0 instead of a mate score. Measured: `7k/6Q1/5K2/8/8/8/8/8 b - - 100 1`
→ `search = 0`, expected −29999.
Fix: in `_draw_score`, when `halfmove >= 100`, first test for a deliverable mate
(cheap `legal_moves(st, scratch, False) == 0`) before declaring the draw — or check
the TT for an existing mate score (pick the cheaper correct option; keep it tight).
Demonstrate: the exact FEN above returns the mate score (before/after). Nothing else changes.

### Candidate 2 — C4: TT fifty-move context (LOW-MED, ~1 h)
Audit §C4: a warm TT entry can override a fifty-move draw that a cold search sees.
Fix: pack a "fifty-move armed" bit (or halfmove) into the **spare TT bits** and reject
mismatches at `tt_probe`. (`tt.py` has spare bits — see audit; keep the probe exact.)
Demonstrate with a warm-vs-cold probe: same position searched twice in one process
(warm TT) vs fresh process — after the fix both agree with the cold reading.
**Any TT change moves strengths: this one MUST be gated** (already planned below).

### Candidate 3 — C5: EP canonicalisation unification (LOW, ~1 h)
Audit §C5 (root cause of F3): `parse_fen` and `make_move_apply` disagree on when the
ep square exists *and is capturable* (`board.py:311-320` vs `721-733`). Fix: make them
agree — **promote the make-side test from pseudo-legal to legal**. This fixes repetition
identity for EP positions and removes a class of TT misses.
Instrument: `tools/probe_ep_key.py` (exists) 38-move control sweep before/after + perft.

## Per-candidate protocol (each one, before its gate)

1. **One focused commit** per fix (message style: `[engine] q5-c3: mate-vs-fifty
   inversion — _draw_score tests deliverable mate before the draw` etc.). NOTHING else
   in the commit beyond the fix + its demonstration.
2. **Battery on the candidate** (reuse the v8dp battery shape):
   - perft `tools/perft_check.py` ALL PASS (mandatory for C5; cheap for all)
   - determinism `tools/det_check.py` fixed-depth ×2, fresh process + fresh
     `NUMBA_CACHE_DIR` each — same build same output (node counts vs v9k MAY differ)
   - eg_check `tools/eg_check.py --strong hand:1111 --weak hand:0000` @300ms —
     compare to v9k's record (8/8-class; KPK is the known 100cp/500cp boundary cell;
     re-run at 2000ms before classifying any diff)
   - shuffle `tools/shuffle_check.py` — compare to v9k (KRvK-close-w is a documented flake)
   - the candidate's own targeted probe (C3 FEN, C4 warm/cold, C5 ep sweep)
3. **L1 gate**: 24 games @500ms, both sides `hand:1111`, candidate tree A (repo HEAD)
   vs **v9k-shipped tree B**:
   ```
   python tools/gate_match_tree.py --side-a hand:1111 --side-b hand:1111 \
     --side-b-root /tmp/chessathon-v9k-base --games 24 --move-ms 500 --seed 7 \
     --log results/gate_<tag>_vs_v9k.log
   ```
   Run as a background process and POLL (do not sit on it). **Check the box is quiet
   before starting** (`ps aux | grep -E "[g]ate|[e]ngine_side|[s]tockfish"` empty besides
   yours; box load < 2). If the orchestrator is running a desktop gate that's fine —
   that's a different box; but do not run two gates on THIS box at once.
   Bands: ≥0.55 positive / 0.45-0.55 neutral (FINE for correctness fixes) / <0.45 revisit.

## After all three (only if each one's gate is ≥0.45)

**Combined stack gate (the V5/v7 pattern):** stack C3+C4+C5 in one tree and gate it as
a whole — pooled seeds [7, 11, 13] if the box is quiet enough (use
`tools/gate_parallel.py` shape; 24g @500ms per seed), or seed 7 alone if time is short.
Stage: `make_zip.sh` → unzip to temp, `cmp` all 7 shipped files vs the combined tree,
sha256 → `/tmp/night-candidates/chess-final-combined.zip`.
If any individual gate is <0.45, EXCLUDE that candidate from the stack and say so.

## Staging + records

- Per candidate (if it passes): commit gate + battery records under `results/`; stage
  zip `/tmp/night-candidates/chess-<c3|c4|c5>.zip`; commit message carries the gate number.
- PROCESS.md: add a §16c-style section for this round — defect, fix, battery, gate
  number(s), zip sha, and an explicit ship/hold recommendation per candidate + the stack.
- Final report to the orchestrator (in your closing message): per candidate — commit
  hash, battery verdict, gate number (W-L-D + score), zip path + sha256, and the
  combined-stack number if run. State clearly what you did NOT finish.

## Out of scope (do NOT do)

- Do not touch eval.py (no more strength candidates this late — C7/C8/C11 are closed).
- Do not touch `agent.py`, zobrist keys (C6), or the v9k zip.
- Do not re-run/re-litigate anything from audit-6 already decided (C1/KBR, r92 tunnel,
  rootorder, time policy). Do not upload.
