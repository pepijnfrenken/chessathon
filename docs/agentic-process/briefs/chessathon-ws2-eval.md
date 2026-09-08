# Chessathon Research — Workstream 2: Evaluation & Testing Infrastructure

You are building the RESEARCH KNOWLEDGE BASE for a chess-engine competition (AI Chessathon). Produce **markdown docs**, NOT code. Save output under `/home/pino/projects/chessathon/docs/research/`.

## The competition constraint (design for this)
- ONE Python process, 1 core, 2GB RAM, no GPU/network. python-chess 1.11.2, numba 0.67.0, numpy/torch/onnxruntime preinstalled. 120s+0.5s/move. 60s init. Pondering allowed.
- Classical search is a full entry; NN optional. 50MB zip. Books + tablebases allowed as data.
- Games start from **curated level positions** (not standard start) — so opening-book value is limited; midgame/endgame skill matters.
- Third-party engines (Stockfish/Lc0/Maia) PROHIBITED in the submission. But for TESTING locally you can use whatever you want.

## Your task: write two docs

### A. `docs/research/02-eval-and-tuning.md` — Evaluation & tuning
1. Hand-crafted eval deep-dive: material values (modern: Q=9.5? P=1, N=3.05, B=3.33? or classical?), piece-square tables (PeSTO, or better modern ones — find actual good PST data with sources), tapered eval, mobility, king safety, pawn structure. What distinguishes a ~2400-CCRL engine from a ~1800 one in eval terms?
2. **Tuning methodology**: Texel tuning (what it is, how to run it with no GPU — is it feasible CPU-only?), using human game data / engine-annotated data (allowed: "training data unrestricted incl. positions annotated by an existing engine"), or simpler hand-tuning with self-play + SPRT. What's the minimum viable tuning approach for a week-long build?
3. Which eval terms are highest ROI per implementation hour. What NOT to bother with.
4. **Testing infrastructure** (local, for development): how to test engine strength without Stockfish in the loop... or WITH it locally for dev: quick ways to get a baseline engine binary (is it OK to download Stockfish for LOCAL dev-testing only, clearly not shipping it? Yes — clarify: the ban is what ships in the submission). How to run engine-vs-engine matches with python-chess, time controls, opening positions, and compute an approximate Elo / use SPRT (e.g. via cutechess or a python harness). Recommend the fastest reliable local dev loop.

### B. `docs/research/03-openings-endgames.md` — Openings, endgames, adjudication
1. Opening book strategy given curated starting positions: worth shipping a polyglot book? Which positions are "curated level"? What does the house-bot baseline (CCRL public ratings) suggest about required strength?
2. Tablebases: exactly what fits in 50MB (3-4 piece syzygy is ~1MB? 5-piece ~1GB no). Is chess.syzygy probing worth it for the endgame? What about the 300-ply adjudication rule (material decides) — when to play for the win vs draw.
3. Draw/repetition handling with python-chess: threefold/fifty-move claimed by referee; how the engine should avoid/seek repetition; the 300-ply adjudication (material decides if no result) — implications for endgame play (winning KQvK etc.).
4. Practical endgame knowledge: what eval heuristics make an engine convert won endgames reliably (avoiding stalemate traps, KQ/KR mate technique, opposition)? Or is a tablebase probe the only reliable way?

Keep both dense, practical, current, with inline source URLs, under ~200 lines each.

<!-- source session: 2026-09-07T06-32-41-010Z_01a07a91-a732-7000-9947-e6ccbd6bf1d9.jsonl -->
