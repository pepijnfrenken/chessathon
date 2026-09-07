# 02 — Evaluation & Tuning (Workstream 2 KB)

Scope: hand-crafted eval design, tuning methodology, and the dev-time testing loop for a
1-core / 2 GB / CPU-only / numba-accelerated Python engine (python-chess 1.11.2, numba 0.67.0).

## 0. Originality boundary (read ORIGINALITY.md first)

- **Concepts are public knowledge**: negamax, alpha-beta, tapered eval, Texel tuning, PSTs —
  implement fresh in our code, zero copied lines. `[standard concept]` tags below mark these.
- **Published numbers are citable data** (material values, PST tables, TB sizes). If we ship a
  published PST table we must log the source in BUILD.md; **preferred: tune our own values** so the
  eval is demonstrably ours (ORIGINALITY.md §Provenance). Nothing here is copy-pasteable source.
- **Dev-only tools** (Stockfish, cutechess-cli, CCRL engines) live **outside this repo** (`/tmp`,
  `~/tools`), never committed, never in the zip. The ban is on what ships.

## 1. Constraints that shape the eval

Search speed is the currency: every eval term competes with depth. Assume ~2–20 kNPS in a
python-chess + numba search (measure in Phase 2); at 120 s/move that's ~10^5–10^6 nodes — enough
for depth ~10–16 with a cheap eval, not for a big one. Eval must be: numba-friendly (integer
arrays, no objects), O(pieces) not O(attacks), no TT probing inside.

## 2. Material values — the modern landscape

| System | P | N | B | R | Q | Source |
|---|---|---|---|---|---|---|
| Classical | 1 | 3 | 3 | 5 | 9 | Capablanca&deFirmian (cited in [1]) |
| Kaufman 1999 | 1 | 3.25 | 3.25 | 5 | 9.75 | [1]; Wikipedia piece values [2] |
| AlphaZero-implied | 1 | 3.05 | 3.33 | 5.63 | 9.5 | "Assessing Game Balance with AlphaZero", arXiv:2009.04374 — verbatim: "3.05–3.33–5.63–9.5" [1] |
| PeSTO mg | 1 | 3.37 | 3.65 | 4.77 | 10.25 | Texel-tuned PST-only eval [3][4] |
| PeSTO eg | 1 | 2.81 | 2.97 | 5.12 | 9.36 | same |
| Kaufman 2021 | 1 | 4 | 4+ | 6 | 11 (queens ON); N3/B3+/R5 (queens OFF) | [2] |

Takeaways:
- Tuned systems all put **B slightly > N** (bishop pair bonus adds more), R ≈ 4.8–5.6, Q ≈ 9.4–10.
- **Endgame values differ from middlegame**: Q drops, R rises, N drops — that's why tapered
  material (or mg/eg PSTs) beats single values. PeSTO's eg table is exactly this.
- Kaufman 2021's queens-on/off split is the single most important *structural* insight: the value
  of minors and rooks shifts by ~25% when queens are on or off. Cheap to implement as two
  material tables selected by `queens_present`, or ignore it and let PSTs absorb it.
- Decision: start from a published set as prior (log source), then Texel-tune our own (§6); the
  numbers above are sanity anchors when tuned values look crazy (e.g. PeSTO's mg-queen 10.25 is a
  known artifact of its rook being undervalued — don't chase 9.5).

## 3. Piece-square tables + tapered eval — the backbone

- PeSTO pattern `[standard concept]`: full-board mg + eg tables per piece (no symmetry expansion),
  plus per-piece mg/eg *material* base; final score interpolates by game phase:
  `score = (mg·φ + eg·(24−φ))/24` with φ = Σ phase-inc(piece), phase=1 per minor, 2 per rook,
  4 per queen, cap 24. P=82/94, N=337/281, B=365/297, R=477/512, Q=1025/936 (mg/eg) [3][4].
  Full 64-square tables are public data [3] — **cite or re-derive; do not paste into our file
  without logging the source in BUILD.md**.
- Why PSTs dominate: they encode king safety-in-late-game, development, pawn structure topology,
  and endgame king activity all at once. **Pawn PST is the single highest-value table** (pawns
  decide most games); king PST (mg: castle-ish; eg: centralize) is second.
- Alternative to hand-graining: **fit our own PST by least squares** — if the eval is linear in
  params (material + PST only), Texel-style regression becomes closed-form/IRWLS in numpy;
  Leorik reported high-quality material+PST tables "in 20 seconds" this way [5]. This is our
  primary plan; hand-start values from §2.
- Practical notes: mirror tables for Black by rank-flip (`sq^56`-style); store as flattened
  arrays for numba; phase from a simple material count is enough.

## 4. Beyond material+PST — terms by ROI per implementation hour

1. **Tempo / side-to-move**: skip (search's null move handles it).
1. **Mobility** — biggest non-PST term: count moves (or attacks) per piece, weight minors ≈
   2–4 cp/move, rooks ≈ 1–2, queen ≈ 1 [6]. Cheap with precomputed attack tables. Typical
   published bonus scale: ~2–3 cp per extra move for minors/queen, ~1 for rooks.
2. **Pawn structure** — isolated/doubled penalties (~8–15 cp), **passed pawn** bonus by rank
   (biggest endgame ROI: ~10–50 cp, +protected/advanced, +rook-behind bonus) [7][8]. Highest
   strategic ROI per hour after PSTs.
3. **King safety** — pawn shield/shelter in front of castled king + enemy-attacker/queen-tropism
   term; gate the whole attack machinery. A coarse shield+shelter table buys more Elo than
   anything else in open positions [9].
4. **Bishop pair** (~30–50 cp mg, fading in eg) and **rook on open/semi-open file** (~10–20 cp).
5. **Endgame king activity** (distance-to-enemy/center bonuses, ~–20..+20 range) — converts wins
   (see doc 03); cheap, high value because adjudication rewards material preservation.
- **NOT worth it**: Q-vs-3-minors imbalance formulas; per-colour-bishop subtleties; eval
  resolution under 1/100 pawn; explicit opposition logic; contempt beyond a constant; an NN —
  a 1-core tensor eval is slower than the depth it buys, and "did you train it?" is the exact
  question judges ask. Classical hand eval is the whole point (ORIGINALITY.md, BUILD.md).

## 5. What separates ~1800 from ~2400 CCRL (in eval terms)

CCRL rating lists (40/15, 40/2): https://ccrl.chessdom.com/ccrl/404/ (unreachable from dev
sandbox — verify link locally). Band heuristic, from engine dev lore (not a measurement):

| Band | Eval characteristic |
|---|---|
| ~1700–1900 | material + naive PST (no taper or wrong values); no mobility/king-safety; endgame-blind (no passed-pawn, no king activity); eval noise → missed tactics, shuffling in won positions |
| ~2000–2200 | tapered mg/eg PST (PeSTO-class) alone gets you into this band once search is sane (TT + qsearch); this is the documented "wall at ~1860–2000" region [10] |
| ~2300–2500 | + mobility, king safety, pawn structure, bishop pair, decent endgame terms; eval *matches* search depth — the difference from 2000 is not one big term but the eval not lying about position class |

Caveat: Elo is mostly search (TT/null move/LMR/qsearch quality + speed); the 1800→2400 jump in
*practice* comes from eval that converts plans (pawn breaks, king attacks, won endgames), which is
where terms above pay. The CCRL list is the ladder we calibrate against with Stockfish at
`UCI_Elo` (below).

## 6. Tuning methodology

### 6.1 Texel tuning — what and how `[standard concept]`
- Data: positions from games with results, **qsearch eval at each position**, target
  `p = 1 / (1 + 10^(−s/400))` (Texel's original: `1/(1+exp(−K·s))`, K≈1.13 with s in pawns).
  Minimize mean squared error against game result (0/0.5/1); K fitted once, then frozen [11].
- Filters that matter [11]: skip opening-book plies; skip positions with mate scores; don't
  exclude "noisy" positions (Österlund found including them *helps*). Correlation: ~140
  positions/game are fine (weighted-LS view).
- **CPU-only: yes, fully feasible.** Österlund's own runs were CPU: ~400 params, ~8.8M
  positions, gradient ≈ 25 min on 16 cores [11]. Scale to 1 core: 100–200k quiet positions →
  roughly 10–60 min per gradient pass with a numba-jitted static eval; local search
  (one-param-at-a-time, ±1) over ~400 params ≈ hours per sweep. A curated 50k-position set
  with a *static* (no qsearch) eval converges in minutes per epoch and still tunes PSTs well —
  this is the standard hobby-engine path [5][12].
- Data sources, in preference order: **(a) our own self-play PGNs** (strongest signal; played at
  fast TC, e.g. 1s+0.08, between our builds); **(b) human games (Lichess DB, database.lichess.org)
  or engine-annotated PGNs** — explicitly allowed by the rules ("training data unrestricted incl.
  positions annotated by an existing engine"); (c) mixed. All `[standard concept]` data, no
  shipping of any third-party *code*.
- Fast path: **linear eval ⇒ linear least squares / IRWLS in numpy** for material+PST (Leorik [5]);
  then hill-climb discrete terms (mobility weights etc.) with small local-search epochs; validate
  every accepted change by SPRT (§7).

### 6.2 Minimum viable tuning for a week
1. Day 1–2: sane hand values (§2 priors) + PeSTO-style tables; **no tuning yet** — fix search first.
2. Day 3: extract 50–200k quiet positions from self-play/human PGNs (skip post-mate, skip first
   ~10 plies); fit material+PST (numpy). Expect a visible jump vs hand tables.
3. Day 4–6: add one §4 term at a time, re-tune the affected params, SPRT-accept/reject. Stop
   adding when SPRT says "no difference" twice — further terms are noise-shifting.
4. Day 7: final material/PST re-tune on fresh data; freeze; test at 120+0.5 (real clock).
Rule: **accept only SPRT-certified changes**; Elo from raw matches lies at these sample sizes.

## 7. Dev-time testing infrastructure

### 7.1 Rules status
Stockfish **may** be used locally, outside the repo (`/tmp`, `~/tools`), never committed —
ORIGINALITY.md §Allowed.5. Same for cutechess-cli and any CCRL engine used as an opponent.
Nothing engine-like ships in agent.zip. Build log is in BUILD.md.

### 7.2 Baselines (best → ok)
1. **Our own previous build** — the fairest SPRT opponent for patch testing.
2. **Stockfish at a target strength**: official release binary (github.com/official-stockfish),
   set `UCI_LimitStrength true` + `UCI_Elo <target>` (SF plays at an approximate Elo level) —
   the cleanest way to emulate the house-bot band and to know "where we are" on CCRL-ish scale [13].
3. **A CCRL-listed engine near our band** (download outside repo) — cross-checks SF-elo mapping.

### 7.3 Harness
- **cutechess-cli** (github.com/cutechess/cutechess; install outside repo) is the fastest
  reliable loop: engine-vs-engine, PGN openers, per-`-each` clocks, adjudication flags, and
  built-in **SPRT**:
  `cutechess-cli -engine name=base cmd=... -engine name=patch cmd=... \
    -each tc=1+0.1 -openings file=curated.pgn format=pgn order=random \
    -sprt elo0=0 elo1=10 alpha=0.05 beta=0.05 -games 2 -rounds 1000 ...`
  (SPRT: accept/reject a 0→10 Elo gain with 5% error — roughly 200–600 games at fast TC; the
  pass/fail verdict, not the raw score, is the decision [14].)
- **Python-only loop** (no extra deps for a quick check): `chess.engine.SimpleEngine` driving
  both sides in-process (our own small harness script; dev-only — the shipped agent is
  `get_move(fen, time_left_ms)`). Approximate Elo: `400·log10(score/(1-score))`, CI via binomial;
  use it only as a smell, not a gate.
- **TC ladder for a Python engine**: SPRT at 1+0.1 (or fixed-node ≤ ~1e6 nodes) for patches;
  a 120+0.5-sample (100+ games) against SF-at-target-Elo for acceptance in the last days.
- **Openings**: the competition's curated set (if published) + a suite we write ourselves
  (midgame tactical + endgame conversion FENs from our own games); avoid copyrighted test
  suites. Alternate colors automatically (`-games 2` swaps).
- Adjudicate fast dev games (`-draw movenumber=100 movecount=50 score=5`, `-resign`) so engines
  don't exhaust time dancing — final 120+0.5 runs keep full adjudication rules of the event
  (300-ply, material-decides, see doc 03).

### 7.4 Fastest reliable local loop (order)
1. Patch → cutechess SPRT vs previous build @ 1+0.1 (minutes).
2. Daily: 200-game run vs SF (`UCI_Elo` = target band) @ 5+0.05 — trend vs house-bot band.
3. Pre-freeze: 120+0.5 sample vs SF-at-target + a CCRL anchor opponent; both colors; then stop.

## Sources
[1] arXiv:2009.04374 (Assessing Game Balance with AlphaZero) — https://arxiv.org/abs/2009.04374
[2] Wikipedia: Chess piece relative value — https://en.wikipedia.org/wiki/Chess_piece_relative_value
[3] CPW: PeSTO's Evaluation Function (mg/eg tables, phase math) — https://chessprogramming.org/PeSTO's_Evaluation_Function
[4] RofChade blog: PeSTO PSQT-only — https://rofchade.nl/?p=307
[5] Leorik devlog: PSTs from scratch in ~20 s — https://www.talkchess.com/forum3/viewtopic.php?f=7&t=79049
[6] CPW: Mobility — https://chessprogramming.org/Mobility
[7] CPW: Passed Pawns — https://chessprogramming.org/Passed_Pawn
[8] CPW: Pawn Structure — https://chessprogramming.org/Pawn_Structure
[9] CPW: King Safety — https://chessprogramming.org/King_Safety
[10] "Hitting a wall at ~1860 Elo" (eval-vs-search evidence) — https://www.talkchess.com/forum3/viewtopic.php?f=7&t=77427
[11] CPW: Texel's Tuning Method — https://chessprogramming.org/Texel's_Tuning_Method
[12] txt: automated tuning tool (concept reference) — https://talkchess.com/viewtopic.php?t=55696
[13] SF UCI options (UCI_LimitStrength/UCI_Elo) — https://official-stockfish.github.io/docs/
[14] cutechess-cli docs (SPRT, openings, adjudication) — https://github.com/cutechess/cutechess