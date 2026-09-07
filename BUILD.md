# BUILD.md — Design log (originality record)

> This file exists to prove the engine is OUR original work and to let
> Pino walk a judge through every design decision. Update it as the build
> progresses. Read `ORIGINALITY.md` first — it is the law of this repo.

## Competition (from official docs, 2026-09-07)

- **AI Chessathon** — build a chess agent (`get_move(fen, time_left_ms) -> uci`).
- Env: 1 CPU core, 2 GB RAM, no GPU, no network. python-chess 1.11.2,
  numpy, numba 0.67.0, torch-cpu, onnxruntime preinstalled.
- Clock: 120 s + 0.5 s/move. 60 s init. Pondering allowed (process alive
  between moves, own core after `get_move` returns).
- Classical search is a full entry. 3rd-party engines banned in the zip.
  Books/tablebases allowed as data. 50 MB unzipped. Source must be
  readable by a judge. Uploads close 11 Sep 11:00.

## Strategy (why classical search, not a model)

1 core / no GPU / no network + "classical search is a full entry" +
"third-party engines banned, model must be self-trained" ⇒ the highest-EV,
lowest-risk path to a strong legal entry is an **original, numba-jitted
alpha-beta engine with a hand-tuned evaluation**, not an NN.

## Design log

(To be filled as we build — every component, why, what we measured.)

## Current status

- [ ] Research KB complete (docs/research/)
- [ ] Phase 1: minimal legal agent + local harness
- [ ] Phase 2: search core (negamax/alpha-beta/ID/TT/quiescence)
- [ ] Phase 3: evaluation
- [ ] Phase 4: time management + pondering
- [ ] Phase 5: tuning + testing vs baseline
- [ ] Submission zip

## Build record

- 2026-09-07: repo scaffolded; ORIGINALITY.md + BUILD.md written; research
  agents launched (architecture / eval / landscape workstreams).
