# Chessathon KB — INDEX & BUILD DECISIONS (synthesis of research)

> All five research docs are in `docs/research/`. This INDEX is the
> operator-level synthesis: what we build, in what order, and why.
> `ORIGINALITY.md` is the law; `BUILD.md` is the running design log.

## 1. The locked build decision (from research 01, 02, 04, 05)

**Classical numba-jitted alpha-beta engine, own board+movegen, tuned hand eval.
A self-trained net is a GATED Day 3-4 sprint behind it (05 B1).**

Why:
- The environment (1 core, no GPU, no network, 50MB, judge-readable source)
  rewards a correct, fast classical engine. 3rd-party engines are banned, so
  the field is amateur engines; top-3 needs ~2200-2400 CCRL-class (04).
- Measured on this box: pure-Python search caps at ~depth 6 (sunfish-class,
  ~1700-2000); **own numba board+movegen is 25-40× faster → depth 8-10**,
  which is the 2200-band enabler (01 §3).
- Eval is the biggest lever below master (05 B2a); Texel-tuned hand eval is
  the highest Elo/hour (02 §6; 05 B3 table).

## 2. Architecture (from 01 §7 + §1-3) — module layout

```
agent.py          get_move(fen, time_left_ms) -> uci; load state at import;
                  wire protocol; own move->uci.  [pure Python glue]
engine/board.py   OWN board + movegen + make/unmake + zobrist  [numba]
engine/search.py  ID + negamax/PVS + aspiration + TT + qsearch +
                  killers/history + null move + LMR + check ext  [numba]
engine/eval.py    tapered eval: material + PST + bishop pair + tempo,
                  pawns (doubled/isolated/backward/passed), mobility,
                  king safety  [numba]
engine/tt.py      packed numpy/numba arrays, ~128-256MB (2^23 entries),
                  depth-preferred 2-4-way buckets  [numba]
engine/time.py    time management (cold path, pure Python)
engine/ponder.py  pondering orchestration (cold path, pure Python)
data/             (later) polyglot book + optional Syzygy subset — data only
```

Order of implementation (01 §1, 02 §6.2, 05 B3):
1. Own numba board + movegen; **perft parity vs python-chess** (correctness gate #1)
2. Alpha-beta + qsearch + TT + ordering → iterative deepening + time mgmt
   (correctness gate #2: perft at depth; no illegal moves; no flags)
3. Hand eval (PST + tempo first) → Texel-tune against own self-play annotations
   (SPRT-gate every change)
4. Self-play harness + book diversity (multiplies every other gain)
5. **Gated sprint (Sep-10 22:00)**: small net trained on Modal, only if it
   beats hand-eval in ≥300-500 SPRT games — else ship classical
6. Ship-quality: book, polish, `make_zip.sh` (only agent.py + engine/ + data/)

## 3. Key facts every build agent must respect (from 01 §3)

- **JIT warmup ~5.8s must run inside the 60s init budget** (call a jitted fn
  at import); set `NUMBA_CACHE_DIR` to `/tmp` scratch (repo is read-only at
  runtime)
- **Never import torch at runtime** (adds ~1s + hundreds of MB; RSS ~430MB
  with just python-chess+numpy+numba; 2GB budget)
- Own movegen is MANDATORY for the 2200 band; python-chess is I/O + oracle
  only (parse FEN once per move; perft cross-check during dev)
- TT in packed arrays, NOT python dicts (dict = 100-200MB/M entries)
- Skip: singular extensions, probcut, mate-distance pruning, SEE-in-eval,
  complex king-attack tables (not worth it at our depth/nps)

## 4. Rules / strategy facts (from 03, 04)

- Zero game-losing bugs > everything (illegal move / crash / flag = instant loss)
- Quiescence non-negotiable; check extension + null move + LMR are the cheap Elo
- 300-ply material adjudication → prefer keeping material over risky mates;
  Syzygy subset (3-4 man ~2-15MB) as shipped data to convert won endgames
- Curated level positions → eval/search robustness on arbitrary positions >
  opening theory; small book still worth ~+50-150
- Pondering ~+50-150 Elo if bug-free (search opponent's expected reply after
  get_move returns, on our core; never overrun own clock)
- Time: adaptive budget ~5-10% remaining/move, hard cap ~45s, never-flag floor

## 5. Compliance (ORIGINALITY.md — never violated)

- All code written in this repo during the event, granular commits
- Classical search default; net ONLY if self-trained (anywhere: local/Modal),
  only OUR `.onnx`/`.pt` weights ship
- Stockfish: local sparring partner + data annotator ONLY, never in repo/zip
- Every source file readable + explainable to a judge; BUILD.md updated as we go

## 6. Research docs quick-map

| Doc | Topic | Key build input |
|---|---|---|
| 01 | Engine architecture playbook | module layout, search framework, measured perf numbers |
| 02 | Eval & tuning + testing | eval terms by ROI, Texel tuning, SPRT harness |
| 03 | Openings, endgames, adjudication | book/TB strategy, draw/repetition handling |
| 04 | Competition landscape | field strength, CCRL bar, schedule, failure modes |
| 05 | Chess models & methodology | NNUE/AlphaZero/Maia analysis, gated-net feasibility, ROI table |
| 06 | Brain-A radical search/eval probes | ranked pre-freeze probe menu (read-only research, Sep 8) |
| 07 | Brain-B meta / wild probes | alternative-approach probe menu + evidence (read-only) |
| 08 | PST phantom decomposition | the inverted pawn-table root cause + ranked PST ablation spec (Sep 9) |
