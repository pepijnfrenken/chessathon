# Chessathon Research — Workstream 4: Chess Models & Methodology

You are building the RESEARCH KNOWLEDGE BASE for a chess-engine competition (AI Chessathon). Produce **markdown docs**, NOT code. Save under `/home/pino/projects/chessathon/docs/research/`.

## MANDATORY FIRST: READ BEFORE ANYTHING
- `/home/pino/projects/chessathon/ORIGINALITY.md` — the repo's law. The submission must be 100% code WE write during the event. NO copying/porting/adapting existing engine source. NO shipping pretrained models or downloaded weights. Classical search is the default plan; a self-trained NN is the only model path allowed (and only if time permits).
- `/home/pino/projects/chessathon/BUILD.md` — design log.
- Acknowledge in your final summary that you read both.

**Methodology inspiration IS fair** — reading papers/blogs/source for IDEAS is standard. Copying code is not. Your doc must separate "what they did (methodology)" from "what we may NOT copy (code/weights)".

## Competition constraints
1 core, 2GB RAM, no GPU/network at runtime. python-chess 1.11.2, numpy 2.5.2, numba 0.67.0, torch 2.13.0+cpu, onnxruntime 1.29.0 preinstalled. 120s+0.5s/move, 60s init, pondering allowed, 50MB zip. Training data unrestricted incl. positions annotated by an existing engine (but we can only generate that data LOCALLY before submission — no network at runtime, and no engine binaries in the zip). Local dev box: 6-core CPU only, no GPU. ~4 days until uploads close (Sep 11).

## Task: `docs/research/05-chess-models-and-methodology.md`
Research how the famous chess NN engines were BUILT (methodology), and distill what's actionable for us. Cover:

### Part A — How they were built (concise per system, with sources)
1. **AlphaZero** (DeepMind): architecture (residual net, policy+value heads, ~19x256? verify), self-play RL with MCTS, no human knowledge, data generation loop, temperature/opening randomization, compute scale.
2. **Leela Chess Zero**: distributed self-play, data lake format, training pipeline, how the community scaled it, net sizes over time, how it integrates with classical search (MCTS tree + policy prior).
3. **Stockfish NNUE**: what it is (efficiently-updatable neural network replacing hand-crafted eval INSIDE alpha-beta), architecture (inputs = halfKP piece placements, two small FC layers, quantized int8), training data (SF self-play, supervised on search q-values/evals from stronger SF), how it's updated incrementally for speed, why it beat hand-eval so decisively.
4. **Maia**: human-like chess, trained on human games (Lichess) to predict human moves per rating bucket; different objective (accuracy vs strength); used for fair rating estimation.
5. **Small/compact nets for constrained compute**: what's the smallest NN that adds real strength? (e.g., tiny NNUE ~2-8MB, nets from the "nnue-pytorch" ecosystem, 768→256→1 halfKP nets; also onnxruntime CPU inference speed reality.)

### Part B — Methodology takeaways (what's actionable for OUR build)
1. **Can we legally+feasibly train our own small net in ~2-3 days on a CPU-only box?** Concrete plan if yes: generate positions (our own engine search / random self-play at low depth), annotate with q-values (locally, using an engine — data only, never shipped), train a tiny net (torch CPU, halfKP or simple 768→N→1), export to onnxruntime int8, integrate as our eval replacing/augmenting hand-crafted eval. Honest estimate: data size needed (10k/100k/1M?), training time on 6-core CPU, expected Elo gain vs hand-eval, risk (overfitting, integration bugs, time lost). Verdict: worth it or not, given the deadline and that classical search alone is already a full entry?
2. **Even if we ship NO net**: what methodology lessons transfer? (a) eval quality is the biggest lever below master level; (b) self-play/Texel tuning beats hand-tuning (cross-ref doc 02); (c) test-driven iterative improvement via SPRT self-play; (d) opening diversity in test games; (e) policy-like move ordering (can a cheap heuristic approximate it — e.g., PST+SEE ordering — or a tiny policy net as ORACLE only at the root... careful: any net we ship must be self-trained).
3. **Time/ROI ranking**: given 4 days, rank by expected Elo-per-hour: hand-eval + tuning vs tiny net vs deeper search vs endgame tables vs opening book. Be honest and concrete.

### Part C — Fairness boundary (state clearly in the doc)
What's allowed (reading anything, standard algorithms, self-trained weights, engine-annotated training data, methodology mimicry) vs forbidden (copying source, shipping any downloaded net/weights/engine). This doc itself must NOT contain copy-pasted implementation code — descriptions and citations only.

Dense, practical, cited inline (URLs), under ~300 lines. Prioritize Part B — that's what decides our build.

<!-- source session: 2026-09-07T06-38-20-080Z_01a07a96-d3b0-7000-8c93-c58e714b378a.jsonl -->
