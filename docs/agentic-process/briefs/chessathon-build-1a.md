# CHESSATHON BUILD — Phase 1a: Minimal Uploadable Agent + Local Harness

You are building the FIRST SHIPPABLE chess agent for the AI Chessathon. Goal:
get a **correct, legal, validation-passing agent** we can upload TODAY (Sep 7)
so the team starts collecting ladder data. Strength is secondary — correctness
and pipeline are the point. A stronger engine (own numba board+movegen) comes
in a later mission and will replace this file.

## MANDATORY FIRST (before ANY code)
Read, in order:
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW. All code here
   must be written fresh by you in this repo. No copying/adapting existing
   engine source (sunfish, python-chess examples, GitHub engines). Standard
   algorithms implemented fresh are fine.
2. `/home/pino/projects/chessathon/CLAUDE.md`
3. `/home/pino/projects/chessathon/BUILD.md` — append your design decisions
   to the log when done.
4. `/home/pino/projects/chessathon/docs/research/INDEX.md` + `01-engine-architecture.md`
   (skim — they define the full plan; you implement only 1a)
Acknowledge in your final summary that you read ORIGINALITY.md.

## What to build (all in /home/pino/projects/chessathon/)

### 1. `agent.py` — minimal but real engine (root of submission)
- Exposes `get_move(fen: str, time_left_ms: int) -> str` returning a legal UCI move.
- Implement a **correct, simple alpha-beta negamax with iterative deepening**:
  - depth ~3-4 fixed (safe, fast in pure Python on 1 core) + a **simple
    material + piece-square-table evaluation** (write your own PST values —
    standard published concepts OK, implement fresh; keep it simple: material
    + basic PST + a tempo bonus is plenty for 1a).
  - Simple move ordering: captures first (MVV-LVA), then others. No TT needed
    yet (keep it small and correct). Quiescence: a *minimal* capture-only
    quiescence is strongly encouraged (prevents the worst horizon blunders)
    but keep it simple and bug-free — if unsure, depth 3 + captures-first
    ordering + tiny qsearch is fine.
  - **Correctness first**: never return an illegal move, never crash, never
    hang. Wrap the search in try/except that falls back to a legal move from
    `chess.Board(fen).legal_moves` on any error.
  - Must import fast (<60s init — it will be; no numba/torch yet), no network,
    no filesystem writes at runtime.
  - Use python-chess for move legality, FEN parsing, and move application —
    that's the permitted preinstalled library (I/O + oracle). Your own logic
    (search/eval) is the original part.
- `agent.py` must also work as `python agent.py` for a quick self-test
  (optional: main that plays a few moves against itself and prints them).

### 2. Local harness `tools/local_game.py` (dev tool, NOT shipped in zip root)
- Plays two agents (or agent vs a simple random/material bot) against each
  other under the REAL clock shape: 120s + 0.5s/move per side, using
  `get_move(fen, time_left_ms)` with a real time_left_ms decrement + increment.
- Runs N games from a few varied starting positions (use 2-3 curated-ish FENs
  or standard start + a couple of common openings you generate via
  `chess.Board()` + a few ply from a small opening list — write the opening
  moves yourself, do not copy a book file).
- Reports: games won/lost/drawn by each side, and flags ANY illegal move /
  crash / timeout / slow move (move taking > ~50s). This is the correctness
  gate: ZERO illegal moves, ZERO crashes across all games.
- Keep it dependency-light (python-chess only).

### 3. `make_zip.sh` (repo root)
- Assembles `agent.zip` = exactly `agent.py` at zip root (50MB limit — ours
  will be KBs). Nothing else. No .git, no docs, no tools, no test files, no
  __pycache__.
- Verify after build: `unzip -l agent.zip` shows only agent.py; and the zip
  imports + `get_move` works from a *different* cwd (simulate the box:
  `cd /tmp && python3 -c "import sys; sys.path.insert(0,'/home/pino/projects/chessathon'); from agent import get_move; ..."`).

## Hard requirements
- **ORIGINALITY**: every line written by you in this repo. Do NOT fetch or
  paste any engine code from the internet. Standard algorithm *ideas* are
  fine; implementations are yours. Commit granularly (at least: scaffold,
  agent, harness, zip) so git history shows organic development.
- **Correctness gates** (run them, show output in your summary):
  1. `python -c "from agent import get_move; print(get_move(chess_start_fen, 120000))"`
     returns a legal move, fast (<2s).
  2. Self-test: 20+ fast games in the harness at tiny clocks (e.g. 2s+0.1s)
     → 0 illegal moves, 0 crashes, 0 timeouts.
  3. Zip test: build agent.zip, verify contents + import-from-zip works.
- Keep it SIMPLE and CORRECT. This is the floor we ship today; the numba
  engine replaces it in 1b.

## When done
- Commit everything (agent.py, tools/local_game.py, make_zip.sh, harness
  output log under `results/`).
- Append a short "Phase 1a" entry to BUILD.md (what you built, gates passed,
  measured move times).
- Final summary: files created, gate outputs (perft not applicable yet — show
  the 3 gates above), zip size, and any risks/notes for 1b.

<!-- source session: 2026-09-07T07-02-21-808Z_01a07aac-d370-7000-9c83-51be5c175bf5.jsonl -->
