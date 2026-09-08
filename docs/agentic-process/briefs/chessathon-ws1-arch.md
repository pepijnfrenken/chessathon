# Chessathon Research — Workstream 1: Engine Architecture

You are building the RESEARCH KNOWLEDGE BASE for a chess-engine competition (AI Chessathon). You are a research agent: produce **markdown knowledge-base documents**, NOT code. Save all output under `~/.hermes/.aiwg-shared/kb/` no — save under the repo: `/home/pino/projects/chessathon/docs/research/`.

## The competition constraint (MUST design for this)
- ONE Python process, 1 dedicated CPU core, 2 GB RAM, NO GPU, NO network.
- python-chess 1.11.2 preinstalled. Also preinstalled: torch 2.13.0+cpu, numpy 2.5.2, onnxruntime 1.29.0, numba 0.67.0.
- Time: 120s per side + **0.5s increment per move**. 60s init budget before clock.
- Process stays alive between moves; **pondering allowed** (thinking during opponent's move, on your own core). Only 1 thread helps (single core).
- **Classical search is a full entry.** A NN is optional.
- Compiled speed = numba JIT (JIT compiles Python in-process; first call pays compile cost). NO Cython/native binaries. Pure Python speed matters.
- 50 MB zip max. Files read-only except 256MB /tmp scratch. NO network at runtime.
- Chess knowledge allowed: opening books + tablebases OK (chess.polyglot + chess.syzygy in base image).

## Your task: write a definitive architecture playbook
Research (web, CPW, GitHub, your knowledge) and write `docs/research/01-engine-architecture.md` covering:

1. **Search framework**: iterative-deepening negamax with alpha-beta; PVS (principal variation search) vs plain; aspiration windows; move ordering (MVV-LVA, killer moves, history heuristic, TT move first, captures); quiescence search (stand-pat + captures, checks handling); transposition table sizing/strategy for 2GB RAM; repetition draw handling; check extension / singular extensions; late move reductions (LMR) — which are worth it in Python.

2. **Evaluation**: a strong hand-crafted eval for a CPU-only engine: material + piece-square tables (PeSTO-style), mobility, pawn structure (doubled/isolated/passed), king safety, tempo. What actually matters at ~depth 6-9 with 120s+increment? Tapered eval (middlegame/endgame interpolation).

3. **Python performance reality**: what's feasible in pure Python + numba on 1 core in 120s? Realistic depths (pure python maybe depth 4-6; numba-jitted maybe 6-9). What to jit vs leave pure. Why python-chess movegen is the bottleneck and how to work around (bulk movegen, using board.legal_moves efficiently, avoiding FEN parsing each move — use board.push/pop + zobrist).

4. **Time management**: how to use 120s + 0.5s increment optimally; how much to spend per move; using the increment; pondering strategy; when to stop searching (no obvious refutation, stable PV); sudden-death vs increment clock behavior; the "play the clock" principle.

5. **Pondering**: how to implement pondering with python-chess in the given architecture (think during opponent's move, verify the opponent's actual move matches your predicted move, else restart).

6. **Opening book + endgame**: is a polyglot opening book worth it? Which openings to include (given games start from "curated level positions" not the standard start — so a book may be less useful). Syzygy tablebases — 3-4-5 piece worth shipping in 50MB? (5-piece is ~1GB+ — too big; what fits?)

7. **Recommended architecture** (synthesize): concrete module layout, what the search/eval split should be, the order to build/test in, and honest expected strength (CCRL-ish estimate) for a well-built numba-jitted engine on this hardware.

Prioritize PRACTICAL, CORRECT, CURRENT info. Cite sources inline (URLs). Be concrete with numbers. Keep it under ~250 lines but dense. This is the playbook the team codes from — get it right.

<!-- source session: 2026-09-07T06-32-38-037Z_01a07a91-9b95-7000-9fc4-44d9861c5e51.jsonl -->
