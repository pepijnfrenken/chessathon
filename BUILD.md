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

- [x] Research KB complete (docs/research/)
- [x] Phase 1: minimal legal agent + local harness
- [ ] Phase 2: search core (negamax/alpha-beta/ID/TT/quiescence)
- [ ] Phase 3: evaluation
- [ ] Phase 4: time management + pondering
- [ ] Phase 5: tuning + testing vs baseline
- [ ] Submission zip

## Build record

- 2026-09-07: repo scaffolded; ORIGINALITY.md + BUILD.md written; research
  agents launched (architecture / eval / landscape workstreams).
- 2026-09-07: research KB: `docs/research/05-chess-models-and-methodology.md`
  (AlphaZero/Lc0/SF-NNUE/Maia methodology; verdict: train-our-own small net is
  feasible (GPU training now allowed — only shipped weights must be ours) but
  ONLY as a gated days 3-4 sprint behind the classical engine; hand eval +
  tuning remains the top Elo/hour; classical search stays the guaranteed ship).
- 2026-09-07: **Phase 1a shipped — minimal uploadable agent** (`agent.py`,
  pure Python, no numba yet). Commits 338144f..2b4cc14.

### Phase 1a — minimal legal agent (shipped 2026-09-07)

What was built (all fresh code in this repo; ORIGINALITY.md read and honored
before any code):

- `agent.py` — iterative-deepening alpha-beta negamax, pure Python.
  python-chess 1.11.2 used ONLY as I/O + legal-move oracle (FEN parse, move
  application, legality) — search and eval are ours.
  - Move ordering: MVV-LVA captures, promotions, a single killer per ply.
  - Minimal capture-only quiescence (stand-pat; full evasions when in
    check; mate/stalemate handled at qsearch entry).
  - Eval: material + our own hand-written PSTs tapered mg/eg by game phase
    (standard phase weights N1/B1/R2/Q4, max 24) + tempo +10; king PST is
    castle-back in middlegame, centre in endgame; insufficient material → 0.
  - Draws in search: fifty-move, repetition (python-chess `is_repetition(2)`
    = position already seen once in the path).
  - Time: spend ≤8% of remaining clock, capped 1.25 s, never >50% of tiny
    remaining; search is interruptible INSIDE a subtree (timeout check every
    512 nodes, `SearchTimeout` caught at root, previous-iteration best
    returned; push/pop are finally-safe). Any unexpected error falls back to
    a legal move — never illegal, never crash, never hang.
  - `get_move` returns `"0000"` only when the game is already over.

- `tools/local_game.py` — self-play harness under the real clock shape
  (base+inc per side, genuine decrement/increment), agent vs a material-greedy
  bot (our own tiny bot), 5 varied starting positions (start + 4 openings
  written by hand), flags illegal/crash/timeout/slow(>50s), 300-ply cap with
  material adjudication, non-zero exit on any flag.

- `make_zip.sh` — builds `agent.zip` containing exactly `agent.py` (uses
  `python3 -m zipfile`, no external zip binary needed on the box), lists
  contents, imports `get_move` from `/tmp` with the zip on sys.path.

Gates (all passed on the shipped code):

1. `get_move(start_fen, 120000)` → legal move; measured **1.25 s** (budget
   cap; spec wanted <2 s). Per-move at the 120 s clock: start/middlegame/
   sharp/endgame all ≈ 1.25 s, all legal.
2. 24 games at 2 s + 0.1 s in the harness: **17 wins / 7 losses / 0 draws,
   ZERO flags** — no illegal moves, no crashes, no timeouts, no slow moves
   (log: `results/local_games_20260907_071953.log`, seed 7).
3. `agent.zip` = exactly `agent.py` (4.4 KB), import + legal move from an
   unrelated cwd.

Notes / risks for 1b:

- Strength is a floor (depth 3-5 typical; pure-Python nps ceiling). The
  harness shows it beats the random+material bot but shuffles endgames.
- Two real bugs found during gating are instructive for 1b: (a) an eval
  phase-counting bug (KeyError) that silently degraded to fallback moves —
  validate eval from a known position on every change; (b) non-interruptible
  subtree — the numba engine's search MUST check time inside the recursion,
  not only between root moves (research §4 "never run a search that can't be
  interrupted mid-iteration").
- Budget tuned for the 2 s+0.1 s harness clock (8% of remaining); revisit
  with the real 120 s+0.5 s and pondering in 1b-4.
