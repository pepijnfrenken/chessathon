# CHESSATHON BUILD — Phase 1b: Numba Engine Core (board + movegen + search)

Context: Phase 1a shipped a minimal pure-Python alpha-beta agent that is
validated and rated 47/351 on the ladder. This phase REPLACES agent.py's
internals with a real numba-jitted engine: our own board + movegen +
make/unmake + search core. Target: 25-40x speedup (depth 8-10 vs 3-4) →
Weiss-class.

## MANDATORY FIRST (read before ANY code)
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW. Every line of
   code written fresh in this repo. NO copying/adapting existing engine
   source (sunfish, python-chess example engines, any GitHub engine). NO
   fetching engine code from the internet. Standard published algorithm
   *ideas* are fine; implementations are YOUR OWN. Granular commits.
2. `/home/pino/projects/chessathon/CLAUDE.md`
3. `/home/pino/projects/chessathon/BUILD.md` — append Phase 1b entry when done.
4. `/home/pino/projects/chessathon/docs/research/INDEX.md` + `01-engine-architecture.md`
   — the blueprint. Follow it.
5. Current `agent.py` (1a) — you're replacing its guts while keeping the
   `get_move(fen, time_left_ms) -> str` interface + zip layout.
Acknowledge reading ORIGINALITY.md in your final summary.

## The environment (design for it)
1 core, 2GB RAM, no GPU/network at runtime. python-chess 1.11.2 + numpy +
numba 0.67.0 preinstalled. NO torch import at runtime (imports ~1s + hundreds
MB; RSS budget ~2GB). 120s+0.5s/move, 60s init budget (JIT warmup MUST run
inside it — call a jitted fn at import). Filesystem read-only at runtime →
`NUMBA_CACHE_DIR` must point at /tmp scratch (set in agent.py before numba
compiles). Process stays alive between moves (state persists). 50MB zip.

## What to build (in /home/pino/projects/chessathon/)

### 1. `engine/board.py` [numba] — OUR OWN board + movegen + make/unmake
- Our own design (mailbox or bitboards — your choice, justify in BUILD.md).
  Complete: legal movegen incl. castling, en-passant, promotions; check
  detection; make/unmake; zobrist hashing (own scheme); FEN parse/export.
  Must be numba-jittable (use typed containers / arrays / plain ints —
  NO python-chess objects inside jitted code).
- **Correctness gate #1 — PERFT PARITY**: perft(1..5) must EXACTLY match
  python-chess on >=4 positions (startpos + Kiwipete + 2 varied) before
  proceeding. This is non-negotiable.

### 2. `engine/search.py` [numba] — search core (from research doc 01 §1)
- Iterative deepening + negamax alpha-beta (fail-soft) with PVS.
- Move ordering: TT move → MVV-LVA captures (SEE optional/skip) → killers
  (2/ply) → history → rest.
- Quiescence: stand-pat + captures; full evasion search when in check;
  cap q-depth (~10). No killers/TT in q-search.
- Transposition table `engine/tt.py`: PACKED numpy/numba arrays (NOT dicts),
  ~12-16B/entry, target 2^21-2^23 entries (32-192MB), depth-preferred
  replacement, 2-4 way buckets. Mate scores stored as MATE-ply.
- Null-move pruning (R=2/3, skip in check + low piece count), LMR (quiet
  non-first moves, depth>=3, cap 2), check extension (+1 in check).
- Repetition/draw handling: track history of positions (stack of zobrist
  keys) to avoid/seek 3-fold; respect 50-move.
- Root: pick best from last completed iteration; always have a legal
  fallback move from python-chess if anything throws.

### 3. `engine/eval.py` [numba] — Phase-1b eval (keep SIMPLE, tune later)
- Tapered eval: material + PST (write your own values or cite a published
  PST table in BUILD.md with source — either is fine, implement fresh) +
  bishop pair + tempo. That's it for 1b. (Pawns/mobility/king safety come
  in the eval-tuning phase.)

### 4. Time management `engine/time.py` [pure Python, cold path]
- Adaptive: target ~5-10% of remaining per move, soft cap ~30-45s, hard
  never-flag floor (keep >=15s + 30*increment unless only one legal move).
  Stop the search cleanly between iterations (check a stop flag; the 1a
  interruptible pattern already exists in agent.py — reuse that approach).

### 5. `agent.py` (replace internals, KEEP interface)
- `get_move(fen, time_left_ms) -> str`. Import-time: set NUMBA_CACHE_DIR to
  /tmp, import engine modules, WARM UP the jitted functions (call a small
  jitted fn / do a tiny search) so compile happens in init budget, and time
  it (must be < 60s).
- Parse FEN once per call into our board; search; return UCI string via
  python-chess legality check at root (or our own UCI conversion + python-
  chess verify as belt-and-braces). try/except fallback to a legal
  python-chess move — NEVER crash.
- Keep agent.py importable and fast; do NOT import torch.

### 6. Harness + gates
- Reuse/extend `tools/local_game.py` to play engine-vs-engine under the real
  clock shape. **Correctness gates (run, show output):**
  1. Perft parity (above) — exact match, show table.
  2. Speed: nps benchmark (perft + search nodes/s) — show numbers; expect
     big jump vs 1a.
  3. Harness: 20+ games vs the 1a agent (equal short TC ~5s+0.05s) — 0
     illegal/crash/flag AND 1b should win a clear majority (>=65%). Show
     score + flags.
  4. Zip test: rebuild agent.zip (agent.py + engine/ at root), unzip in
     clean dir with python-chess installed, get_move returns legal move
     fast, total import+JIT < 60s.
- Update `make_zip.sh` to include engine/ (zip root: agent.py + engine/*.py,
   nothing else).

## Originality & hygiene
- Fresh code only. Commit granularly as you go (board+perft, eval, search,
  agent integration, harness results, zip). git history = provenance.
- Update BUILD.md with design decisions (board representation choice, TT
  sizing, measured nps/perft, why).
- Keep modules readable + commented for a judge.

## Done when
All 4 gates pass and everything is committed. Final summary: files, perft
table, nps numbers, harness score vs 1a, zip size, init/JIT time, risks/notes
for the eval-tuning phase (next).

<!-- source session: 2026-09-07T08-39-20-275Z_01a07b05-9bd3-7000-a003-682a1a2351a3.jsonl -->
