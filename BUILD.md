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
- [x] Phase 2: search core (negamax/alpha-beta/ID/TT/quiescence) — 1b
- [x] Phase 3: evaluation — 1b baseline (PST+taper+bishop-pair+tempo); tuning next
- [x] Phase 4: time management — 1b (remaining/45 + inc, never flags); pondering pending
- [x] Phase 5: tuning + testing vs baseline — tuned LOSES to hand (SPRT 0-wins-in-50, gate 0.104, eg 1/4); hand eval ships
- [x] Submission zip — agent.py + engine/ only, 25,031 B, init 44.9s, hand eval

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

### Phase 3 (in progress, 2026-09-07) — search strength: aspiration windows + the correctness forensics they exposed

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
untouched). eg_check (strong-as-white, 300ms): KQvK WIN, KRvK WIN,
KRPvK WIN, KPK DRAW — 3/4, matching the Phase-2 record (KPK draw is the
known baseline).

Gates re-run on the final Step-1 tree: perft parity ALL PASS (6 pos,
d1-5 + breakdowns); bench nps 487/572 knps (startpos d10 / mg d8); exact-
core aspiration parity EXACT; shipped-config parity equal-value-only.

**Step-1 strength gate (running)**: `hand:1111:asp` vs `hand:1111:noasp`
24 games @ 500ms our openings — `results/gate_asp_vs_noasp_20260907_*.log`.
Need ≥ ~55% to proceed.
