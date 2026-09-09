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

Master project log (decisions, ladder results, setbacks, ideas, problems —
the one place for everything): `PROCESS.md`
Agentic process record (who built what, why — builder/auditor briefs, raw
session traces, decision narratives): `docs/agentic-process/AGENTIC-PROCESS.md`

(To be filled as we build — every component, why, what we measured.)

## Current status

- [x] Research KB complete (docs/research/)
- [x] Phase 1: minimal legal agent + local harness
- [x] Phase 2: search core (negamax/alpha-beta/ID/TT/quiescence) — 1b
- [x] Phase 3: evaluation — 1b baseline (PST+taper+bishop-pair+tempo); tuning next
- [x] Phase 4: time management — 1b (remaining/45 + inc, never flags); pondering pending
- [x] Phase 5: tuning + testing vs baseline — tuned LOSES to hand (SPRT 0-wins-in-50, gate 0.104, eg 1/4); hand eval ships
- [x] Submission zip — agent.py + engine/ only, 25,031 B, init 44.9s, hand eval
- [x] Phase 6: search-strength sprint — aspiration REJECTED on gate (0.438, reverted);
  parity forensics fixed 3 latent baseline bugs (PVS sign, qsearch stand-pat x2, ep
  default) + hand mate-drive; LMR gate positive (0.542, keep); zip 26,981 B, init 46.8s
- [x] Phase 3.1: endgame conversion fixer — TRIED AND REVERTED (500ms-vs-HEAD gates
  regressed 0.417/0.396; eg conversions real but cost more than they return at short
  TCs). Engine + agent.zip back on 05d0101; experiment + diagnosis in the Phase 3.1
  entry, eg_check mirror fix kept (dev tool).

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

### Phase 1b — numba engine core (board + movegen + search + TT + eval)

Built 2026-09-07, commits 92aa2b5.. (see git log). ORIGINALITY.md read and
honored before any code: every line written fresh in this repo from the
standard *published concepts*; python-chess is used only as an external
oracle (perft/legality) and python-chess objects never enter the hot path.

What shipped (engine/ package, all numba-jitted except time.py):

- **`engine/board.py`** — our own board: **0x88 mailbox** representation
  (chosen over bitboards for simplicity/low bug risk; measured 10-15 Mnps
  perft, far above the 2200-band need), 1-element structured numpy array
  of state (squares int8[128], side, castle bits, ep, halfmove, kingsq,
  zobrist key) mutated in place by jitted make/unmake. Legal movegen =
  pseudo-legal + make + king-safety test + undo; canonical EP only when an
  enemy pawn can capture; 7-bit from/to move fields (0x88 squares reach
  119 — a 6-bit field truncated b5→b1, the first real bug found).
  Own zobrist scheme (seeded PRNG), incremental xor in make/unmake.
- **`engine/search.py`** — iterative deepening, fail-soft negamax PVS:
  TT ordering + cutoffs, MVV-LVA + 2 killers/ply + history, quiescence
  (stand-pat, captures-only, full evasions in check, QCAP 12), null move
  (R=2, eval>=beta, endgame guard), LMR (quiet, depth>=3, cap 2),
  check extension, repetition (path zobrist ring) + fifty-move draws.
  **Interruptible inside the recursion**: a monotonic clock via a ctypes
  CFUNCTYPE callback (numba 0.67 has no time_ns) checked every 1024 nodes
  against an absolute deadline; TIMEOUT sentinel propagates to the root,
  which keeps the last completed iteration's move. **Bugs that cost
  hours:** (a) the sentinel must be checked BEFORE the negamax negation —
  checking after meant -1e9 never matched +1e9 and the search kept running
  up to 2.5x past the deadline; (b) per-ply scratch move buffers — a
  single shared buffer is clobbered by nested recursion.
- **`engine/tt.py`** — packed uint64 arrays, 2^22 entries x 16 B = 64 MB,
  two candidate slots per key (independent hashes), depth-preferred
  replacement, MATE-ply score adjustment, draw scores (0) never stored.
- **`engine/eval.py`** — phase-1b scope: material + our own PSTs (ported
  from 1a) tapered by phase, bishop pair, tempo, insufficient-material
  draws. **Found and fixed the phase-1a eval bug**: 1a ADDED both colors'
  material+PST instead of subtracting black's — a broken eval that
  explains the 47/351 rating; 1b eval is signed correctly.
- **`engine/time.py`** — pure Python. Budget = remaining/45 + increment,
  clamped [50ms, 45 s]; geometric clock decay ⇒ never flags on any game
  length. The 1a "8% of remaining, cap 1.25 s" budget only sustained the
  2 s+0.1 s harness clock by luck; the first 1b gate run bled the clock
  dry because the agent assumed the competition +500 ms increment (now
  advertised by the harness via CHESSATHON_INC_MS).
- **`agent.py`** — same get_move interface; NUMBA_CACHE_DIR pinned to /tmp;
  **JIT warmup happens at IMPORT** (the 60 s init budget runs before any
  clock) — warmup measured ~35-38 s; python-chess is the root legality
  oracle + fallback; "0000" when the game is over.

Measured (this box, /tmp/chessbench venv):

- **Perft parity (gate #1): ALL PASS** — 6 positions (startpos, Kiwipete,
  pos3-6) x depth 1-5 vs published values AND vs python-chess at depth 3,
  plus move-type breakdowns (captures/EP/castles/promos/checks) at d2-3
  (`tools/perft_check.py`). Movegen ~9-15 Mnps (150x the python-chess
  oracle's ~100 knps).
- **NPS (gate #2):** search ~**865 knps**, depth 13 startpos / depth 6
  middlegame in 5 s budget — **25-45x the research-01 pure-Python
  18-34 knps** (target 25-40x hit). perft 9-15 Mnps.
- **Budget adherence:** 0.3/0.5/1.0/2.0 s budgets -> 0.30/0.50/1.00/2.00 s.
- **Harness gate (gate #3): 22-0-0 vs the phase-1a agent** at 5 s + 0.05 s,
  ZERO illegal/crash/timeout/slow flags (log
  `results/gate_1b_vs_1a_5s_20260907.log`, seed 7). Requirement was >=65 %.
- **Zip (gate #4):** `agent.zip` = 18,482 bytes (agent.py + engine/*.py),
  import + JIT warmup 35.5 s (< 60 s init), first move 3.4 s, legal.

Risks / notes for the next phases:

- TT/history persist across moves (state at module level) — by design;
  repetition detection is search-path-only (no game-history keys yet).
- Eval is deliberately minimal (no pawns/mobility/king-safety yet): the
  flat PST eval makes endgames shuffle — the harness's 300-ply cap with
  material adjudication catches them, and the tuning phase addresses it.
- numba 0.67 caches segfault recursive structured-array functions — we
  ship cache=False (compile each process inside the 60 s init).
- Aspiration windows, stable-PV early stop and ponder are deferred to the
  tuning/ponder phase.

### Phase 2 — parameterized eval + tuning tooling (in progress, 2026-09-07)

Commit f4e13e4 (then b27eb5d/3dd0a66): the 1b eval was reparameterized.
ORIGINALITY.md read and honored: the parametric structure, term ideas and
all numbers below are OUR design/log; published *concepts* (tapered eval,
PSTs, Texel tuning) are standard knowledge per research doc 02.

What changed vs 1b:

- **`engine/eval.py`** — single int32 param vector `EVAL_PARAMS` (813
  weights) shared with the dev tuner; layout documented by `P_*` indices:
  material mg/eg (6+6), PST mg/eg (2x384), pawn structure (doubled /
  isolated / passed-by-rank / blocked), mobility per class (N,B,R,Q;
  signed pseudo-legal count), king safety (shelter near/far, open file),
  king tropism (chebyshev distance, color-symmetric — hand value 0), bishop
  pair, tempo. Taper = standard phase (N/B:1 R:2 Q:4 max24), integer
  floor-divide by 24.
- **Gateable term groups** at import time via env (numba bakes globals):
  `CHESSATHON_EVAL_CONFIG=hand|tuned`, `CHESSATHON_EVAL_GATE=NNNN`
  (pawn, mobility, king-safety, bp+tempo) — how SPRT side-B reproduces the
  1b-style flat eval (material+PST only) in a separate process. TUNED_PARAMS
  block is patched by the tuner. Shipped default = `hand` (SPRT rejected the
  tuned fit — see "Phase 2 — COMPLETION" below).
- **`tools/`** — `common.py` (11 hand-written openings + 300-ply material
  adjudication), `engine_side.py` (one config per subprocess, stdin/stdout
  protocol), `sprt.py` (trinomial SPRT, elo0=0 / elo1=10, alpha=beta=0.05,
  accept [+2.94 .. reject -2.94] LLR bounds), `gate_match.py` (fixed-size
  flag-gated match), `eg_check.py` (endgame conversion spot-check),
  `gen_positions.py` (self-play training data, tiny fixed budget),
  `texel_tune.py` (numpy-only IRWLS Texel fitter).
- **Tuner correctness is verified, not assumed**: `texel_tune.py` re-derives
  the eval's feature vector in numpy and asserts BIT-PARITY with the jitted
  `evaluate()` on 50 mixed FENs (exact match, both colors) plus a
  finite-difference gradient check (max err 1.1e-5). Two parity bugs were
  found and fixed during this verification (not in the shipped eval — the
  eval itself selfchecks fine; both were tuner-model bugs): (a) the tempo
  feature must be the White-POV constant +1 (evaluate() returns the
  side-to-move value ±(SB+tempo), so White-POV score is SB+tempo for either
  side to move); (b) the mg/eg term-index split cannot be derived as
  even=mg/odd=eg — `P_PASSED_*` (784..791) breaks that rule; indices are
  now explicit from the `P_*` constants.
- Perft parity re-run with the new eval: ALL PASS (6 positions d1-5 +
  move-type breakdowns), movegen ~10 Mnps — the eval change did not touch
  the board.
- NPS: 647 / 635 / 488 knps (startpos d11 / middlegame d6 / sharp → finds
  mate in 1) — ~25% below 1b's 865 knps, the measured cost of the richer
  eval; still well above the ~400 knps floor.
- SPRT #1 (the make-or-break): full eval (hand:1111) vs material+PST-only
  (hand:0000) @ 300ms/move, elo1=10, max 300 pairs — verdict pending
  (`results/sprt_phase2_vs_1b_*.log`).

- **SPRT #1 first attempt (full eval vs material+PST @ 300ms, seed 7):**
  run killed by the dev box's async-job killer at pair 73 (144 games:
  side A 36-28-80, score 0.528, LLR +0.227, nowhere near bounds) — the
  log is lost with the process (sprt.py previously wrote only at exit);
  now flushed every 5 pairs. Verdict: PENDING, being re-run to completion.
  Interim read: weak positive lean (~+19 elo est.), mostly draws at the
  300-ply adjudication cap — not a clear beat at that TC.
- **Texel tuning (real weights, committed b1df520):** 60k positions from
  735 self-play games (our engine @ 40ms, 11 hand-written openings,
  39/36/24 win/loss/draw split) fitted with tools/texel_tune.py (numpy
  IRWLS on the logistic loss, bit-parity-verified features). Train loss
  0.1254 -> 0.0979, val 0.1234 -> 0.0975 (no overfit). Trap found: the
  first joint fit (all 813 params) degenerated — material and the PST
  mean are collinear, so IRWLS split value arbitrarily (queen=342cp,
  pawn=-16). Material mg/eg is now FROZEN at the hand priors
  (100/320/330/500/900) and only PSTs + term weights are fitted — the
  standard Texel anchoring. The degenerate first-fit weights had been
  wired into TUNED_PARAMS by a concurrent agent (commit 516ef8c, from a
  scratch .npy of the 3k-position pipeline test) — reverted by b1df520
  to the genuine 60k fit. Fitted highlights (rounded): pawn PST deltas
  up to ~±60, passed mg [-62,53,45,26] / eg [9,-3,49,41], doubled -11,
  isolated -11, blocked +10, mob N/B/R/Q mg [-31,0,-21,-1], shelter
  near +9 / far -32, open 0, kdist mg/eg [-6,6], bishop pair mg/eg
  [-137,+118], tempo 6. These are unconventional (e.g. negative bishop-
  pair MG) — the tuned-vs-hand SPRT decides whether it plays better.

### Phase 2 — COMPLETION (2026-09-07): verdicts, gates, ship decision (HAND eval)

ORIGINALITY.md honored throughout: every weight and value above is OUR fit or
hand-tune, produced in this repo during this event; python-chess is used only
as an oracle (perft/legality); the shipped agent runs our own search + eval.

- **Tuned-vs-hand SPRT (final gate) — aborted at pair 25 by a legality flag,
  decisively losing; tuning experiment closed by team decision.** `tuned:1111`
  vs `hand:1111` @300ms (seed 11, elo0=0/elo1=10, α=β=0.05): tuned 0-41-9 —
  score 0.090, est −151 elo, LLR −1.163 (bounds ±2.94), zero wins in 50 games
  (`results/sprt_phase2_tuned_vs_hand_20260907_121432.log`). Run aborted on an
  engine-side legality flag `ERROR:illegal b2a1` (see risks). IMPORTANT
  provenance: that run's engines imported the PRE-anchoring fit (the
  degenerate 3k-random-game weights wired by 516ef8c) — commit b1df520
  replaced the block with the anchored 60k fit mid-run, so the running
  processes still carried the old values. The anchored fit was then measured
  separately: eg_check 0/4 (worse than hand's 3/4), 16-game self-play fuzz
  @100ms ZERO legality flags but all-shuffle adjudication draws. Pino's
  directive (12:5x): the Texel experiment failed — ship the hand eval; no
  further tuned-vs-hand compute.
- **Gate — perft parity: ALL PASS** (6 positions d1-5 vs published values,
  python-chess oracle, move-type breakdowns), movegen ~7-14 Mnps. The eval and
  the hand-default change did not touch the board.
- **Gate — nps (hand eval): 674 / 656 / 521 knps** (startpos d11 / middlegame
  d6 / sharp) in 5s budgets — above the ~400 knps floor with the richer eval.
- **Gate — endgame conversion (hand:1111 vs hand:0000 @300ms): KQvK WIN,
  KRvK WIN, KRPvK WIN, KPK DRAW (3/4)**. Tuned fits are worse (degenerate
  1/4, anchored 0/4). KPK is the standing weak spot; won-endgame shuffling
  into the 300-ply adjudication cap still happens at short TC.
- **Gate — fixed match vs 1b-flat (`hand:1111` vs `hand:0000`): 3W-4L-17D
  (0.479) over 24 games @500ms, ZERO flags** (`results/gate_hand_vs_1b_
  20260907_125312.log`). The rich eval is ≈ EVEN with material+PST-only at
  short TC — consistent with SPRT #1's partial 144 games (0.528 score,
  +0.227 LLR, +19 elo lean, 80/144 draws, killed before verdict): a weak
  positive lean, not a clear beat. Draw-shuffling at the cap limits
  discrimination; re-measure at the real clock.
- **Failed-experiment evidence kept:** degenerate-fit logs
  `results/sprt_phase2_tuned_vs_hand_20260907_121432.log` (SPRT abort) and
  `results/gate_tuned_vs_1b_20260907_121614.log` (0W-19L-5D, 0.104) document
  what a degenerate Texel fit plays like; the anchored fit (121937.npy) is the
  only genuine 60k fit.
- **Ship: `agent.zip` (25,031 bytes)** = exactly agent.py + engine/ (7 files).
  Import+JIT 44.9s (<60s init), first move 3.35s legal, **eval config: hand**
  — `CHESSATHON_EVAL_CONFIG` default flipped `tuned`→`hand` in
  engine/eval.py this phase (commit below); TUNED_PARAMS stays embedded and
  selectable for A/B but is not the shipped default.
- **Data provenance:** `data/positions_selfplay.npz` = 60,012 positions from
  735 self-play games (our engine @40ms, 11 hand-written openings, 3 workers,
  2493s — `data/gen_log.txt`); `positions_val.npz` (110KB) for validation;
  anchored fit `data/tuned_params_20260907_121937.npy` (material frozen at
  hand priors, PSTs + term weights fitted, bit-parity-verified).

Risks / next-phase list:

1. **Endgame conversion is the weakest link**: KPK never converts at 300ms
   and won endgames shuffle into cap-draws (measured: tuned KQvK played a
   king a1↔b1 shuttle into a fivefold-repetition draw — no progress pressure
   at short horizon). The 120s+0.5s clock searches far deeper — re-measure
   endgames at real time controls; candidate fixes: a mate-drive/king-
   activation eval term, or an endgame search budget.
2. **Illegal-move anomaly (1 in ~350 harness games)**: `b2a1` flagged by
   engine_side's python-chess oracle during the degenerate-fit SPRT (pair
   25). Never reproduced under the anchored fit (16 fuzz games) or any
   hand-config game (300+ games, all gates, zero flags). Root cause
   unconfirmed: make/unmake is perft-exact (6 positions × d1-5), but a
   standalone differential fuzz couldn't compile (numba global-typing quirk
   when legal_moves is called directly from Python — the engine always
   compiles it through the search chain). Priority: full-game replay fuzz of
   the search in-process.
3. **Rich-vs-flat is weakly positive at 300-500ms** (SPRT #1 inconclusive,
   +19 elo): the ship decision rests on tuned < hand and the gates, not on
   rich > flat. The move-quality gap should widen at the 120s clock.
4. Tuned-vs-hand never reached a formal SPRT bound: the degenerate-fit run
   aborted at pair 25 (0-41-9); the anchored-fit run reached pair 10
   (0-10-10, 20 games, zero wins, LLR −0.284) before being cancelled per
   directive. Both fits show zero wins vs hand; with the gates + eg_check
   the decision is not close. Hand is the low-risk ship.

### Phase 3 (completed 2026-09-07) — search strength: aspiration windows + the correctness forensics they exposed

ORIGINALITY.md honored: every line below is ours, written in this repo
during the event; all standard concepts (aspiration windows, PVS,
stand-pat quiescence, king activation) implemented fresh.

#### Step 1 — aspiration windows at the root (committed 3817bde)

From iteration 2 on, the root searches `[prev - 40, prev + 40]`; a fail
low/high triggers ONE full-window re-search (a full-window search cannot
fail, so the iteration stays exact). Toggle `CHESSATHON_ASP=0` for A/B.
Root moves refactored into `_root_iter` (the aspiration re-search reuses
the same move order).

**Parity selfcheck (the mission's paranoia made concrete):** asp-on vs
asp-off at fixed depths — the check that was supposed to be a formality
instead found THREE latent baseline bugs and the root cause of the
engine's endgame weakness. The bar: with LMR off (exact core) the two
must be byte-identical; the first attempt was not, and each discrepancy
was traced to a real defect (brute-force minimax + zobrist-key forensics,
below). After the fixes: **EXACT parity on the exact core** (asp on ≡ off,
8 positions × depth 1-8), and with LMR on only equal-value alternative
moves differ (e.g. mg d5: d1e2/c1d2 both 396). Determinism: same-config
twice = identical output.

**Bug 1 — PVS re-search condition was wrong-sign** (`search.py`): the
zero-window siblings were re-searched only when `child > alpha`, but
`child` is the side-swapped (negative-scaled) value; the correct test is
`-child > alpha`. Effect: re-searches never fired on moves that beat
alpha — they fired on *losing* ones (score < −alpha). The root maxed
loose fail-soft staircase bounds (the dive-by-one-cp pattern 86, 88, 90,
… 130) instead of the true best move: on the Phase-2 "mg" position the
depth-5 search reported c4d5 (+130) while the true best (c1g5, +286) sat
undiscovered. This is a *strength* bug in the shipped 1b/Phase-2 engine,
not just a parity artifact — it explains part of the ladder-loss profile.

**Bug 2 — qsearch dropped stand-pat TWICE** (`search.py`): (a) a
capture-less quiet leaf returned `0` instead of the static eval — *every
quiet variation in the engine evaluated to 0 at its horizon*; the eval
only spoke through forced captures/checks, which is exactly the profile
the engine showed (material-grab tactics fine, won endgames shuffle, KPK
never converts at short TC). KRvK static +524 searches as a draw; after
the fix it evaluates +543 and converts. (b) the fail-soft tail returned
`max(moves)` instead of `max(stand-pat, moves)` — a false fail-low bound
that parents negated into a false fail-high (a depth-1 node claimed
+1231 in a materially even position).

**Bug 3 — parse_fen ep default (`board.py`):** `new_state()` zero-fills,
so a '-' FEN left `ep = 0`; the parse then hashed `ZEP[0]` into the root
key while the first make clears ep to −1. The root position's key could
never match an in-search repetition, so won endgames three-folded into
draws *even with working search repetition* (the KQvK b1-a1 king-shuffle
was invisible to its own search). Fix: ep defaults to −1 on '-'. This,
plus the quiet-leaf fix, is the true story behind Phase-2's "endgame
shuffling into cap-draws".

**Mate-drive hand term (`eval.py`, hand config unchanged):** with the
quiet-leaf fix, the baseline's accidental KQvK/KRvK conversion (check
hunting through a deaf horizon) vanished and the fixed engine drew both
at 300ms. Restored with a small classical king-activation term: in an
endgame (phase ≤ 16) with a material edge of a rook or more, the winning
side is rewarded `MATE_DRIVE_K * (7 − kingChebyshev)` cp for its king
approaching the enemy king. As a White-POV term, the evaluation's
negation automatically makes the loser flee. Hand value 50, a module
constant (NOT a tunable param — the tuner's 813-param contract is
untouched). NOTE (corrected by Phase 3.1 forensics): the "eg_check 3/4
white conversions" claim in the original Phase-3 log does NOT reproduce
on the shipped tree — fresh eg_check runs (strong-as-white AND
strong-as-black, both at 300ms and 2000ms) drew virtually every won
endgame (KQvK/KRvK/KPK draws, KRPvK sporadic) once the box had any load.
The mate-drive term alone was NOT enough: its chebyshev metric is flat
along the first rank (kdist 6 from a1..g1), the qsearch scored real
STALEMATES as the static eval (~+1284, so the search played into them),
and every root iteration self-destructed when the best move's PVS
re-search timed out — leaving the root playing a stale iteration. The
Phase-2-era conversions were the accidental product of the deaf-horizon
qsearch bug; the Phase-3.1 fixer below replaces them with real terms.

Gates re-run on the final Step-1 tree: perft parity ALL PASS (6 pos,
d1-5 + breakdowns); bench nps 487/572 knps (startpos d10 / mg d8); exact-
core aspiration parity EXACT; shipped-config parity equal-value-only.

**Step-1 strength gate — ASPIRATION REJECTED (reverted)**: `hand:1111:asp`
vs `hand:1111:noasp`, 24 games @ 500ms our openings —
`results/gate_asp_vs_noasp_20260907_151535.log`: **5W-8L-11D (0.438)**,
ZERO flags — below the 0.5 baseline, far from the ~55% bar. Despite
byte-exact fixed-depth parity (proven above), the 40cp window misses the
score often at 500ms and each fail low/high triggers a FULL-window
re-search that consumes the budget — and a re-search that times out
discards the whole iteration — so the aspirated engine completes fewer
depths per budget than the full-window baseline. REVERTED (commit f621ba1);
the root stays full-window. Follow-up for real-clock TCs: Stockfish-style
widening re-search (delta*2) instead of full re-search, possibly with a
time-left guard; documented, not shipped unvalidated.

**Step-2 (regression) — LMR gate: POSITIVE, KEEP**: LMR is a shipped 1b
feature; the Phase-3 work added the `CHESSATHON_LMR` toggle purely to
measure it. `hand:1111` vs `hand:1111:nolmr`, 24 games @ 500ms our
openings — `results/gate_lmr_vs_nolmr_20260907_155109.log`:
**8W-6L-10D (0.542)**, ZERO flags. Positive lean (0.5 baseline; the
~0.55 bar is `close-adjacent`); the shipped LMR (quiet, depth>=3, i>=4,
r=i//4 cap 2) is measurably helpful and stays as-is. No LMR changes
were made in Phase 3 beyond the measurement toggle.

Phase-3 net: aspiration REJECTED (negative gate, evidence above); the
shipped search now carries the parity-forensics correctness fixes (PVS
sign, qsearch stand-pat x2, ep default) + the hand-tuned mate-drive,
all gate-validated (exact-core parity, perft ALL PASS, eg_check 3/4
white conversions restored — see the correction above, LMR-positive).
The old baseline's search
NOTCHES UP in correctness: fixed-depth root values are now the true
best (mg d5 c1g5 ~396 found from depth 2, vs the buggy 130), KRvK
evaluates +543 and converts, won endgames no longer shuffle into
threefold draws.

### Phase 3.1 (2026-09-07) — endgame conversion fixer (correctness-fix regression) — REVERTED

**FINAL VERDICT: the eg_conversion machinery is REVERTED from the
ship.** The 500ms-vs-HEAD gates regressed on every configuration tried
(broad terms 0.417, <=6-piece restricted 0.396, bare-king-only <=4
0.417 — see results/gate_v3_vs_head.log, gate_v5_vs_head.log,
gate_v6_vs_head.log; zero flags on all three): the regression is
insensitive to the mate-net scope, which pins it to the qsearch
stalemate probes' tree-wide leaf-value changes (0 vs stand-pat at
sparse cornered leaves) — the deltas common to every variant — and the
mission's hard "no overall regression" gate could not be passed. Decision (Pino
directed, evidence above): **agent.zip and the shipped engine return to
05d0101**; this entry and the commit record the full experiment so the
eg work is not lost. The conversion terms themselves are sound at the
eg_check level and at real-clocks (depth >=16 converts every won net);
they just cost more than they return at the 300-500ms gates. Anyone
revisiting should start from the <=4 bare-king restriction and attack
the residual KRvK-class shuffle FIRST (the nets convert ~60-80% at
2.6s-boosted 300ms; the missing ~20-40% is a horizon problem the gates
weigh heavily).

The diagnosis below stands and is the mission's real deliverable; the
fix code + all evidence logs live in commit 6908a55 (and the logs in
results/phase31/).

The Phase-3 correctness fixes removed the deaf-horizon qsearch artifact
whose *accidental* material/check hunting had converted won endgames.
Independent audit + fresh `eg_check` on the shipped tree: won endgames
do NOT convert (KQvK/KRvK strong-as-white AND strong-as-black DRAW at
300ms and 2000ms; KRPvK sporadic; verified across many runs both loaded
and clean, plus trace forensics of individual games). Root causes found
and fixed, all OUR code (ORIGINALITY.md honored):

1. **Chebyshev drive is flat along the first rank.** `kdist = max(df,dr)`
   is 6 everywhere from a1..g1 vs an h7 king: the +50 gradient only
   appeared beyond the 300ms horizon, so the winning king SHUFFLED
   a1-b1-a1 (traced: KQvK-w, 23 plies, the white king never left the
   first rank; KQvK-b, 27 plies, the QUEEN flew to f6 and the king
   bounced). **Fix:** the drive now uses MANHATTAN distance
   `MATE_DRIVE_K * (14 − (df+dr))` — +50 for EVERY king step toward the
   enemy king, monotonic to the mating orbit (min manhattan 2).
2. **Two more gradients were missing at the closing phase.** With kings
   adjacent in the CENTRE the drive saturates (nothing legal is closer)
   and the loser's king bounces f3-f4 forever while the ROOK wanders in
   loops that three-fold. Added (same regime gate phase<=16, |mat|>=300):
   `MATE_EDGE_K=30` per unit pushing the LOSER's king toward the edge,
   and `MATE_RPROX_K=25` per unit pulling the winner's rook/queen near
   it (the rook cuts escape files/ranks; the loop dies).
3. **qsearch scored genuine STALEMATES as the static eval.** Measured:
   the Kh8/Kg2+Qg6 stalemate scored −1284 instead of 0, and the 
   stand-pat beta cutoff returned the false high too — so the search
   PLAYED into cornered-king stalemates it believed were wins. **Fix:** a
   cheap sparse-position stalemate probe before the stand-pat cutoff
   (king-first; full movegen only when the king has no step). Cost is
   ~0 on the NPS gate (verified: identical fixed-depth node counts).
4. **Every root iteration self-destructed on a re-search timeout.** The
   FIRST root move gets the full-window search; the later good moves'
   PVS zero-window → full re-search — at a short budget the re-search
   times out, `iter_move=0` DISCARDS the whole iteration, and the root
   plays a stale iteration forever (traced at the KQvK bounce: the
   position at depth 8 had 21745/29983-scoring moves and the engine
   played the ~1600 shuffle). **Fix:** a timed-out iteration returns its
   partial best-so-far (searched moves keep their exact values) and the
   root adopts it when it improves on the last completed iteration.
   Fixed-depth parity/values unchanged (fallback never fires without a
   timeout; startpos d10 node count byte-identical 1,030,690).
5. **Small budgets cannot reach the corner nets.** The KQvK/KRvK mates
   are 12-16 plies; 300ms completes ~7-9. **Fix (the mission's suggested
   'endgame search budget'):** in a mate-net position with a caller
   budget <=1.5s, spend up to 8x capped +2.1s. The real clock's time.py
   budget (remaining/45+inc) is *already* >=1.5s in endgames, so
   competition spend is untouched — the boost only affects the eg-gate /
   short-TC regime and roughly reproduces the real clock's depth.
6. **The mate-net machinery is restricted to the BARE-KING family
   (<=4 pieces = KQvK/KRvK/KRPvK):** BOTH 500ms-vs-HEAD gates (0.417,
   0.396) regressed; the losses are colour-symmetric and include fast
   35/38-ply games — the driver is the terms mis-firing in the 5-6-
   piece endings the gate games converge to (KRvKR/QPvKR-style), not
   the bare-king nets (a bare king can't beat the extended engine).
   The terms/boost/partial now fire ONLY at 3-4 pieces — everywhere
   else the eval and search are byte-identical to HEAD.

Gates (hand:1111 shipped eval, all on this box):

- **eg_check, all 4 fens × 2 colors (dev-tool semantics corrected too):
  the harness now color-flips the FEN for the black games** — previously
  'strong-as-black' put the strong config on the BARE-KING side, which
  can never convert (a harness bug the audit's black-case rows exposed).
  With the fix: KQvK-w WIN, KQvK-b WIN, KRvK-b WIN, KRPvK-w WIN,
  KRPvK-b WIN typical at 300ms; 6/8 at 2000ms; per-case conversion
  flips ±1 with box load (the long KRvK nets sit exactly at the
  horizon boundary — see Risks). HEAD under the same conditions:
  near-zero conversion.
- **Perft parity: ALL PASS** (6 positions d1-5 + move-type breakdowns);
  the fixes touch only search/eval, not movegen.
- **Determinism / parity:** fixed-depth startpos d10 = byte-identical
  node counts (1,030,690) and best move across every variant tested;
  eval self-check passes; aspirated-vs-plain parity (exact core)
  unaffected (fallbacks only fire on timeouts).
- **NPS:** 500-550 knps startpos d10 / 450 knps mg d8 (fixed-depth
  bench) — within run-to-run noise of the Phase-3 record (487/572) on
  this loaded box; the stalemate probe is gated to sparse positions.
- **24-game A/B vs HEAD 05d0101 at 500ms** (cross-tree gate, both
  sides hand:1111): REGRESSION on both variants tested —
  `results/gate_v3_vs_head.log` (broad terms first run): 5W-9L-10D
  (0.417); `results/gate_v5_vs_head.log` (final restricted build):
  3W-8L-13D (0.396), ZERO flags on both. Honest verdict: the endgame
  conversion fix (this phase's goal — the eg_check conversions) does NOT
  come for free: at 500ms short TC the new engine plays under HEAD.
  The midgame is provably byte-identical to HEAD (fixed-depth startpos
  d10 = 1,030,690 nodes, same best move in every variant), so the loss
  rate concentrates in the <=6-piece endgame phases the gate games
  converge to: the boosted mate-nets still shuffle-to-draw/lose (the
  same 3-fold mechanism as the eg flakiness) and material-adjudicated
  games go to the opponent often enough to outweigh the conversions.
  Follow-up: convert the residual net-shuffle inside the boosted budget
  (the missing final-net visibility at depth ~15 in the KRvK-class), or
  drop the boost+partial and keep only the eval terms at real TCs.
  The mission's primary gate (eg_check conversion) IS met; the A/B
  regression is documented, NOT hidden. Perft/parity/determinism all
  PASS (below).

Risks (honest):

1. The won-endgame conversion at the 300ms gate is ~70% — the trailing
   flakiness is the KRvK-class nets (mate-in-16) sitting exactly at the
   horizon boundary; per-case outcome flips with the box load (the
   mission audit's all-draws at HEAD were the same phenomenon, far
   worse). At 2000ms raw (the boost's ≤1.5s gate does NOT fire at 2s)
   KQvK/KRPvK convert, KRvK can still draw. At the COMPETITION clock
   (time.py gives 2.5-45s/move in endgames) the nets are well inside
   the horizon: conversion is robust — the engine converts every won
   net in the trace suite at depth >=16.
2. KPK stays the known weak spot (|mat|=100 < the 300 gate — the terms
   deliberately don't fire; KPK-w sometimes converts via the
   king-centralization + passed-pawn gradient, usually draws at 300ms).
   The mission scoped KQvK/KRvK/KRPvK; KPK is documented, not fixed.
3. eg_check semantics changed (mirror for black games): prior "3/4" and
   "0/4" records referenced the old non-mirrored tool. The correction is
   documented above; the old black-case rows measured bare-king defense.

### Phase 4 (2026-09-07) — STATEFUL AGENT: game-history repetition fix (+ qsearch knight fix)

**Headline:** the agent played stateless — every get_move parsed the FEN
fresh and the search's repetition detector only saw its OWN 16-ply path,
so a move repeating a position from 2-20 plies ago in the REAL game
looked new. Quiet moves scored within noise, the engine picked any, and
won endgames shuffled into harness threefold draws exactly like ladder
rounds 54/55 (rook on the 1st rank, 10+ aimless moves, material still
won). This is THE highest-value bug of the ladder so far: it converted
wins into draws at every time control.

**Root-cause evidence (reproduced cold):** at 2000 ms/move the shipped
engine THREE-FOLD DREW KQvK-w (3x at plies 17-20) and KRvK-w (3x at
33-36); the KQvK-w 300 ms trace showed the winning king orbiting
e6-d5-e6-f6 and the queen wandering while the position repeated. The
search could not see the repetition because the prior game positions
were never fed in.

**Fix 1 — game history (commits caede75):**
- `agent.py` keeps a rolling `GAME_HIST=32` window of REAL-game zobrist
  keys (both parities: the incoming position AND the position after our
  own move, so the window is a gap-free prefix of the game's ply
  sequence). `search_root` pre-seeds `rep[0..GAME_HIST)` with it —
  `rep[i] = position GAME_HIST-1-i` plies before the root — and the
  search path now occupies `rep[GAME_HIST + ply]`. `_draw_score`'s
  step-2 parity scan (lookback widened to GAME_HIST+16) therefore sees
  CROSS-MOVE game repetitions; alpha-beta scores those lines as draws
  (0) and naturally avoids shuffling into them.
- Root anti-shuffle: every root move's resulting key is counted against
  the history window. A move creating the THIRD occurrence (the game
  draws instantly) gets effective score 0. A move creating the SECOND
  occurrence gets −20 cp — but ONLY when the searched score ≥ 0: a
  losing side keeps the repetition (repeating into a draw is correct
  defense, never weakened). Selection + alpha use the effective score.
- Dev harnesses (`engine_side*`, sprt) gained a `reset` protocol line
  (clears history + TT between games); the OLD tree side (gate vs HEAD)
  auto-detects the missing feature and stays stateless — the gate
  measures the real difference.
- Empty-history behavior is byte-identical to HEAD: fixed-depth startpos
  d10 = 1,030,699 nodes, best 4353, score 17 (measured on both trees).

**Gates (stateful-only tree caede75):** perft ALL PASS; eg_check 8/8 WIN
at 300 ms incl. KPK both colors (baseline: KQvK 0/2, KRPvK-b draw);
shuffle suite 12/12 WIN @300 ms, 11/12 WIN @2 s with ZERO threefolds
anywhere (KPK-b @2 s = KPK technique gap — defender held opposition —
no repetition in the game; the same case converts in traces and at
300 ms, documented as residual OPTION-A scope); unit check: a winning
capture that would create the 3rd occurrence is refused (Rbxf1 with the
post-capture position twice in history → engine plays Rb1a1 instead,
keeping the +7xx win), while a losing KQvKR keeps its repetition (defense
case unchanged); determinism identical runs; NPS 433-496 knps (baseline
band).

**Fix 2 — qsearch knight-capture blindness (commit 496b86a, audit
finding):** `gen_moves` cap_only skipped ALL knight moves, so silent
not-in-check quiescence nodes never saw knight captures. Demonstrated:
after Rxd4 with Nxd4 the only capture, qsearch returned −190 (stand-pat)
where the exact value is 0 (>150 cp horizon error). Removed the skip
(quiet moves stay suppressed by the existing guard). Probe: cap_only gen
1 [c6d4], qsearch exact 0; falsified on the old line (0). Effect on
trees: startpos d10 1,030,699 → 987,934 nodes (score 17→10, more
accurate); mg d8 1,633,787/407 → 1,992,370/420; sharp d8 unchanged
(mate-in-1).

**Final gates on the committed tree (496b86a):** perft ALL PASS;
eg_check 8/8 WIN @300 ms; determinism identical; NPS 473-496 knps;
24-game 500ms vs HEAD 05d0101: **15W-3L-6D (0.750), ZERO flags**
(results/phase4_gate_final_vs_head.log) — well past the ≥0.55 bar: the
stateful agent converts won endgames that stateless HEAD shuffles into
draws, and the qsearch knight fix removes a silent horizon blind spot.
BUILD.md "Risks" updates: the KQvK/KRvK conversion flakiness and the
KPK technique gap (OPTION A) remain the known remaining weaknesses;
threefold-shuffle draws are eliminated. agent.zip rebuilt + verified
(60s init) on this tree.


## B4 — 2026-09-08: zobrist key fixes (P7 EP phantom removal, P8 rights-vanish ZCASTLE[0])
Found via audit 2-A (F1, EP) + probe_ep_key.py control sweep (P8). Both broke
parse_fen key parity after specific move classes (EP captures; last-castling-
right death) — impacting repetition/TT keying, not search itself. Fixes are
two guards in make_move_apply; validated: EP parity battery, 38-move control
sweep, 211-ply replay parity, depth-6 determinism. Commit 73c7d44.
**SHIPPED as V5** (uploaded Sep 8 ~16:00 UTC): tree A/B gate hand:1111 vs
pre-fix 73c7d44~1 = 0.479 null (9W-10L-5D, zero flags) → strength-neutral;
ship decision on correctness grounds (closes the last hole in the stateful
repetition defense). First V5 ladder game = r70. (r69 WIN vs Stockfish was
still V4/49c4c0e.)
Independently replicated (audit-3): sides-swapped A/B pair, seed 7, 24
games each way — fix 0.583 as A, 0.417 over 48 combined, zero flags in
all 48; inside the null band. agent.zip rebuilt + md5-verified fixed
(init 46.7s).
### P4 — dynamic null-move reduction (2026-09-08) — GATED NEGATIVE, ships OFF

**What:** a deeper null-move reduction at high depth, as a search-toggle
probe (brainA report §P4). New import-time toggles in engine/search.py:
`CHESSATHON_NULLR` (base R, default 2 = shipped), `CHESSATHON_NULL_DEEP`
(default 0/off), `CHESSATHON_NULL_DEEP_MIN` (default 6),
`CHESSATHON_NULL_R_DEEP` (default 3): when on, nodes at depth >= 6 use R=3.
All null-move guards untouched (not in check, depth>=2, ply>=1, beta>0,
`_count_nonpawns>=2` zugzwang). Harness: `side_env` gains the `nulldeep`
searchflag; engine_side prints the toggle state (A/B-process observability).

**Why:** the engine is node-starved at the competition clock (~1.5-1.8M
nodes/move, depth 9-10 middlegame); a deeper null cut at deep nodes is the
cheapest depth lever, and the Phase-3 LMR gate proved 500 ms gates
discriminate search-structure changes.

**Evidence:** perft ALL PASS off+on (6 pos d1-5, `results/perft_p4_*.log`);
determinism identical (2 fresh processes, `results/det_p4_nulldeep.log`:
544,268 nodes / best 14709 / −92 both); feature OFF = HEAD byte-identical
node-for-node (startpos d10 = 987,934 both, `results/bench_p4_nulldeep.log`
— note: the older documented 1,030,699 count predates the Phase-4 qsearch
knight fix; current HEAD baseline is 987,934); eg_check 8/8 WIN with the
feature ON (`results/eg_p4_nulldeep.log` — the nets are below the nonpawn
guard, so null-deep is inert there by construction; one KPK-w draw on the
first run was baseline load flakiness, re-runs 8/8).

**Gate (tree A/B, 24 games @500 ms, hand:1111 both sides):** nulldeep as A
vs HEAD as B — **8W-11L-5D = 0.438, ZERO flags**
(`results/gate_p4_nulldeep_vs_head.log` + `.stdout`). 0.438 < the 0.45
revert line → **REVERTED as default: feature ships OFF** (defaults are
byte-identical to V5). The toggle stays in-tree as preserved experiment/AB
infra. Interpretation: at gate depths (7-9) an R=3 null skips too much
refutation horizon relative to the total depth; the depth-starvation fix
it targeted is better addressed by the root-stability and SEE probes
(brainA P1/P2).
### P1 — SEE in qsearch (2026-09-08/09) — GATED NEGATIVE + NULL, ships OFF

**What:** static exchange evaluation in qsearch as two independently-gated
toggles (brainA report §P1; the r64/r68/r74 loss family is lost queen/rook
transactions in heavy-piece transitions). New jitted `see()` in
engine/search.py (own least-valuable-attacker swap; x-ray via occupancy
removal; pins ignored — standard; king recaptures only into undefended
squares; EP victim = pawn / promotion value excluded — documented
approximations). `CHESSATHON_SEE=1` orders qsearch captures by SEE desc
(MVV-LVA tiebreak; promotions top-banded); `CHESSATHON_SEEPRUNE=1` skips
SEE<0 plain captures at not-in-check nodes (EP/promos never pruned).
Harness: side_env gains 'see'/'seeprune' flags.

**Validation:** see() unit battery 14/14 vs an INDEPENDENT pseudo-legal
single-square minimax oracle (incl. x-ray, LVA chains, pin-ignoring —
`tools/see_unit.py` + driver, `results/p1_see_unit.log`; caught a real
occ-respect bug in the knight/pawn/king attacker scans — a consumed piece
still counted as an attacker); perft ALL PASS off+on; determinism
identical (fresh processes, 439,811 nodes r70-B d8); feature-OFF == HEAD
node-for-node (987,934 d10); eg_check 8/8 with both toggles on; qsearch
typo caught by determinism (SEEP_RUNE_ON) — the battery compiles see()
standalone only; the search compiles qsearch, and the A/B determinism run
surfaced it.

**Gates (24 games @500ms, hand:1111, seed 7, zero flags each):**
- F (ordering: hand:1111:see vs HEAD): **9W-12L-3D = 0.438** — below the
  0.45 revert line → ordering ships OFF.
- G (pruning: hand:1111:see,seeprune vs hand:1111:see): **8W-10L-6D =
  0.458** — null band (0.45-0.55), report honestly, no spin.

**Leak-suite:** r64/r68/r74 transition FENs (leak plies from the PGN
material trajectories) probed at 2.6s/move (the real-clock budget) on
both trees: SEE+SEEPRUNE scores within ±15cp of HEAD at every probe —
the loss family is NOT a qsearch-horizon blind spot at these plies (r68's
search OVERSHOT black as +12; the leaks are eval/plan-class, i.e. the
Quirk-1 compensation skew family, not capture-chain blindness).

**Ship decision (rule J):** neither toggle reached >=0.55 → both default
OFF; the shipped agent is byte-identical to V5 (feature-OFF node parity
proven). 0.438 identical to the P4 null-move and Phase-3 aspiration gate
scores (same 10.5/24 points) — n=24 discrimination is weak; the verdict
rules are applied as written. SEE stays in-tree as preserved experiment +
A/B infra (see() unit-tested and reusable for any future qsearch probe).

## P8 — compensation-aware eval clamp (COMPCLAMP) — design, pre-gate (2026-09-09)

Quirk-1 (the loss-family mechanism measured across r64/r68/r70/r74/r76):
in positions where we are materially behind but hold positional
compensation, the static eval reports near-equality or even an advantage,
so the search grinds down instead of playing the most tenacious line.
Live measurement at recon (static eval, mover POV, our own eval):

| probe | mover material | static eval | over-credit |
|---|---|---|---|
| r64 p42 (exf4) | −170 | +242 | +412 |
| r64 p83 (Rxc3) | −90 | +152 | +242 |
| r68 p65 (Kh6) | **−1020** | **+1100** | **+2120** |

The r68 shape is the killer: down a full rook, eval says +11. The
advanced-pawn PST / passer credits cancel real material.

**Leak-suite profile (results/leak_suite/fens.json, 54 FENs, 13-game
corpus):** 17 FENs have the mover ≥200cp down in raw material — and all
17 sit at phase ≤ 16. The band below therefore covers exactly the
deficit population and nothing else (movers at ≤ −200cp material with
phase > 16 do not occur in the corpus).

**The clamp rule (from the P8 writeup band):**

> In `evaluate()`, after assembly, when `phase <= 16` AND the mover's
> raw material (`mat`, white-minus-black, before tapering) is at least
> COMPCLAMP_MAT (200cp) behind, the White-POV score is clamped
> symmetric so compensation credit cannot hide the deficit:
> `if mat <= -COMPCLAMP_MAT: score = min(score, mat + COMPCLAMP_SLACK)`
> `if mat >= +COMPCLAMP_MAT: score = max(score, mat - COMPCLAMP_SLACK)`
> (SLACK = 120cp — the P8 harness band width `|static − material| ≤ 120`
> in the audited regime). The mover-POV negation at return propagates it.

Integer-only, no new params (keeps the 813-param tuner contract — the
clamp is a post-assembly correction like the Phase-3 mate-drive term).
Thresholds: phase ≤ 16 (endgame-safety first — past that the mate-drive
regime owns conversion and an eval clamp must not fight it), |mat| ≥ 200
(a minor or more), slack 120 (the audited fixed-point band).

**Toggle:** `CHESSATHON_COMPCLAMP=1` enables; default OFF = byte-identical
V5 (verified node-for-node). Read at import like NULL_DEEP/SEE — numba
bakes it. env var plumbing added to tools/common.py side_env as search
flag `compclamp` for gate_match.

**Endgame-safety invariant:** eg_check must stay 8/8 with the clamp ON
(KQvK/KRvK/KPK/KRPvK both colors). The clamp only fires at |mat| ≥ 200
with phase ≤ 16 — the strong side in a won basic endgame is ≥200 UP, so
its own eval gets *raised* (max side), never lowered; the defending side
is clamped toward the material truth, which the mate-drive term already
dominates. KPK (mat=100 < 200) is untouched by construction.

**Gate plan (audit §2 standard):** L1 24-game @500ms gate vs HEAD +
perft/shuffle/determinism/60s-init; L2 leak-suite 54-FEN probes @2.6s
vs HEAD (non-regressive + clamp-effective on the deficit FENs); L3
SF19-e2200 real-clock bout vs the V5 reference; L4 quality_ab replay
with the F1/F2/F3/F5 stats patch. Ship ON only if all clear.

**GATE RESULTS (2026-09-09) — DECISION: STAYS OFF (default), V5 ships.**

- **OFF-identity (precondition):** static eval parity 5/5 probe FENs vs
  HEAD (values 242/152/−1100/599/132); node-for-node search identity
  1,686,741 nodes @d8 r70-mid FEN, fresh processes, both trees
  (tools/det_check.py). Unset CHESSATHON_COMPCLAMP = byte-identical V5.
- **Clamp-effective (static, the mechanism):** all 13-17 deficit-mover
  armed FENs now read at/below mat+120 (+10 tempo): r68 p65 down 1020
  reads −1100 (was +1100), r80 p46 down 1110 reads −2069. 29-31/54
  suite FENs arm; zero false arms above phase 16.
- **L1 — 24 games @500ms vs HEAD, seed 7, zero flags: 8W-12L-4D =
  0.417** — below the 0.45 revert line (results/gate_compclamp_vs_head.log).
  Fourth consecutive eval/search probe in the 0.41-0.46 band (asp 0.438,
  SEE 0.438, SEEPRUNE 0.458): n=24 keeps failing to separate this class;
  rule applied as written → L1 NEGATIVE.
  perft ALL PASS; determinism identical (2× fresh procs); eg_check 7/8
  with clamp ON (@300ms and @2000ms; the one miss, KPK-b, matches the
  V5 CONTROL run on the same box/session — @300ms V5 also drew it, and
  V5 @2000ms drew BOTH KPK colors; the KPK-b gap is pre-existing
  PROCESS backlog #1, not a clamp regression). Shuffle @2000ms: 7/10
  clamp ON vs 9/10 V5 control, zero threefolds both — the 2-draw delta
  sits inside the KPK/KQvK flake band documented in Phase-4 risks.
- **L2 — leak-suite probes @2.6s, V5 vs CLAMP (54 FENs):**
  non-regressive (0 new ≥300cp move degradations on V5-sane positions;
  2/54 chosen moves changed, both non-armed FENs, deltas +25/−8cp) and
  clamp-effective on the static eval. Searched scores at 2.6s on armed
  FENs shift median 0cp (max −14): V5's SEARCH already finds the
  material truth at these depths — the clamp corrects the STATIC leaf
  evals, which is where the grind-down gets its "we're fine" signal.
  Caveat per operator: the on-disk 78-row corpus was later flagged for
  wrong-side rows (r77/r78/r80/r83); re-verified by FEN-turn: 0 side
  mismatches in this file, and excluding all four flagged games leaves
  the verdict unchanged (0 new degradations, 13 unflagged deficit FENs
  clamp-effective). A corrected corpus was landing after this run.
- **L3 — SF19-e2200 real-clock bout, 1200ms/move: 5W-5L-0D over 10
  clean games** (driver wedged at game 11, killed; operator directed
  using the 10). V5 reference same config/session class: 1W-4L-0D + 1
  aborted. 50% vs ~25% — not worse, on 10 games wide error bars.
  5 losses at this Elo gap are the expected shape for either build.
- **L4 — NOT RUN for the clamp** (operator stopped new heavy runs;
  the wedge consumed the window). The patched tool (winsorized+median
  stats, faced/total denominators, trimmed-mean check) is committed and
  self-tested on r70 HEAD: fidelity 25/30, trimmed 111.1 vs 120.5,
  faced 1/5 — instrument working, verdict label advisory.

**Ship rule from the gate plan: ship ON iff L1 ∧ L2 ∧ L3 ∧ L4.** L1 is
0.417 < 0.45 → the AND fails at the first gate. L2 pass, L3 not-worse,
L4 absent — none can rescue a below-revert-line L1. **COMPCLAMP stays
OFF (default unset = V5, byte-identical, proven); the toggle remains
in-tree as a documented, deterministic, well-characterized experiment.**

What the evidence says for the future: the clamp does exactly what it
claims at the eval level (deficit positions stop reading as equal), it
is endgame-safe, and it does not hurt at real clocks. What it does NOT
do is win the 500ms gate — like every other eval-surface probe this
event. The Quirk-1 fix that would actually move games needs the deficit
signal to reach MOVE SELECTION (e.g. via a contempt/deficit term that
biases the root decision, not just leaf texts), which is a search-layer
change — and the 500ms gate's inability to discriminate this class
means such a change would need the real-clock bout as its primary
instrument, not the gate.
