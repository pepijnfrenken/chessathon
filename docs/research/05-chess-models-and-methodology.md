# 05 — Chess Models & Methodology: What the NN Engines Did, What's Actionable for Us

Status: DONE (2026-09-07). Sources cited inline; read `ORIGINALITY.md` and `BUILD.md`
before writing (acknowledged). Methodology = what they did, described only — NO
implementation code is reproduced here, and copying any engine source remains
forbidden. Priorities: Part B > Part A.

---

## Part A — How the famous NN engines were built

### A1. AlphaZero (DeepMind, 2017/2018)

- **Architecture** (identical for chess/shogi/Go, same as AlphaGo Zero): body =
  one rectified batch-normalized conv layer + **19 residual blocks** (each block:
  2 conv layers + skip connection), all **256 filters, 3x3**; a **policy head**
  (conv → 73-filter conv for chess = 8×8×73 = 4672 move logits, illegal moves
  masked) and a **value head** (1×1 conv → 256 ReLU → tanh → scalar
  win-probability). Note Lc0's "20x256" counts the initial conv as a block; the
  paper itself says 19 residual blocks. Input = stack of binary piece planes over
  the last ~8 plies + planes for castling, repetition, 50-move, color.
  (https://www.science.org/doi/10.1126/science.aar6404, architecture section of
  https://discovery.ucl.ac.uk/id/eprint/10069050/1/alphazero_preprint.pdf)
- **Learning**: pure self-play RL ("tabula rasa" — only game rules as knowledge),
  **800 MCTS simulations per move** during training, move chosen ~ proportional to
  root visit counts (exploration via Dirichlet noise at root; no opening book).
  Loss = MSE on value + cross-entropy on policy, L2-regularized.
- **Scale**: 700k training steps (mini-batches of 4096); chess trained **~9 hours**
  using **5,000 first-gen TPUs for self-play generation + 16 second-gen TPUs for
  training**; ~44M self-play games of chess (Table S3). Search speed ~60k
  positions/sec vs Stockfish's 60M — yet beat Stockfish-8 (2016 TCEC champ, 44
  cores) 155–6 and even at 1/10 of the time, because the NN focuses the tree.
- **What we cannot take**: nothing code-wise, but the **methodology** (policy+value
  heads, self-play loop, temperature/opening randomization for diversity — e.g.
  temp 10 within 1% of best move for first 30 plies to increase game diversity)
  is fair game.

### A2. Leela Chess Zero

- **Pipeline**: distributed self-play — community clients run MCTS (PUCT) with the
  current net, play games with randomized openings, and upload **compressed
  "chunks"** of position records to a central data store ("data lake", GCS). Each
  record = board planes + root **visit-count policy distribution** + game result
  (and later root/best Q, D, move-count targets); format documented at
  https://lczero.org/dev/wiki/training-data-format-versions/.
- **Training**: on dedicated TPU pods (project hardware), nets released every few
  days; RL runs take months; **contrib/supervised runs on the same lake take 1–2
  weeks and usually beat the RL nets** — a real lesson: the *data* matters more
  than the training loop (https://lczero.org/play/networks/basics/).
- **Net sizes**: named `blocks × filters` (10x128 small, 15x192, 20x256, up to
  64x512 "huge"); size ∝ blocks × filters² (24x320 ≈ 15× a 10x128). Odd-numbered
  test runs deliberately use small 10x128 nets for experiments — small nets are a
  standard, workable baseline, not a curiosity.
- **Search integration**: policy = prior for PUCT move selection, value = node
  eval, batched NN inference + NNCache (transposition reuse). This is why the net
  is strong: NN focus + tree averaging, not raw speed
  (https://lczero.org/dev/wiki/technical-explanation-of-leela-chess-zero/).

### A3. Stockfish NNUE (the one that matters most for us)

- **What**: an efficiently-updatable neural network that *replaced the
  hand-crafted eval inside alpha-beta* (not MCTS). Invented for shogi by Yu Nasu
  (2018), ported to SF by Hisayori Noda, merged Aug 2020
  (https://stockfishchess.org/blog/2020/introducing-nnue-evaluation/).
- **Architecture** (SF 12 era): **HalfKP** feature set — input = for each king
  square, the ~10 non-king pieces in (square,piece) form: 64×(64×10+1) = 41,024
  binary features per perspective; first layer maps to 2×256 (the "accumulator"),
  then 32, then 1. First layer ≈ **10.5M params ≈ 20MB** quantized (int16);
  int8 later. Layers: Linear + ClippedReLU, all int8/int16; final scale ∓16 =
  eval in centipawns (https://www.chessprogramming.org/Stockfish_NNUE,
  https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md).
- **Why it's fast**: (1) inputs are ~0.1% sparse — only ~30 active features per
  side; (2) **incremental updates** — a move changes ≤4 features, so the 256-dim
  accumulator is updated by adding/removing a few weight columns, not recomputed;
  (3) int8 SIMD (SSE2/AVX2/AVX-512). Target: millions of evals/sec/thread. NNUE
  *without* those three tricks (e.g. a full forward pass in Python per node) is
  ~100–1000× slower — this is the crux for us.
- **Training data**: supervised — millions of positions at *moderate search depth*
  annotated with the stronger engine's search value (and later WDL from Lc0 data).
  Training is cheap: "small training sets... some high-score networks built by one
  or a few people within a few days"
  (https://www.chessprogramming.org/Stockfish_NNUE). Modern nets train in
  nnue-pytorch (PyTorch) on a single GPU; SF 15/16 nets are HalfKAv2 512x2-32-32,
  ~40-60MB. Later nets partly trained on **billions of Lc0 positions** (SF−Lc0
  data-sharing, 2021).
- **Result**: first NNUE was **~+90 Elo over SF's classical eval despite ~half the
  search speed** (fishtest 60k games, 92.77±2.1), ~+100 more within a year;
  hand-eval was deleted entirely in SF 16. Why it won: it sees piece-king
  *interactions* and non-linear patterns a hand PST can't express, learned from
  vastly more positions than any human tuning effort.

### A4. Maia (human-like, different objective)

- **What**: AlphaZero/Lc0-style policy net trained **on 12M human Lichess games
  per rating bucket** (9 buckets, 1100–1900), objective = *predict the human
  move*, not maximize strength (https://arxiv.org/abs/2006.01855,
  http://www.cs.toronto.edu/~ashton/pubs/maia-kdd2020.pdf).
- **Results**: matches human moves 46–52%+ of the time vs 35–40% for attenuated
  Stockfish; each bucket's model peaks at its own rating → "there is such a thing
  as 1100-rated style". Test hygiene worth copying: discard first 10 plies, drop
  moves made with <30s left.
- **Fair rating estimation**: the authors also use Maia's move-matching accuracy
  to *estimate a human player's rating* — accuracy correlates with the rating
  bucket the model best predicts — a rating methodology, not a strength claim
  (KDD paper §6). Lesson: what a model predicts (human moves vs. engine evals)
  defines what it's good for; don't expect a human-move net to rate *strength*.
- **Lesson for us**: a net trained on engine annotations will inherit engine
  *style/strength*; a net trained on our own self-play learns what we search.
  Not directly reusable except as the strongest known proof that a *policy* head
  is learnable and that supervised move-prediction works — and as a reminder that
  shipping Maia itself is banned.

### A5. Small nets for our compute class

- **Tiny/dense**: a plain `768 → 256 → 1` (or `→128`) net on piece-square binary
  inputs (64×6×2 = 768 features) has ~200–100K params → **<1MB fp32, ~0.5MB
  int8**; fits the 50MB zip trivially. This is the common tutorial/lite baseline.
- **Small NNUE**: HalfKP 256x2-32-32 ≈ **10-20MB** int8/int16; current tiny
  SF-era nets 2-10MB; modern 40-60MB nets fit zip but are pointless (our CPU
  inference cost scales with them).
- **onnxruntime 1.29.0 CPU reality** (estimates): single-thread fp32 forward of
  the dense 768→256→1 ≈ 10–30 µs of compute + 30–100 µs Python/FFI overhead → **~
  10–40k evals/sec**. A full HalfKP forward (41k×256) in onnxruntime is dense =
  ~1–5ms → useless; HalfKP only pays off with **our own incremental accumulator**
  in numpy/numba (update ≈ few hundred MACs, then 512→32→1 dense ≈ 16K MACs → ~5–20
  µs → 50–200k evals/sec). Verdict: a workable net path exists at 10–200k
  evals/sec — but it's 10–100× slower than SF's C++ SIMD millions/sec, so the net
  must earn its keep via eval quality, and our search must not need millions of
  evals.

---

## Part B — Methodology takeaways (what's actionable for OUR build)

### B0. Updated constraint (team-lead, verified 2026-09-07)

**Training location is unconstrained.** The ban covers only what *ships* inside
the submission: weights (`.onnx`) must be ours — trained by us. So: generate +
annotate data locally (Stockfish may annotate OUR data — data is unrestricted,
SF itself never ships), **train on Modal GPUs** (fast, big nets possible), ship
only the resulting `.onnx` + our inference code. Runtime inference remains
1-core/2GB/no-GPU via onnxruntime. This converts training time from a blocker to
a non-issue; the real costs are (1) data generation, (2) CPU integration speed,
(3) engineer hours before Sep 11.

### B1. Can we legally + feasibly train our own small net in ~2-3 days? — YES, with a hard gate

Legal: yes — self-trained weights are explicitly permitted (ORIGINALITY.md:
"any model you ship is one you trained"; training-data unrestricted). No
downloaded nets, ever.

Feasible plan (only start AFTER search core + hand eval exist and pass baseline):

1. **Data (bottleneck #1)** — generate positions cheaply: random self-play of our
   own engine at low depth from diverse openings, plus (cheap) our own games,
   ~10-50 positions/game. Annotate each with SF (outside repo, /tmp) at fixed
   depth 10-14 or fixed nodes: local 6 cores, SF ≈ 20-100ms/pos → **100-300
   pos/s/core → 1M positions in ~1-3h, 5M overnight**. Target = q-value (cp),
   winning side, maybe game result from self-play. 100k positions = weak start;
   **~1M minimum, 3-5M comfortable** — matches SF evidence ("small training
   sets" are enough for decent nets; SF runs used millions-millions+).
2. **Train (bottleneck solved by Modal GPU)** — torch, 2-layer net, L1-loss or
   MSE on cp (or sigmoid WDL). Dense 768→256→1: ~minutes on any GPU. HalfKP
   256x2-32-32 (we write our own sparse trainer; must NOT copy nnue-pytorch
   source — read docs for ideas only): ~1-2h on an L4/A100 for 3-5M positions.
   Validate on held-out set; quantize to int8 (onnxruntime dynamic/static QDQ).
3. **Integrate (bottleneck #2)** — two routes:
   - *Route A (low effort, ~half a day)*: dense net, onnxruntime full forward per
     leaf, 10-40k evals/sec. Acceptable only if our numba search runs
     ≤~15k nps with hand eval; else the net *halves* nps — likely a wash at
     equal strength, still possibly +50-100 Elo from better eval.
   - *Route B (proper, ~1-1.5 days)*: HalfKP with our own incremental accumulator
     in numba, 50-200k evals/sec, size ≤11MB int8. This is the version that
     plausibly *beats* the hand-eval engine outright.
   Then: SPRT self-play A/B, net-vs-hand-eval, diverse openings (section B2d).
4. **Cutover gate (non-negotiable)**: if the net does NOT beat the hand-eval
   baseline in ≥300-500 SPRT self-play games by **Sep 10 22:00**, delete it and
   ship classical. The classical engine is the guaranteed deliverable; the net is
   a sprint upgrade only.

Honest numbers:
- Time: data 1-3h (parallel with day-3 work) + train <2h + integrate 0.5-1.5d +
  SPRT 0.5d ≈ **1.5-2 days of engineer time**, overlapping with search work.
- Expected gain over a Texel-tuned hand eval: **+50 to +150 Elo** at equal node
  budget, possibly +0-50 net after speed loss (SF's own first NNUE was +90 at
  *half* speed against an elite hand eval; for a much weaker hand eval the
  relative gain is likely larger [INFERENCE], but our CPU inference is far slower
  than SF's SIMD, which cuts the other way).
- Risks: integration bugs eating the gate, int8 accuracy loss, eval-scale
  mismatch (cp↔search scores, tempo), search-speed collapse in Route A.
- **Verdict**: worth attempting **only as a days-3-4 sprint behind the classical
  engine, with the Sep-10 gate**. Not worth delaying search/eval/tuning for.

### B2. Lessons that transfer even if we ship NO net

(a) **Eval quality is the biggest lever below master level.** NNUE's +90
    (and SF's year of +100 more) was *strictly* an eval change — same search.
    Our hand eval should be the best-tuned thing we ship.
(b) **Self-play / engine-annotated tuning beats hand-tuning.** Texel/GLS-style
    tuning of PST+weights against our own search annotations is the classical
    analog of NNUE training (see doc 02 — evaluation & tuning). Cheap, legal,
    high ROI.
(c) **Iterate by SPRT self-play, not vibes.** SF/Lc0 both gate every change by
    statistically valid A/B games. We must build the self-play harness early
    (it also generates training data for B1).
(d) **Opening diversity in test games.** AlphaZero's diversity experiments and
    Maia's hygiene both show you learn nothing from repeating one line.
    Self-play tests must start from varied openings (random book positions from
    our own book or lichess-derived positions — shipped book is allowed data).
(e) **Move ordering ≈ policy.** SF's "policy" is iterative deepening + TT move +
    killers + history + MVV-LVA/SEE. A cheap heuristic policy (SEE-capture
    ordering + history) already captures most ordering value; a trained policy
    net is a *marginal* extra. History table is our best move-ordering
    investment; a policy net as root-only oracle is a low-ROI curiosity (root
    order is already dominated by the previous-iteration PV move).

### B3. Time/ROI ranking (given 4 days, engine not built yet)

| Priority | Item | Est. Elo | Est. hours | Elo/hour | Risk |
|---|---|---|---|---|---|
| 0 | Search core (ID/alpha-beta/TT/qsearch/LMR/null) | prerequisite | 16-24h | — | — |
| 1 | Hand eval + PST + Texel/GLS tuning | +150-400 vs material-only | 8-16h | ~15-25 | low |
| 2 | SPRT self-play harness + book diversity | ×every other gain | 3-6h | multiplier | low |
| 3 | Opening book (polyglot, shipped data) | +50-150 | 2-4h | ~25-40 | low |
| 4 | Search refinements (LMR/tune, TT sizing, move ordering, time mgmt) | +50-150 | 8-16h | ~5-10 | med |
| 5 | **Small trained net (B1), GPU-trained, gated** | +0-150 | 12-20h | ~0-8 | **high (cutover gate)** |
| 6 | Endgame TBs | +20-60 | 4-8h | ~5 | med; only 3-4-piece fits 50MB (5-piece ≈1GB) |

Order of operations (concrete): Day 1-2: search core → hand eval → harness;
Day 2-3: tune eval (SPRT every step), ship-quality classical; kick off data
generation in parallel once search exists; Day 3: train net on Modal overnight;
Day 3-4: integrate + SPRT; **Sep 10 22:00 gate**; Day 4: book + polish + zip.
Book and TBs are data-only (≤50MB total budget: book ~10-40MB optionally, net
≤11MB, 4-piece TB ~2MB) — Zip budget is not a reason to skip the net.

---

## Part C — Fairness boundary (read alongside ORIGINALITY.md)

**Allowed**
- Reading anything (papers, blogs, source of other engines) for *ideas*; standard
  algorithms are public knowledge.
- Code **we write in this repo during the event**, from empty files, organically
  committed.
- Self-trained model weights (`.onnx`/`.safetensors`/`.pt`) as shipped data —
  trained **by us**, anywhere (local or cloud GPU): only what ships is bounded.
- Engine-annotated training data (e.g. positions annotated by Stockfish run
  locally, SF kept outside the repo) — for local training only, never shipped.
- Opening books (polyglot) and Syzygy tablebases as shipped data.
- Methodology mimicry: incremental eval updates, HalfKP-style features, MCTS,
  self-play loops, SPRT — concepts, not code.

**Forbidden**
- Copying/pasting/porting/adapting any existing engine's source (SF, Lc0, Maia,
  sunfish, python-chess examples, nnue-pytorch internals) into our files. Read
  for understanding; write fresh.
- Shipping any downloaded/pretrained net, any third-party engine binary, or any
  native compiled extension (image has no compiler; Cython rejected).
- Wrapping/calling any external engine at runtime in the submission.
- Obfuscation; the source must stay explainable to a judge (BUILD.md trail).

**This doc**: descriptions and citations only — no implementation code is copied
or reproduced; any numbers that sound like constants (architectures, sizes,
Elo) are cited claims, and our own engine will use values we choose/tune.

---

## Sources

- AlphaZero: https://www.science.org/doi/10.1126/science.aar6404 ; preprint
  https://discovery.ucl.ac.uk/id/eprint/10069050/1/alphazero_preprint.pdf
- Lc0: https://lczero.org/dev/wiki/technical-explanation-of-leela-chess-zero/ ;
  https://lczero.org/play/networks/basics/ ; training-data formats
  https://lczero.org/dev/wiki/training-data-format-versions/ ;
  https://github.com/LeelaChessZero/lczero-training
- SF NNUE: https://stockfishchess.org/blog/2020/introducing-nnue-evaluation/ ;
  https://www.chessprogramming.org/Stockfish_NNUE ; Yu Nasu's original NNUE paper
  https://github.com/ynasu87/nnue/blob/master/docs/nnue.pdf ;
  nnue-pytorch docs https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
- Maia: https://arxiv.org/abs/2006.01855 ;
  http://www.cs.toronto.edu/~ashton/pubs/maia-kdd2020.pdf
- ORIGINALITY.md (repo law), BUILD.md (design log), official rules
  https://aichessathon.com/docs (verified 2026-09-07).