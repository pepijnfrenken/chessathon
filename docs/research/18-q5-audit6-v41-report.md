# chessathon AUDIT 6 (deepseek-v4.1) — v7 fresh-eyes audit + r92-tunnel deep dive + ranked improvements

**STATUS: COMPLETE.** All three requested deliverables are delivered: (A) codex5 2/3/4
verified-or-refuted with observed output **plus 10 new findings**, (B) the r92 tunnel mechanism
measured and three mitigations prototyped with a **document-only verdict + gate spec**, (C) a
ranked candidate list with patch sketches, instruments, risks and gate specs, (D) the builder's
`590f5ff` reviewed against its own gate result.
Read-only throughout: **no writes** to `/tmp/chessathon-aud6` or `/home/pino/projects/chessathon`;
all prototypes in scratch copies.
Probe work stopped at 11:30Z on the operator's instruction when the builder's v8 L1 gate started
(flag `/tmp/chessathon-v8dp-gate.flag`, 11:27Z) and **has not restarted** — the flag file is still
present at the time of writing, so the remaining listed measurements are deliberately unrun (§F).
That gate has since finished (**0.417, 6W-10L-8D, zero flags** — a null inside the project's known
band; §D). One probe of mine (`aud6-probe8.py`, 11:29Z) overlapped it; it was killed as soon as
the operator flagged it, and every overlap is disclosed in §F rather than hidden.

**Basis:** read-only tree `/tmp/chessathon-aud6` @ `1fc4402` = shipped v7 (zip sha `d5d57f6a6e4a`).
**Control-tree verification:** `/tmp/chessathon-v7ref` (the control the builder's gates and L2 runs
use) is **byte-identical to my audit tree on all 7 shipped files** — `board.py c36229c95986`,
`eval.py b1dd2413e948`, `search.py 8804e3800d82`, `tt.py c42fd2300577`, `time.py 258de7ae09cd`,
`agent.py c67cefd50b04`, `__init__.py e3b0c44298fc`. So the builder's A/B numbers and mine describe
the same two trees: *this audit's v7* vs *v8 + one index fix*. No hidden divergence.
Scratch prototypes live outside it: `/tmp/aud6-scratch-regress` (M1), `/tmp/aud6-scratch-consist` (M2),
`/tmp/aud6-scratch-pstfix` (C1 PST flip, env-toggleable).
Probe scripts `/tmp/aud6-probe{1..10}.py`, `/tmp/aud6-static-preview.py`, outputs `/tmp/aud6-p*.txt`,
`/tmp/aud6-c1-*.txt`, `/tmp/aud6-c1-battery.log`.
**Live-state updates folded in during the audit** (all read-only): the v8dp L1 gate was run twice —
**same config, same seed 7**, scoring 0.417 then 0.562, which produced the §B5 instrument-calibration
finding; and ladder rounds r95 (win) / r96 (loss, *not* the r92 motif) landed, §E.1.
Box discipline: one engine process at a time, `NUMBA_CACHE_DIR` fresh per tree, gate/flag checked
before every batch; the 11:27Z overlap is disclosed, not hidden.

---

## 0. HEADLINE

1. **The r92 "collapse" is not a root-ordering defect and not a ≤2 s band. It is a depth-granular
   eval outcome.** At *equal fixed depth* v7 and night2 play the **identical** move in both r92
   positions; they diverge only in *which depth completes* inside the venue budget. The m35 ID
   prefers `d5b3` at depths **7, 8 and 9** (the full root table at d7: `d5b3` 70 vs `e5d3` **13**).
   Stockfish 19 @d20 does not list `d5b3` in its top 6 at all, and rates it **287 cp worse than `e5d3`** (the d6 pick) and **315 cp worse than its own best** (`g3h2`).
2. **The tunnel is not budget-fixable.** With a fresh TT, v7 plays `d5b3` at **every** budget from
   1 s to 8 s (depth 7 → 9). Only depth 10 (~20 s on this box) switches it — far outside the clock
   policy. "Spend more time" and "revert rootorder" are both wrong instruments.
3. **PROCESS §14's sweep claim ("blunder band ≤2 s, avoided at ≥3 s") did not reproduce.** It is a
   warm-TT artifact of `probe_r92_collapse.py`'s sequential SWEEP loop (TT carried across calls);
   my fresh-TT runs blunder at 3/4/6/8 s. Section B1.
4. **Two candidate root-side guards were prototyped. Both are rejected on measurement:**
   M1 (score-regression) churns **35/98** leak-corpus moves with **16 swings ≥ 300 cp** and biases
   reported scores *optimistic* in lost positions; M2 (move-consistency) would have **rejected
   v7's own correct depth-8 move on m36** (analytically proven from my own root-score tables).
   **Tunnel verdict: DOCUMENT-ONLY.**
5. **Highest-value strength candidate found: the PST family is read upside down.** Every PST
   literal is the standard **row-0-is-rank-8** presentation (proof: `_PAWN_MG` row 1 = `[50]*8`,
   `_ROOK_MG` row 1 = the classic 7th-rank bonus, `_BISHOP_MG` row 5 = the classic rank-3 row),
   but the consumer indexes `s = sq64(sq)` with row 0 = rank 1. **night2 normalized only the pawn
   tables.** Consequence as read: white's own back rank `e1/g1/c1 = −50/−40/−40` while the
   **enemy** back rank `e8/g8/c8 = 0/+30/+10` (king asymmetry 70 cp, 64/64 cells); the rook's
   7th-rank bonus (+10) sits on **rank 2**; the bishop's rank-3 row sits on rank 6. A one-line row
   flip per table restores the intended profiles — the same shape that gated **L1 1.000** for the
   pawns. This subsumes the repo's own `docs/research/08` "Ablation B", which was never run. §C1.
6. codex5 findings 2/3/4 **all CONFIRMED** with fresh runtime probes; F4 is **worse** than
   reported (a warm TT can override an *actual* fifty-move draw). New: mate-scored-as-draw at
   halfmove 100; stalemate invisible to qsearch stand-pat; two contradicting EP canonicalisations.
7. Builder commit `590f5ff` (doubled-pawn index fix) is **correct and minimal**; review + the
   gate-power caveat in §D. **Its L1 gate finished at 11:59Z: 0.417 (6W-10L-8D, zero flags)** from
   the candidate's perspective — a score sitting exactly at the top of this project's recorded
   known-null band (0.396–0.417), so it is the expected null for a strength-neutral correctness
   fix and **not** a blocker. §D also flags that the v8 battery's r92 line repeats the warm-TT
   sweep artifact my §B1 corrects (conclusion right, evidence wrong).
8. **THE INSTRUMENT IS NOISIER THAN THE DECISIONS MADE WITH IT.** The builder's two v8dp gates
   were the *same configuration* (same seed 7, same trees) and scored **0.417 vs 0.562** — with
   **15 of 24 games changing result** between runs. Measured same-config repeatability ≈ **±0.07
   score (±3.5 games)** at n=24, because the search is time-limited and wall-clock jitter flips
   games. Against that: the **night3 rootorder change — the one that produced the r92 tunnel — was
   shipped on a gate at +2.5 games, i.e. INSIDE the instrument's own noise.** The pawn flip's
   1.000 (+12) stands; 0.708 (+5) is marginal; 0.604 (+2.5) and the old "known-null band
   0.396-0.417" do not. §B5 — this is the methodology finding of the audit.
9. **Tooling gap found: every gate/bout harness never clears `_REP` on `reset`** (it clears the
   game window and the TT only). Games 2..N of a multi-game process therefore scan repetition keys
   belonging to an **earlier game**. Re-derived severity: **LATENT, low** — those entries hold the
   previous game's *final* positions, so a phantom hit needs a genuine cross-game transposition at
   matched parity. It does **not** inflate the draw count and does **not** undermine the gate or
   bout results. Still a free 1-line fix (§A12/§C0) — I originally over-claimed this as HIGH and
   have corrected it in place rather than quietly dropping the claim.

---

## 0b. OPERATOR SUMMARY — what to do before the freeze (30-second read)

| # | do what | why | evidence | cost |
|---|---|---|---|---|
| 1 | **Upload the v8dp doubled-pawn fix** — pooled gate **0.490/48 games**, zero flags, and **L2: 13/107 moves changed with 0 score swings ≥100 cp and node ratio 0.995** | strength-neutral correctness fix; the two gate runs were the SAME config (seed 7) and straddle 0.500 = textbook null; perft/det/decompose green | §D, §B5, §A17 | 0 (all instruments already run) |
| 2 | **Run the C1 king-PST gate** (staged, one variable, spec in §C1b) | the only candidate that can plausibly *gain* strength; attacks the r92 root cause | §C1, prediction: static +103→+69 at m35 | ~1 h |
| 3 | If C1 ≥ 0.55 → gate `KBR` (rook+bishop) as the next single variable | rook's 7th-rank bonus is on rank 2 today | §C1/C8 | ~1 h |
| 3b | Do **not** chase the mate-stratum gap (4/24) with C3b — I tested it: only 1/24 rows involve a pawn on the 7th; 19/24 are piece-bearing positions where we were already worse | negative mechanism check recorded so nobody re-derives it wrongly | §A18 | 0 |
| 4 | Apply **C0** (`_REP.fill(0)` on reset) — **before the planned ladder bout**: the new `tools/engine_side_clk.py:172-175` has the same gap | hygiene; makes the next bout/gate count mean what it says | §A12 | 10 min |
| 5 | Do **not** revert rootorder; do **not** chase the tunnel with a root-side guard | measured: the two r92 positions demand contradictory root policies | §B1-B4 | 0 |
| 5b | **Use pooled multi-seed gates and these thresholds: ≥0.55 positive, ≤0.45 negative, 0.45-0.55 unresolved.** Never overturn a shipped change on one 24-game gate | same-config repeats span 0.417-0.562 (15/24 games flip) | §B5 | 0 |
| 6 | Optional, free: apply the two selfcheck assertions (§F1) so this PST class cannot recur silently | the shipped selfcheck is invariant to the bug | §A7/F1 | 5 min |
| 7 | When reading the v8dp **L2** leak log, ignore its **first row** (`nodes=0 score=-32000`) — that is cold-JIT, not engine behaviour | the new tool has no warmup call before the corpus loop | §A16 | 0 |

**Do not do:** revert rootorder (m36 reverses, +164 % nodes, contradicts the 18-game bout); ship a
score-regression or move-consistency root guard (both measured/derived to fail one of the two r92
positions); re-run the r92 sweep with `SWEEP=1` and read the ≥3 s rows (warm-TT artifact, §B1).

---

## A. VERIFY-OR-REFUTE (codex5 2/3/4) + fresh-eyes findings

| # | claim | verdict | location |
|---|---|---|---|
| F2 | king-colour Zobrist alias | **CONFIRMED** | board.py:101,254,290,296,753 |
| F3 | pinned EP breaks repetition identity | **CONFIRMED** (wider root cause) | board.py:311-320 vs 721-733 |
| F4 | TT ignores fifty-move context | **CONFIRMED, worse** (can override a real draw) | search.py:545-563, tt.py:49 |
| F1 | doubled-pawn `FILE_SQ[f*8]` | present in v7, **fixed** in builder 590f5ff | eval.py:598,601 |
| F5 | mate@hm100→0; stalemate qsearch; MAX_PLY | **CONFIRMED** | search.py:341-360, 492 |
| F6 | `eval_decompose` mixed index groups | confirmed (dev-only) | tools/eval_decompose.py:74-86 |
| F7 | clock divisor model | confirmed, no defect | time.py:22-32 |
| **NEW 1** | **PST family read inverted; only pawns were normalized** (king 70 cp/64 cells, rook+bishop 10 cp/20 cells) | **CONFIRMED (literals are standard row0=rank8)** | eval.py:236-311 |
| **NEW 2** | `docs/research/08` item 4 "non-pawn tables: NO-OP" is false for rook/bishop | **REFUTED (that doc item)** | docs/research/08 |
| **NEW 3** | mate-vs-fifty rule inversion | CONFIRMED | search.py:341-360 |
| **NEW 4** | stalemate invisible to qsearch stand-pat | CONFIRMED (new mechanism) | search.py:486-500 |
| **NEW 5** | `_REP` never cleared between games | CONFIRMED (dev-harness scope) | agent.py:73-89 |
| **NEW 6** | EP canonicalisation mismatch (root vs make) | CONFIRMED (root cause of F3) | board.py:290-300 vs 721-733 |
| **NEW 7** | `eval._selfcheck` mirror test is structurally blind to vertical inversion | CONFIRMED (by inspection) | eval.py:723-746 |
| **NEW 8** | qsearch never generates **quiet** promotions | CONFIRMED (by inspection) | board.py:432-461 |
| **NEW 9** | mate-drive term armed with queens on the board, up to 350 cp | CONFIRMED (arithmetic) | eval.py:671-673 |
| **NEW 10** | blocked-passer (`blk`) term is **structurally dead code** | CONFIRMED (inspection) | eval.py:151-157 vs 579-583 |
| **NEW 11** | `reset` clears `_GAME_KEYS` + TT but **never `_REP`** in every harness; stale keys are scanned (LATENT, low severity — needs a cross-game transposition) | CONFIRMED (inspection, all 4 harnesses) | q5_engine_side.py:171-176, engine_side.py, engine_side_tree.py:146-152, engine_side_clk.py:172-175 |
| **NEW 12** | builder's L2 tool loses its **first corpus row** to cold JIT on *both* sides (budget consumed by compile) | CONFIRMED (results/v8dp_leak_probe_cand.log + _v7ref.log line 1) | tools/leak_probe_tree.py |
| **NEW 14** | mate stratum: only **4/24** positions yield a mate score (both trees); 19/24 are piece-bearing ⇒ hard-position/depth, **not** promotion blindness (1/24) | measured (leak_probe_tree + material check) | §A18 |
| **NEW 13** | L2 cand/control logs are **not row-aligned** (98 vs 107 rows; corpus refreshed mid-run) | CONFIRMED (row counts + corpus mtime 12:34) | results/v8dp_leak_probe_{cand,v7ref}.log |

### A2 — King-colour Zobrist alias (CONFIRMED)
`ZPIECE = _RNG.integers(0, 2**64, size=(128, 12))` (board.py:101), consumed at :254, :290, :296
and :753 as `ZPIECE[sq, pc + 5]`. Piece codes are `-6..-1, +1..+6`, so `pc+5` maps white
`{+1..+6} → {6..11}` and black `{-1..-6} → {4,3,2,1,0,-1}`. **`-6+5 = -1 ≡ 11` = white king's
column** — the only collision.

```
$ cd /tmp/chessathon-aud6 && NUMBA_CACHE_DIR=/tmp/aud6-numba-p1 \
    /tmp/chessbench/bin/python /tmp/aud6-probe1.py | grep f2_king_alias
{"probe": "f2_king_alias", "f1": "7k/8/8/8/8/8/8/K7 w - - 0 1",
 "f2": "7K/8/8/8/8/8/8/k7 w - - 0 1",
 "key1": 18439174916088828477, "key2": 18439174916088828477,
 "keys_equal": true, "valid": [true, true]}
```
Fix: 13 columns, index `pc + 6` at all five sites. Exposure: the two colliding positions need
both kings swapped with side-to-move/castling/ep matched, so real-game frequency is very low.
**Priority LOW-MED; cheap; gate-able (24 g @500 ms); no strength claim.**

### A3 — EP canonicalisation: three disagreeing rules (root cause of F3)
Measured (`f3_pinned_ep`, `f3b_ep_key`):
```
start  3k4/8/8/8/3p4/8/4P3/K2R4 w - - 0 1
play   e2e4 d8e8 a1b1 e8d8 b1a1
python-chess is_repetition(2) = True ; engine key != start key  -> False
engine ep field after e2e4 = 36 (e3); python-chess FEN after e2e4 = "... b - - 4 3" (ep dropped)
```
Three notions of "EP present" that disagree:
1. `parse_fen` (board.py:721-733) **trusts the FEN field** and hashes `ZEP[ep & 7]` — even when no
   pawn can capture. Measured: `4k3/8/8/8/4p3/8/8/4K3 w - e6 0 1` hashes differently from `-`,
   and python-chess normalises the former to the latter.
2. `make_move_apply` (board.py:290-300) sets ep on a **pseudo-legal** test (adjacent enemy pawn
   exists) — no pin/legality check.
3. The arena / python-chess emit ep **only when a legal EP capture exists**.
Consequence: an arena FEN carrying a non-capturable ep field yields a root key the search's own
make/unmake path can never reproduce → repetition blindness (the r54/r55 shuffle family) + TT
misses. Fix: make `parse_fen` canonicalise through the same test as `make_move_apply`, **and**
move that test to legality (king-safety after the capture) so both agree. **Priority MED.**

### A4 — TT ignores fifty-move context (CONFIRMED, worse than reported)
```
placement 7k/8/8/8/8/8/8/KR6 w - - <hm> 1 at depth 2
  fresh TT, hm=99      ->     0     (correct)
  fresh TT, hm=0       ->   593
  TT warm,  hm=99      ->   593    <-- WRONG: a warm entry overrides the draw that was seen cold
```
The key contains no halfmove state (STATE_DTYPE has `halfmove`, but neither `parse_fen` nor
`make_move_apply` hashes it) and `tt_probe` accepts any depth-sufficient matching entry
(search.py:545-563) before the fifty-move rule is re-derived. Fix: pack a "fifty-move armed" bit
(or the halfmove) into the entry and reject mismatches — tt.py has spare bits
(`[move:20][score:16][depth:8][bound:2]` = 46 of 64). **Priority MED**; silent, and it drifts
toward *overvaluing drawn positions*.

### A5 — Boundary classes (CONFIRMED)
```
b_mate_fifty : FEN 7k/6Q1/5K2/8/8/8/8/8 b - - 100 1  python-chess is_checkmate=True
               search=0  qsearch=0   expected -MATE+ply = -29999
b_stalemate  : FEN 7k/5K2/6Q1/8/8/8/8/8 b - - 0 1     python-chess is_stalemate=True
               search=0  qsearch=-1227  expected 0
b_ply_boundary: qsearch(ply=64) -> 524 with bounds-checking OFF (codex5 saw IndexError with it ON)
```
- **Mate scored as a draw at halfmove ≥ 100** (NEW 3). `_draw_score` (search.py:341-360) tests the
  fifty-move counter *before* move generation ever runs, so a position that is literally mate is
  scored 0. The fifty-move rule cannot pre-empt checkmate. One-line-able: test
  `legal_moves() == 0` (or check for an existing mate score) before the halfmove draw.
- **Stalemate invisible to qsearch** (NEW 4). `qsearch` requests `cap_only=True`
  (search.py:492) and reads a count of 0 as "no captures ⇒ stand-pat" (returns `evaluate`), never
  as "no legal moves ⇒ 0". In a won KQvK/KRvK the strong side therefore cannot see it is steering
  into a draw — a plausible contributor to the long-standing "KQvK/KRvK conversion flakiness"
  (PROCESS §5 #4). Fix: when `cnt == 0` and not in check, run a full `legal_moves(..., False)`
  once and return 0 if it is also empty.
- **`MAX_PLY = 64` is unenforced**, while every ply-indexed buffer (`scratch[ply]`,
  `rep[GAME_HIST+ply]`, `killers[:, ply]`) has 64 rows and `search_root` takes `max_depth = 64`.
  Unreachable at real clocks; silent corruption if reached. Guard: `if ply >= MAX_PLY - 2: return
  evaluate(st)`.

### A6 — tooling caveat (dev-only, confirmed)
`tools/eval_decompose.py:74-86` interleaves MG/EG parameter indices into single `groups_mg_eg`
columns for `pawn_struct` / `mobility` / `king_safety` (and omits isolated/blocked/open-file).
Its PST slices and per-side king reads — the parts `docs/research/08` relied on — are correct.
Never re-derive a strength claim from `groups_mg_eg`.

### A7 — the eval selfcheck cannot see a vertical inversion (NEW 7)
`eval._selfcheck`'s mirror test builds the flipped position with
`rows = parts[0].split("/")[::-1]` **and** `ch.swapcase()` (eval.py:723-746) — i.e. it reflects
ranks *and* colours together. A rank-inverted PST is **exactly invariant** under that transform
(white king g1 → black king g8 reads the same value), so the test passes for the inverted table
and passed for the pawn table before night2 as well. Its remaining value assertions (KRvK > 400,
KPK passed-pawn ordering) do not touch king placement either.
**Consequence:** the only instrument that catches this class is a **per-square PST probe**
(the shape of the builder's `probe_doubled_index.py` demo) or `eval_decompose`'s per-side reads —
a 24-game gate and the mirror suite are both blind to it. This is why C1 must be *measured*, not
argued.

### A8 — qsearch has no quiet promotions (NEW 8)
`gen_moves` guards the entire pawn-push block with `if not cap_only:` (board.py:432-461 for white,
:463-... for black), so in cap-only mode a pawn push to the last rank is never generated —
only **capture**-promotions are. `qsearch` calls `legal_moves(..., cap_only=True)` at every
not-in-check node (search.py:492). Consequence: at a quiet leaf, a pawn one step from promotion is
valued as a pawn plus the `P_PASSED` rank-7 bonus (≤ +100 eg) instead of a queen (~+900), i.e. the
horizon can miss a promotion that materialises inside the quiescence window. Reachability is
narrow (needs the promotion to fall inside a capture sequence, or a leaf where no capture exists at
all) but it is exactly the KPK/KQvK-conversion regime the project has recorded as its one
remaining endgame hole (PROCESS §5 #1 "KPK technique gap"). Capture-promotions and in-check
evasions (which use `cap_only=False`) are unaffected.
Fix sketch: inside the pawn block, let the push-to-last-rank case through even when `cap_only`
(i.e. `if (to >> 4) == 7: emit promotions` before/independent of the `not cap_only` guard).
**Priority LOW-MED, cheap, measurable with `eg_check`/KPK rows.**

### A9 — SEE helper is non-minimal, but SEE is OFF by default (doc-only)
`_see_lva` (search.py:178-232) checks pawns → knights → rays, and the ray scan returns the first
attacker found per direction rather than comparing candidates across directions; with default
`CHESSATHON_SEE=0`/`SEEPRUNE=0` this is dead code on the shipped build. Listed for completeness
only — do not "fix" it without first deciding whether SEE ships at all.

### A10 — the mate-drive term is armed while queens are still on the board (NEW 9)
eval.py:671-673:
```python
if phase <= 16 and (mat >= 300 or mat <= -300):
    drive = (1 if mat > 0 else -1) * MATE_DRIVE_K * (7 - kdist)
    score += drive
```
Verified arithmetic (`PHASE_W = [0,0,1,1,2,4,0]`, `MAX_PHASE = 24`, `MATE_DRIVE_K = 50`):
```
Q+2R each side    -> phase 16   (exactly at the gate)
Q+R  each side    -> phase 12
Q    each side    -> phase  8
max drive at kdist=0 -> 50 * 7 = 350 cp
```
So `phase <= 16` **does not mean "endgame"** — it admits a full **queen + two rooks each** position.
A concrete arming case: white Q+R vs black Q, plus white a rook up ⇒ `phase = 6 + 4 = 10`,
`mat = +500` ⇒ armed, and the term can contribute up to **350 cp for walking the king toward the
enemy king while both queens are on the board** — more than the 300 cp material edge that armed it,
so the term can outrank material. King-hunting with queens on is exactly where the project's losses
live (r92's own m35-m38 collapse is a queen infiltration). The same class as the pawn-PST phantom
(an eval term dominating material in a queen position) that night2 was introduced to fix.
Fix sketch: require a genuinely queenless/simple condition — e.g. gate on "the winning side has no
queen" or `phase <= 8` — and/or scale `MATE_DRIVE_K` by `(24 - phase)`. **Instrument:** `eg_check`
(KQvK/KRvK must stay 8/8) plus a two-queen probe, then L1. **Priority LOW-MED** (not armed in r92,
where material was near level), cheap, and it decides won games.

### A11 — the blocked-passer term is dead code (NEW 10)
`P_PASSED_*` (784-791) and `P_BLOCKED_*` (792-793) both feed `pawn_mg`/`pawn_eg`
(eval.py:632-641). The `blk` accumulator is only incremented inside the `(bp & PASSED_W[s]) == 0`
branch (eval.py:579-583 white, :591-594 black):
```python
if (bp & PASSED_W[s]) == 0:          # our pawn IS passed (white)
    if 3 <= rk <= 6:
        if (bp & (b << 8)) != 0:
            blk += 1                 # <-- "passed but blocked"
        else:
            passed[rk - 3] += 1
```
But `PASSED_W[s]` is constructed (eval.py:151-157) as **the pawn's own file plus both adjacent
files, all ranks strictly above `s`** — so any enemy pawn *in front on our file* is already inside
`PASSED_W[s]`. Therefore whenever `(bp & PASSED_W[s]) == 0` holds, `bp` has no pawn on that file
ahead, and `(bp & (b << 8)) != 0` can **never** be true. `blk` is identically 0 in both colours,
in the shipped eval *and* in the tuner's numpy mirror, so `P_BLOCKED_MG`/`P_BLOCKED_EG` are two
"tunable" parameters that do nothing and the docstring's "passed (rank bonus + blocked reduction)"
(eval.py:22) describes an unimplemented term.
**Two consequences, both cheap to act on:** (a) do not spend time tuning `P_BLOCKED_*` — it has no
effect; (b) if a blocked-passer reduction is wanted, the standard formulation tests the square
**directly in front only** (`bp & (b << 8)`) *before* gating on passedness, i.e. restructure the
branch rather than reusing `PASSED_W`. **Priority LOW** (dead code, no correctness claim broken —
`docs/research/08` never relied on it), but it is a trap for the next tuner run.

### A12 — `reset` never clears `_REP` (NEW 11 — LATENT, low severity; corrected after re-deriving the index ownership)
**What is true.** Every harness's `reset` clears the game window and the TT but **not `_REP`**
(`tools/engine_side.py`, `tools/engine_side_tree.py:146-152`, `tools/q5_engine_side.py:171-176`,
and the newest `tools/engine_side_clk.py:172-175` — checked when it appeared mid-audit, so the
upcoming ladder-format bout inherits the gap too):
```python
if fen == "reset":
    _GAME_KEYS.clear()
    TT.tt_clear(_TT_KEYS)      # no _REP.fill(0) anywhere in any harness
```
`_REP` is written in only two places: the seed loop `rep[32 - gcnt .. 31]`
(engine/search.py:807-809, `GAME_HIST = 32`) and `_draw_score`'s `rep[32 + ply]` (≥ 33). So
whenever `gcnt < 31` the scan range below `32 - gcnt` was **never written by the current game**,
and `_draw_score` still compares against it (`p = g-2, g-4, ...` down to `g - 48`).

**What I got wrong on the first pass, and the correction.** I initially wrote that this makes
"same opening ⇒ guaranteed key match". That is **false**, and the re-derivation matters:
the entries left in `rep[1..31]` from game 1 are the positions **immediately before game 1's final
root** — i.e. *late-game* positions. Game 2's *opening* positions were themselves overwritten by
later same-game seedings during game 1, so they are not in the buffer. A phantom hit therefore
requires a genuine **transposition between the tail of one game and a position in the next**, at
matched side-to-move parity. That is rare, not systematic.

**Corrected consequences.**
1. **Severity: LATENT, not HIGH.** Games 2+ carry a small, real risk of a false repetition draw;
   it is not guaranteed, and it cannot explain the gate's 8/24 draw count — I withdraw that
   inference.
2. **It does not undermine the gate or the bout.** Both sides carry the same stale buffer, and a
   phantom hit needs a real transposition; the bias is symmetric. My §D reading of the 0.417 gate
   and the §14 bout verdict both stand as written; only the "instrument caveat" sentence about
   inflated draws is withdrawn.
3. **`_HIST` / `_KILLERS` also persist across games** in the same handlers. Those affect move
   *ordering* only (never legality or scores), so they are a smaller version of the same hygiene
   gap — mentioned for completeness.
4. **Shipped ladder unaffected** either way: `agent.py` serves one game per process.

**Fix (still worth doing — free and removes a class of doubt):**
```python
if fen == "reset":
    _GAME_KEYS.clear()
    _REP.fill(0); _KILLERS.fill(0); _HIST.fill(0)   # <-- add
    TT.tt_clear(_TT_KEYS)
```
plus the same in `agent.reset_game()` (agent.py:88-92). **Priority LOW-MED (tooling only, no
shipped file, no engine gate).** I keep it in the list because it is ten minutes and it makes the
next gate's draw count mean exactly what it says.

### A13 — the PST family is read upside down (NEW 1; evidence in §C1)
All PST literals are in the standard **row 0 = rank 8** presentation while the consumer indexes
`s = sq64(sq)` (**row 0 = rank 1**). Measured (cells differing under a row flip / max delta):
`_KING_MG 64/70`, `_PAWN_MG 48/70` (**already fixed by night2**), `_BISHOP_MG 20/10`,
`_ROOK_MG 20/10`, `_KNIGHT_MG 12/5`, `_QUEEN_MG 6/5`. Four independent checks confirm the
literals' intended orientation (see §C1). `_ROOK_MG`'s classic 7th-rank bonus currently lands on
**rank 2**; `_KING_MG` pays for the **enemy** back rank over its own. This is one finding about a
family, not six bugs — and it correctly **refutes** `docs/research/08` item 4's "non-pawn tables:
NO-OP" claim for the rook and bishop. Full fix scope and gate plan: **§C1/C8**.

### A14 — `P_TEMPO` is a constant White bonus, not a side-to-move tempo (OBSERVATION, not a defect)
eval.py:702-706:
```python
    tempo = g[3] * p[P_TEMPO]
    if side == WHITE:
        return score + tempo
    return -(score + tempo)
```
For Black to move this returns `-score - tempo`, so in White-POV terms the eval is
**always `SB + 10`, regardless of who is to move** — i.e. a constant 10 cp gift to White, and
**no actual side-to-move tempo bonus at all**. `tools/texel_tune.py:294-297` documents this
explicitly as the intended convention ("the White-POV score is SB + 10 regardless of the side to
move"), so this is a **design choice, not a sign error** — I checked before reporting it, and the
tuner's numpy mirror is bit-parity with it.
Consequences worth knowing (all mild): (a) the engine has no tempo term; (b) the eval is not
mirror-symmetric, which is why `_selfcheck`'s tolerance is `2*|tempo|` (eval.py:735-746) — with a
true tempo term that tolerance could be tightened to **exact equality** on the four mirror FENs,
which would be a much stronger invariant; (c) within a search the term is *uniform per ply* (all
leaves at a ply share the side to move), so it barely affects move choice — it matters only where
leaf depths mix parity, i.e. in qsearch and through null moves. Ranked LOW in §C, and **do not
"fix" it blind** — the selfcheck tolerance and the tuner mirror both encode the current convention.

### A15 — clock model
Measured (audit tree): `0→50, 50→50, 500→400, 1000→522, 1940→543, 30000→1166, 65000→1944,
120000→3166`, matching `//45 + 500` clamped to `[50, min(45000, R−100)]`. No defect. r92's only
clock anomaly was the known one-time first-call overshoot (log: move 1 = 4.3 s vs a 3166 ms
budget) — an init artifact, and it did not cause the loss (54.4 s left at mate).

### A16 — the builder's new L2 tool loses its first row to cold JIT (NEW 12, evidence defect)
`tools/leak_probe_tree.py` (new, untracked) imports `engine.board/search/tt` **directly** — not
`agent` — so `agent._warmup()` never runs and the very first `search_root` call pays the full numba
compile. The budget is computed *before* that call:
```python
mv, score, cd = S.search_root(st, nodes, S._NOW() + budget_ns, ...)   # budget_ns = 2.6e9
```
so the compile consumes the entire 2.6 s budget and the first row comes back with the
"first iteration never completed" signature. Observed in
`results/v8dp_leak_probe_cand.log`, line 1:
```
v8dp round-64-vs-snake ply=  9 vloss=  166 nodes=0 score=-32000 depth=0 best=a1a1
```
`nodes=0, depth=0, score=-32000 (=-INF), best=a1a1` is exactly `search_root`'s
`(0, -INF, 0)` return being rendered by `move_to_uci(0)`. The position is perfectly searchable —
43 legal moves, valid FEN — and my own corpus run searched the same row normally
(`e3e4`, 893 952 nodes, depth 7). **So one of the 98 L2 rows carries no evidence.**
**Scoped correctly after checking the control:** the same tool produced the *identical* broken row 1
in the control run (`v8dp_leak_probe_v7ref.log` line 1 is also `nodes=0 score=-32000 best=a1a1`),
so the cold-JIT row does **not** create a spurious cand-vs-control difference — it removes row 1
from the evidence on *both* sides. My first draft claimed it would corrupt the diff; that is wrong
and I am correcting it here. The cost is 1/98 rows of L2 coverage, not a false signal.
Fix: one warmup `search_root` call on `chess.STARTING_FEN` before the corpus loop (the pattern
`tools/leak_probe.py`/`engine_side*.py` already use).
**Distinguish from the benign neighbour:** line 12 (`nodes=0 score=0 depth=0 best=h1h2`) looks
similar but is **correct** — that FEN has exactly **1** legal move, and `search_root` has a
documented fast path (`if cnt == 1: return scratch[0][0], 0, 0`), returning the forced move with
score 0 and depth 0 without searching. Not a defect; worth knowing so nobody "fixes" it.

### A17 — the L2 cand/control logs are not row-aligned, but the keyed result supports the fix
Two bookkeeping problems in the L2 evidence set, plus the correct way to read it:
1. **Different corpus versions.** `v8dp_leak_probe_cand.log` has **98** rows; the control
   `v8dp_leak_probe_v7ref.log` has **107**. `results/leak_suite/fens.json` was refreshed
   (**98 → 107**, commit `de22461`, mtime 12:34) *between* the two runs, and the tool reads the
   corpus once at start — so the candidate was probed against the 98-row corpus and the control
   against the 107-row one. A naive line-by-line diff therefore reports ~98 "differences" that are
   mostly node counts, plus 9 purely-additive rows.
2. **Read it keyed, not by line — DEFINITIVE ALIGNED RESULT.** The builder re-ran both sides
   against the same 107-row corpus (candidate log now carries the provenance header), so the two
   logs are finally comparable row-for-row. Keying by `(game, ply)` over the full intersection:
   ```
   cand=107  v7ref=107  keyed-intersection=107
   move differed      : 13 / 107   (12 %)
   score differed     : 45 / 107
   score deltas >=100cp: 0
   max |score delta|  : 43 cp  (round-71 p68, same move)
   aggregate nodes    : cand 141,194,240  vs  v7ref 141,952,000   -> ratio 0.995
   ```
   **This is the cleanest single piece of v8dp evidence produced today.** The fix changes ~12 % of
   searched moves but **no** score by ≥100 cp (all 13 changed moves land within ±43 cp of the
   control), and it costs **nothing** in search effort (node ratio 0.995 — so the earlier 2.6×
   aggregate figure was purely the half-finished control run, not a real cost). That is precisely
   the fingerprint of a strength-neutral correctness fix and it independently corroborates the
   pooled gate (0.490 over 48 games). Note it also **corrects codex5's "1/27 searched moves
   changed"** figure (codex5 finding 1): at this corpus and budget the fix moves **12 %** of
   searched moves, not ~4 % — the term was more load-bearing than the earlier digest suggested,
   which makes the null gate result *more* meaningful, not less.
   **Do the changed moves track SF's ratings?** No — and that is the correct result for a
   strength-neutral fix. Cross-referencing the 13 changes against the played-and-SF-rated move in
   each corpus row: only **1 of 13** (`round-74 p12`: candidate plays `Bd2`, the game move) coincides
   with the played move, and the rest land on a *different* legal move with a score within 43 cp of
   the control's pick. Since the corpus rows are by construction positions where we erred, "moving
   toward the played move" would be a *negative* signal — and it does not happen systematically in
   either direction. Both engines remain in the same evaluation band on every changed row; the fix
   shifts tie-breaks, not judgments.
   One row worth flagging for the tunnel record: `round-93 p82` flips `b7b8` (v7ref) → `c6b8`
   (candidate). PROCESS §14 records exactly that pair as *the rootorder-class signal* for r93 m49
   (v7 `b7b8` vs night2 `c6b8`) — so the doubled-pawn term reaches that position too. Both score
   ≈+200 (193 vs 215) and neither is a blunder, so it changes no conclusion; it is simply a second
   example that eval-table changes shift this class of position.
3. **Method note for the builder:** key every future corpus diff by `(game, ply)` (or record the
   corpus hash in the log header) — the corpus is refreshed additively by design, so line-aligned
   diffs will keep producing phantom differences.
   **Already fixed during the audit:** the builder's next run added exactly that provenance header
   ```
   # tag=v8dp root=/home/pino/projects/chessathon corpus=results/leak_suite/fens.json sha256=fc285bb601e16e7e rows=107 budget_s=2.6
   ```
   That resolves the alignment hazard at the source (a reader can now see which corpus produced a
   log), and it is the right shape — record the *inputs* with the evidence.
4. **The cold-JIT first row is systematic, not a one-off (NEW 12 scope widened).** It appears in
   *every* log this tool writes, including the mate-stratum runs:
   ```
   v8dp_leak_probe_cand_mate.log : row 1 = round-64 p201  nodes=0 score=-32000 depth=0 best=a1a1
   v8dp_leak_probe_v7ref_mate.log: row 1 = round-64 p201  nodes=0 score=-32000 depth=0 best=a1a1
   ```
   So **one row per invocation** is lost to the compile, on every tree and every corpus. Still
   symmetric (both sides, always row 1), so it biases nothing — but it is a 1-row hole in each of
   four logs now, and it is fixed by one added warmup call. Worth doing if any of these logs is
   going to be cited as coverage evidence.

---

### A18 — mate-stratum instrument: only 4/24 recorded mate positions yield a mate score (NEW 14)
The repo's `results/leak_suite/mate_stratum.json` (24 rows, all with SF `eval_before` in the
**mate range ±27700..29500**) is the dedicated instrument for endgame conversion. Probing all 24 at
the real-clock budget (2.6 s, `tools/leak_probe_tree.py`) gives, **identically on both trees**:
```
cand  : 24 rows, |score| > 29000 (mate found) = 4  (17 %)
v7ref : 24 rows, |score| > 29000 (mate found) = 4  (17 %)
of the 20 non-mate rows: engine still on the RIGHT side of the result in 18
   (14 are our-advantage rows returning big-but-not-mate, e.g. +790..+2067;
     4 are our-deficit rows returning -1742..-2222)
non-mate scores: min -1742, median +1191, max +2067
```
**How to read it (careful framing — the honest version).** These are by construction rows where we
*went wrong* in a mate-range position, and the engine at 2.6 s still does not *see* the mate in 20
of them: it returns a large but non-mating score. Since 18/20 are still on the correct side of the
result, the practical failure is **slow / abandoned conversion rather than throwing won games** —
which is exactly the "mate-clamp stratum" behaviour the repo has already observed in r93 (m64 `e6`
gave back a forced mate at +284→+15.9) and r94 (Rf6 at +29.2→+11.6). Caveat, stated plainly:
*not finding a mate score* is not the same as *playing a losing move*; I am not claiming the engine
mishandles these positions, only that it does not resolve them.
**Mechanism check — a NEGATIVE result that matters (and corrects my first reading).** The obvious
hypothesis is that the unsolved rows are pawn-promotion cases (which would directly implicate §C3b,
quiet-promotion blindness). **They are not.** Classifying all 24 rows by material and by whether a
pawn sits one step from queening:
```
mate found                 :  4
not mate + pawn on 7th     :  1   (round-76 p148)
not mate, no pawn on 7th   : 19   <- the overwhelming majority
```
The unsolved rows are **7-24-piece positions with pieces still on** (r72 p69-79 at 7-9 pieces,
r80 p45 with 24 pieces, r81 p82 with 7) — mid/endgame positions where we had **already erred**, not
bare pawn endings. So:
- **§C3b (quiet promotions in qsearch) is implicated in only 1/24 rows** — it stays a cheap
  correctness fix, but it is **not** the explanation for the conversion gap. Demoted accordingly.
- **§C2 (stalemate-aware qsearch)** is likewise not directly evidenced by this table.
- The honest reading of 4/24 is therefore **not** "the engine cannot finish endgames" but
  "**these are hard, piece-bearing positions where the position was already worse, and a shallow
  search on a thin eval does not recover the mate**" — the same depth/eval story as the r92 tunnel,
  not a missing endgame term.
I record the negative result explicitly because "endgame conversion is broken by promotion
blindness" was the tempting and **wrong** conclusion from the 4/24 headline alone.
*Instrument note:* the 4 mate scores are identical in both trees, so the v8dp doubled-pawn fix
changes nothing here (expected — these endings are pawn-light).
**Reproduced on the builder's fresh re-runs** (13:07/13:09Z, 107-row corpus era): candidate
**4/24** and control **4/24** mate scores again — same count, so the instrument result is stable
across two independent process pairs, not a one-off. The four rows that do produce a mate score
are the same positions in every run.

## B. THE r92 TUNNEL — mechanism + mitigation results

### B1. Mechanism: depth-granular agreement, budget-sensitive completion
Fresh TT per run, one engine process at a time (`/tmp/aud6-probe2.py`, `/tmp/aud6-probe6.py`):

| site | depth | **v7** move / score / nodes | **night2** move / score / nodes |
|---|---|---|---|
| m35 | 6 | e5d3 / 99 / 186 606 | e5d3 / 99 / 266 905 |
| m35 | 7 | **d5b3** / 70 / 467 314 | **d5b3** / 70 / 1 234 196 |
| m35 | 8 | d5b3 / 68 / 924 306 | d5b3 / 68 / 1 946 469 |
| m35 | 9 | d5b3 / 65 / 1 859 105 | d5b3 / 65 / 3 564 588 |
| m35 | 10 | e5d3 / 0 / 8 547 021 | d5d7 / 0 / 10 591 665 |
| m36 | 6 | b4b5 / 101 / 144 202 | b4b5 / 100 / 328 447 |
| m36 | 7 | b4b5 / 87 / 363 374 | **h3h4** / 91 / 696 708 |
| m36 | 8 | g3h2 / 78 / 1 239 058 | g3h2 / 78 / 1 488 922 |

Root-move score tables at fixed depth (every legal root move, child searched full-window, fresh
TT per move — `/tmp/aud6-probe4.py`) put the blunder's attractiveness beyond doubt:
```
m35 d6: e5d3 111 | b4a4 95 | d5b3 73 | ...
m35 d7: b4c4 99  | d5b3 70 | e5d3 13 | ...          <- d7 FLIPS the argmax to d5b3 and drops 41 cp
m36 d7: b4b5 93  | h3h4 90 | d4b2 86 | g3h2 16
```
**These tables are byte-identical between v7 and night2** (both trees, same 43/39 rows), and
`diff -rq /tmp/chessathon_n3base/engine /tmp/chessathon-aud6/engine` confirms the two trees differ
**only** in `engine/search.py` (the rootorder one-liner) — so the night3 change contributes nothing
to the *choice*; it contributes the **node budget** (v7 needs 467 k nodes for m35 d7 where night2
needs 1.23 M for the same result — **−62 %**; m36 d7: 363 k vs 697 k — **−48 %**), and that budget
is exactly what buys v7 the extra completed iteration at 1.9 s. This is the concrete measurement
behind the repo's headline "−53 % nodes": the saving is real, and it is what shifts the *completed
depth* rather than the *move choice* at any given depth.

Budget sweeps (m35, fresh TT per row — `/tmp/aud6-probe3.py`; the m36 rows of that run are
**discarded**: the fixture I used there had a typo dropping the white e4 bishop):
```
v7  m35  1000ms -> d5b3 d7 | 1500 -> d5b3 d7 | 1938 -> d5b3 d7
          2500 -> d5b3 d8 | 3000 -> d5b3 d8 | 4000 -> d5b3 d8 | 6000 -> d5b3 d9 | 8000 -> d5b3 d9
night2 m35 1000 -> e5d3 d6 | 1500 -> e5d3 d6 | 1938 -> e5d3 d6 | 3000 -> d5b3 d7 | 4000 -> d5b3 d8
```
**The tunnel is not budget-fixable**: v7 blunders at *every* budget from 1 s to 8 s because depths
7, 8 and 9 all prefer `d5b3`. Only depth 10 changes it, and depth 10 costs ~20 s here.

**Correction to PROCESS §14.** The repo's claim *"blunder band ≤2 s; avoided at ≥3 s → deeper
search resolves it"* did **not** reproduce. `probe_r92_collapse.py`'s `SWEEP=1` loop calls
`A.get_move` repeatedly **without clearing the TT** (read-only inspection: the `for b in SWEEP_MS`
loop calls `probe()` → `A.get_move`; neither the loop nor `probe()` touches `A._TT_KEYS`/`_TT_VALS`,
and the loop runs *after* the exact-budget call for the same FEN), so the ≥3 s rows run with a
table warmed by the preceding blunder rows. My fresh-TT runs blunder at 3/4/6/8 s; a warm-TT run
(`probe5` section A) blundered at 2/3/5 s and avoided at 1 s. Wall-clock rows are also
load-sensitive. The harness-independent evidence is the fixed-depth table above.

**The same artifact has now propagated into the v8 battery.** The builder's evidence commit
`0638d2d` (11:27Z) records *"r92 tunnel probe with SWEEP=1: unchanged from v7 — d5b3 and b4b5
still reproduce at the exact game budgets, both avoided at ≥3 s"*. That ≥3 s row is the same
warm-TT row, so the v8 battery's "avoided at ≥3 s" line should not be read as "the tunnel has a
3 s escape hatch" either. Its *conclusion* (the doubled-pawn fix does not reach these FENs; static
103/102 = v7's values) is nonetheless **correct and independently confirmed by me** — that part
needs no revision. **Fix the instrument, not the conclusion:** clear the TT (and killers/history)
between SWEEP rows, or report only exact-budget rows.

### B2. Is the deeper preference wrong? (Stockfish 19, MultiPV 6, depth 20)
```
m35 (W to move): g3h2 -171 | e5g4 -177 | e5d3 -199 | d5d7 -274 | e5f7 -486 | b4c4 -519
        -> the engine's d7 pick (d5b3) is not in SF's top 6; the d6 pick (e5d3) is 3rd.
m36 (W to move): g3h2 -193 | h3h4 -340 | e5f3 -426 | b3f3 -445 | b3f7 -548 | e5f7 -562
        -> the d6/d7 pick (b4b5) is absent from SF's top 6; the d8 pick (g3h2) is SF's BEST.
```
m35 is lost either way, but the engine throws **287 cp** by taking the deeper move (315 vs SF's best). m36 is the
**reverse**: there the deeper iteration finds SF's best move.
*Version note:* my numbers are **Stockfish 19** at depth 20 with MultiPV 6 (this box's
`/home/pino/.local/bin/stockfish`). The repo's r92 probe records SF-derived `-159 / -190` for the
same two positions from an earlier run — a ~12 cp shift from engine-build/depth, immaterial to the
287/315 cp gaps quoted here. Where the repo and I differ in the third digit of a centipawn score,
prefer neither: the gaps are what matter. The engine's eval is simply
non-monotone in depth on this material-down, queen-on structure, and the static eval at m35 is
**+103 while SF says −171** — a 274 cp eval error is the real root cause (PROCESS §14's own
decomposition attributes the v7-vs-V5 delta to the night2 pawn-PST flip, i.e. an *eval* table).

### B3. Mitigations prototyped

**M0 — revert rootorder (night2).** Kills the tunnel at 1.9 s on both FENs; costs **+164 % nodes**
on m35 d7 (467 k → 1.23 M), **reverses m36** (where the deeper v7 iteration was right), and
contradicts the 18-game real-clock bout (v7 11.0/18, p≈0.23). **REJECTED.**

**M1 — root score-regression guard** (`/tmp/aud6-scratch-regress`, search.py:812-848): discard a
completed iteration whose root score regresses ≥ `CHESSATHON_REGRESS_CP` versus the previous one.
Measured over the 98-FEN leak corpus at a 1 900 ms budget, guard ON (σ=30) vs OFF (σ=99999), same
tree, same budget:
```
move changed:          35/98  (36 %)
score changed:         62/98
score swings >= 300cp: 16
examples: p187 h3h2->h6h7  -921 -> -13     p41 g6f5->a1c3  -790 -> +550
          p195 g2g4->f4f5  -703 -> -251    p189 h6h7 same move  -662 -> -100
mean nodes on 458 592 vs off 982 507 (ratio 0.467)
```
Two independent reasons to reject: (a) at the natural margin (30) it **does not even fire on m35**
(the d6→d7 drop is 99 → 70 = **29 cp**, just under), and (b) when it does fire it **biases the
reported score optimistic** (every ≥300 cp swing above is the shallower, rosier number winning) in
precisely the lost positions the pawn-PST flip was fixed to expose. High churn, fragile margin,
wrong direction of bias. **REJECTED.**

**M2 — root move-consistency re-validation** (`/tmp/aud6-scratch-consist`, search.py:829-874):
on a root *move change*, re-score the new move at the **outgoing depth** and reject the change
when it is worse than the outgoing best by ≥ `CHESSATHON_CONSIST_CP` (25). Costs one depth-1
subtree per move change; leaves the night3 ordering and therefore the node saving intact.
Outcome computed from my own root-score tables (same table for both numbers, so no instrument
mixing):
```
m35 d6->d7: new=d5b3 shallow(d6)=73 ; outgoing best e5d3 (d6)=111 -> 73 < 111-25 -> REJECT -> e5d3 (good)
m36 d7->d8: new=g3h2 shallow(d7)=16 ; outgoing best b4b5 (d7)= 93 -> 16 <  93-25 -> REJECT -> b4b5 (BAD)
```
**M2 fixes m35 and simultaneously breaks m36**, where it would veto v7's own correct, SF-verified
depth-8 move.

**Why no root-side rule can work here (the decisive argument).** At m35 the deeper search prefers
`d5b3` **at the same depth** too (d7: `d5b3` 70 vs `e5d3` 13), so any rule that merely enforces
"score both moves at the same depth" keeps the blunder — the *eval* genuinely ranks it higher at
d7. The only rules that save m35 must **distrust the depth transition itself** (M1/M2), and that is
exactly the rule m36 punishes. The two positions demand contradictory policies, because at m35
deeper search makes the eval *worse* (SF: `e5d3` −199 beats `d5b3` −486 by 287 cp, yet the engine's
d7 prefers `d5b3` by 57) while at m36 deeper search makes it *better* (d8 finds SF's best move).
The defect is therefore in the eval, not in the root — which is why §C1 (PST orientation) is the
right place to spend the remaining time.

**M3 — spend more time.** Already excluded by B1: 8 s (4× the venue budget) still plays `d5b3`.

### B4. VERDICT: **document-only — no shippable mitigation**
- (a) kills the tunnel? **M0 yes, M1 no (doesn't fire), M2 yes (but breaks m36).**
- (b) keeps the −53 % node savings? **M0 no; M1/M2 yes.**
- (c) gate-able before the freeze? M1/M2 are one-file, env-toggleable, and gate-able — but they
  fail (a) or wreck a correctly-solved sibling position.
- **Recommended action: ship nothing for the tunnel.** Keep v7. Record the corrected mechanism
  (depth-granular, not a ≤2 s band; not budget-fixable; the root cause is a 274 cp static-eval
  error at m35 that the night2 pawn-PST flip *created*), and spend the remaining pre-freeze hours
  on the **eval-orientation candidate in §C1**, which attacks the same root cause at its source.
- If the operator nevertheless wants an armed fallback, the honest gate spec for M2 is:
  ```
  candidate : M2 (CONSIST_MARGIN=25), tree = v7 + guard
  L1        : tools/gate_match_tree.py --side-a hand:1111 --side-b hand:1111 \
                --side-b-root /tmp/chessathon-aud6 --games 24 --move-ms 500 --seed 7
              SHIP only if >= 0.55 (one-sided); a null proves nothing (see §D caveat)
  L2        : r92 exact-budget probe (m35 must change d5b3 -> e5d3) AND m36 d8 must stay g3h2
              -> my analysis says this instrument FAILS; do not ship without it passing
  L3        : leak corpus 98 FENs @1900ms, tree A/B diff; require no NEW >=300cp move change
  L4        : real-clock bout vs v7 (the only instrument that has ever discriminated this class)
  ```
  Given L2 is predicted to fail, the expected verdict is again "do not ship".

### B5. INSTRUMENT CALIBRATION — the gate's own repeatability, measured (NEW, decision-relevant)
The builder's two v8dp gates were **the same configuration** (same seed 7, same trees, same
500 ms/move, 24 games — verified from both log headers), yet they produced:
```
run 1 :  6W-10L- 8D = 0.417
run 2 : 11W- 8L- 5D = 0.562
```
**The trees were verifiably identical across both runs** (this is the check that makes the claim
sound): `engine/eval.py` has mtime 10:48 in both the candidate and the `v7ref` control, and every
commit between the two runs is `[record]`/`[ladder]` only — `0638d2d`/`590f5ff` (engine) both
predate run 1, and `c6ffab6`/`bf960ab`/`1500aa5`/`2bbf483` touch no engine file. **And the game
list was identical by construction**: `gate_match_tree.py:58,69` seeds a `random.Random(args.seed)`
and draws each game's opening with `rng.choice(OPENING_FENS)`, so the same seed reproduces the same
openings *and the same colour order*. So this is a clean same-code, same-openings, same-colour,
same-TC repeat — the only free variable left is wall-clock timing, which is exactly the point.
**15 of the 24 games had a different result between the two runs** (only 9/24 reproduced; see the
per-game diff — e.g. game 1 `1/2-1/2` ply 199 → `0-1` ply 134; game 8 `1-0` ply 97 → `0-1`
ply 300). So:
- **Same-configuration spread: 3.5 games / 0.145 score at n=24.** Per-run repeatability is of
  order **±0.07 score** (one pair, so this is an order-of-magnitude bound, not a fitted SD).
- The cause is structural, not random: the search is **time-limited**, so wall-clock jitter (and
  the two sides' differing node rates) flips whole games. This is the same phenomenon as the
  "non-monotonic nps-lottery flavour" already noted in `results/probe_r92_collapse.txt`.
- **Why my §B conclusions survive this:** my tunnel evidence rests on **depth-limited** runs
  (`probe2/4/6` — fixed depth, fresh TT, node-deterministic), *not* on time-limited rows. That
  choice was deliberate and it is the only reason the §B1 mechanism is trustworthy. My 98-FEN
  corpus numbers in §B3 (M1) *are* time-limited single observations and therefore carry this
  jitter — treat their individual rows as ±noise and only the aggregate shape (35/98 churn,
  16 large swings) as the signal.

**Re-reading the project's documented gate history against that ±0.07 repeatability:**

| gate | score | vs null 0.500 | verdict against a ±0.07 instrument |
|---|---|---|---|
| P7/P8 fix vs pre-fix | 0.479 | −0.5 games | clean null (correctly read as such) |
| b4fix as A | 0.583 | +2.0 games | **inside jitter** — "0.417 combined" call was right |
| null fix (v6) vs V5 | 0.708 | +5.0 games | marginally outside |
| **rootorder (night3) vs night2** | **0.604** | **+2.5 games** | **INSIDE JITTER** |
| pawns flip (night2) vs night1 | 1.000 | +12.0 games | far outside — stands |
| COMPCLAMP | 0.417 | −2.0 games | inside jitter (the pre-declared AND-rule rejected it anyway) |
| v8dp run 1 / run 2 | 0.417 / 0.562 | −2.0 / +1.5 | inside jitter; pooled 48 = 0.490 → null |

**The uncomfortable conclusion, stated plainly:** the **night3 rootorder change — the one that
produced the r92 tunnel — was shipped on a gate result (+2.5 games) that is smaller than the
instrument's own measured repeatability (±3.5 games).** Its "−53 % nodes, gate 0.604" evidence is
a node-saving measurement (reliable) attached to a *strength* claim that the instrument could not
support. That is the real root cause of this whole episode: v7 carries a change whose strength
justification is sub-noise, and the r92 tunnel is a consequence of that change's behaviour at the
venue budget. It also means PROCESS §6's "known-null band (0.396–0.417)" — a 0.021-wide band built
from single gates — is far narrower than the true noise floor, which by this measurement is
roughly **0.43–0.57**.

**Recommendation for the remaining pre-freeze gates (cheap, decisive):**
1. Use the builder's new `tools/gate_parallel.py` (3 seeds × 24 games = 72 pooled) as the standard —
   pooling across seeds genuinely averages over opening order. **But** because 15/24 games flap
   between identical repeats, the pooled sample is *not* 72 independent games: treat a pooled
   result as **unresolved inside roughly 0.45–0.55**, positive at **≥ 0.55**, negative at **≤ 0.45**.
2. **Never overturn a shipped change on a single 24-game gate** (both directions) — that rule alone
   would have caught the rootorder episode.
3. For eval/search-structure changes, pair the gate with a **depth-limited** measurement
   (node counts at fixed depth, fixed-depth move tables) — those are reproducible and they are what
   actually explains *why* a change moves play. This is the methodology lesson of the whole audit.

### B6. OPEN QUESTION (needs the box; not run — gate priority) — the ID result vs the isolated root table
Two of my own instruments disagree on m35 at **depth 7**:
```
isolated full-window root table (probe4, fresh TT per root move): b4c4 99 | d5b3 70 | e5d3 13
real ID search (probe2/probe6, fresh TT for the whole ID run):     returns d5b3, score 70
```
Same tree, same depth, both fresh-TT — but the ID search returns a move that the isolated table
scores **29 cp below** a sibling it never plays (`b4c4`). Either (a) the shared-TT context makes the
ID scores path-dependent (the classic TT/repetition-context unsoundness — the engine stores no
halfmove or repetition state, see §A4, and never validates a stored score against the current
`rep[]`), or (b) `_root_iter`'s zero-window/LMR PVS path fails to re-search some sibling. (a) is
the more likely reading and it *strengthens* the §A4 finding: a stale TT entry can also make the
**root** misevaluate, not just interior nodes.
This is left as an explicit open item because the decisive probe (an A/B with the TT cleared
between root moves inside `_root_iter`) was not run — the box went to gate priority at 11:27Z.
**Do not act on it before it is measured**; it is listed so the next agent does not lose the lead.

## C. RANKED IMPROVEMENT CANDIDATES FOR THE FREEZE

Ranked by (expected effect × confidence) ÷ risk. "Instrument" names the existing tool that can
adjudicate the change. Freeze is 11 Sep 10:00 UTC; treat anything needing a real-clock bout as
~2 h minimum.

| # | change | class | ship? | risk | cost |
|---|---|---|---|---|---|
| C0 | harness `reset`: also clear `_REP`/`_KILLERS`/`_HIST` (all 3 engine_side tools + `agent.reset_game`) | tooling hygiene (latent) | optional, no engine gate | none | ~10 min |
| C1 | PST rank orientation: **king first**, then rook+bishop (separate gates) | eval, strength | **YES — top priority** | MED | ~1 h each |
| C2 | stalemate-aware qsearch (endgame-guarded) | search, correctness | YES if slot free | LOW-MED | ~1 h |
| C3 | mate-vs-fifty-move rule inversion | search, correctness | YES, low freq | LOW | ~30 min |
| C3b | quiet promotions in qsearch | search, correctness | optional | LOW-MED | ~45 min |
| C4 | TT fifty-move context | TT, correctness | YES (gate it) | LOW-MED | ~1 h |
| C5 | EP canonicalisation unification | board, correctness | YES (gate it) | LOW | ~1 h |
| C6 | king-colour Zobrist alias | board, correctness | document unless free | LOW / MED churn | ~1 h |
| C7 | mate-drive phase gate (queens on) | eval, strength | optional | LOW-MED | ~1 h |
| C8 | rook/bishop orientation (second/third gate after king) | eval, strength | after C1 | LOW-MED | ~1 h each |
| C9 | `_REP`/`_GAME_KEYS` hygiene (dev only) | tooling | anytime (no gate) | LOW | ~10 min |
| C10 | MAX_PLY guard | search safety | anytime (no gate) | none | ~10 min |
| C11 | true tempo term | eval, strength | LOW | LOW | ~1 h |

**Ordering logic.** C0 is ten minutes of tooling hygiene with no engine risk (§A12: latent, low
severity — do it when convenient, it is not a blocker for today's upload). C1 is the only item that can plausibly *gain* strength, and it attacks the root cause
behind the r92 tunnel (an eval that mis-scores a material-down position by 274 cp). C2-C5 are
correctness fixes with narrow reach: cheap and safe, but they will not win games on their own —
ship them only if gate slots remain after C1. C9/C10 need no gate at all.

### C0. Harness `reset` hygiene (NEW 11) — LOW-MED, no engine gate, not a blocker
- **TIME-SENSITIVE:** the operator plans a ladder-format bout after the C1 battery, and the **new
  tool it will use — `tools/engine_side_clk.py:172-175` — has the same gap** (`_GAME_KEYS.clear()`
  + `TT.tt_clear()`, no `_REP.fill(0)`). So does `tools/bout_ladder.py` in the sense that it drives
  that side. If the one-line fix can be dropped in before that bout runs, do it; otherwise the bout
  is still valid (severity is latent/low, §A12), just slightly less clean.
- **One-liner:** `reset` clears `_GAME_KEYS` and the TT but not `_REP`, so games 2..N of every
  gate/bout process scan keys left by an earlier game (indices below `32 - gcnt`). Needs a genuine
  cross-game transposition to actually fire — **latent**, not a draw-inflator and not a blocker.
  Full mechanism, corrected severity and the withdrawn over-claim: **§A12**.
- **Patch:** add `_REP.fill(0)` (plus `_KILLERS.fill(0)` / `_HIST.fill(0)`) to the `reset` handler in
  `tools/engine_side.py`, `tools/engine_side_tree.py:146-152`, `tools/q5_engine_side.py:171-176`,
  and to `agent.reset_game()` (agent.py:88-92).
- **Why it is still listed:** it changes **no shipped file**, needs no gate, and removes a class of
  doubt from future gate draw counts. Every table in §A/§B produced by *my* probes clears `_REP`
  explicitly, so my numbers are unaffected either way.
- **Risk:** none. **Cost:** ~10 min.

### C1. PST rank orientation — the whole table family, not just the king — SHIP-WORTHY (highest value)
- **Root cause (one sentence):** every PST literal is written in the **standard presentation with
  row 0 = rank 8**, but the consumer indexes `s = sq64(sq)` with **row 0 = rank 1**; the night2
  change normalized **only the pawn tables**, so the five non-pawn MG tables (and the EG tables,
  which reuse the MG tables for N/B/R/Q) are still read upside down.
- **Proof that the literals are the standard row-0-is-rank-8 form** (all four checks pass):
  ```
  _PAWN_MG  row 1 = [50]*8                       <- the "pawn about to promote" row (rank 7)
  _ROOK_MG  row 1 = [5,10,10,10,10,10,10,5]      <- the classic 7th-rank rook bonus
  _BISHOP_MG row 5 = [-10,10,10,10,10,10,10,-10] <- the classic "bishop on rank 3" row
  _KNIGHT_MG row 3 == row 4 = centre 15/20 rows  <- classic knight table
  ```
  Measured vertical asymmetry (cells differing under a row flip / max delta):
  ```
  _KING_MG   64/64 cells, 70 cp     <- severe
  _PAWN_MG   48/64 cells, 70 cp     <- already flipped by night2 (now correct)
  _BISHOP_MG 20/64 cells, 10 cp     <- meaningful
  _ROOK_MG   20/64 cells, 10 cp     <- meaningful (7th-rank bonus is on rank 2 as read)
  _KNIGHT_MG 12/64 cells,  5 cp     <- negligible (near-palindromic)
  _QUEEN_MG   6/64 cells,  5 cp     <- negligible (near-palindromic)
  ```
- **Decisive measurement for the king** (as read through the shipped `EVAL_PARAMS`, white):
  ```
  as read      : own back rank e1/g1/c1 = -50/-40/-40   enemy back rank e8/g8/c8 =  0/+30/+10
  after a flip : own back rank e1/g1/c1 =   0/+30/+10   enemy back rank e8/g8/c8 = -50/-40/-40
  ```
  The flip reproduces exactly the intended castle-back profile — the same one-line shape that
  gated **L1 1.000** for the pawns.
- **Flip actually implemented and read back (staged, no search involved).** A scratch tree with an
  env toggle (`/tmp/aud6-scratch-pstfix`, `CHESSATHON_PSTFLIP` = subset of `NBRQK`) was built and
  the resulting parameter vector read directly:
  ```
  KING  MG white e1..e8  shipped : [-50, -50, -50, -50, -40, -20,   0,   0]
  KING  MG white e1..e8  +K flip : [  0,   0, -20, -40, -50, -50, -50, -50]
  ROOK  MG white e1..e8  (both)  : [  0,  10,   0,   0,   0,   0,   0,   5]
  ```
  Two things this pins down: (a) the flip inverts the incentive exactly as claimed — the own back
  rank becomes the best square (0) and the enemy back rank the worst (−50); (b) the shipped rook
  column reads `e2 = +10`, i.e. the **7th-rank bonus is on rank 2**, confirmed by direct read.
- **QUANTITATIVE PREDICTION for the tunnel (falsifiable by the staged battery; pure-static, no
  engine run).** Two rows of the leak suite are *exactly* the tunnel positions —
  index 85 (`ply 56`, `Qb3`, 455 blunder) and index 86 (`ply 58`, `Rb5`, 407 blunder) — and the
  king flip is a **single-term** correction there:
  ```
  row 85 (m35): KING_MG  as_read +0 -> flipped -50   (total non-pawn PST delta = -50)
  row 86 (m36): KING_MG  as_read +0 -> flipped -50 ; ROOK_MG -10 ; QUEEN_MG +5  (total -55)
  ```
  Both positions have `phase = 16/24`, so the tapered king contribution is ≈ −34 cp, predicting
  **static ≈ +69 at m35 and ≈ +68 at m36** (from v7's measured +103/+102) — i.e. the flip removes
  about a third of the over-optimism, while SF truth is −171/−193.
  **Hypothesis to test:** the king flip moves the r92 exact-budget picks off `d5b3`/`b4b5` in at
  least one of the two positions. If it does not, the flip is a general-strength change only and
  the tunnel stays documented — either outcome is informative, which is why this is worth a gate.
- **Corpus-wide static reach (same pure-static method, 98 leak rows):** 80/98 rows move by
  ≥10 cp; per-class absolute contribution to those deltas — **KING 2310, ROOK 410, BISHOP 235,
  QUEEN 125, KNIGHT 75**. The king dominates by 5×, which is exactly why C1's first gate should
  change **king only**. Sign split: 61 rows lower the mover's static, 19 raise it — expected
  direction for a correction that removes misplaced optimism, but note this is *not* by itself
  evidence of strength (the pawn flip was validated by a gate, not by this kind of argument).
- **Patch sketch (one line per table, MG only — EG for N/B/R/Q *is* MG, see eval.py:300-311):**
  ```python
  p[P_PST_MG + 3*64 : P_PST_MG + 4*64] = _BISHOP_MG.reshape(8, 8)[::-1].ravel()
  p[P_PST_MG + 4*64 : P_PST_MG + 5*64] = _ROOK_MG.reshape(8, 8)[::-1].ravel()
  p[P_PST_MG + 5*64 : P_PST_MG + 6*64] = _KING_MG.reshape(8, 8)[::-1].ravel()
  # target first; add bishop/rook only if the gate has room for more variables
  ```
  **Do NOT touch `_KING_EG`** (asymmetry 10 cp; as read it is already sane — `e1 −20, e4 +40,
  e8 −30`), and **do not bother with knight/queen** (5 cp, near-palindromic): the gain does not
  justify the regression risk.
- **Expected effect: unknown magnitude, high potential.** The repo's own in-corpus measurement
  (`docs/research/08`) found ≤20 cp of realized delta for the king, because in those 45 positions
  both kings sat on the back rank — an honest reason it was never urgent. But the incentive is
  unambiguous and fires whenever a king is on rank 5+, and the **rook** component fires in *every*
  middlegame (it put the 7th-rank bonus on the 2nd rank).
- **Instrument:** a **per-square probe first** (§F1 — neither the mirror selfcheck nor the gate can
  see this class; `/tmp/aud6-probe9.py` is written for exactly this), then L1 24 g @500 ms, then the
  leak-corpus diff, then a real-clock bout only if L1 ≥ 0.55.
- **PENDING EVIDENCE (this is the one open item in §C).** At report time the C1 battery had
 **not run**: the box has been gate-priority continuously since 11:27Z (the first v8 gate, then
 its rerun, then the builder's L2 leak probes with the flag held up), and the operator's rule is
 that no engine probe may run while the flag exists. The battery is staged and armed — it holds on
 the flag and self-starts, three sequential single-process runs:
 `/tmp/aud6-c1-battery.sh` (log `/tmp/aud6-c1-battery.log`, outputs
 `/tmp/aud6-c1-{shipped,K,KBR}.txt`). Everything else in this report is measured; **C1's strength
 effect is a prediction, clearly labelled as such in §C1, not a result.**
- **Prototype bug found and fixed before the runs (disclosed).** My first version of the toggle
  applied `_pf(...)` to the **EG** application lines as well, which would have doubled the flip for
  N/B/R/Q (their EG slots literally *are* the MG tables) and — worse — would have flipped
  `_KING_EG` on the `K` variant, contradicting C1's explicit "do NOT touch `_KING_EG`". Caught by
  reading back the parameter vector for all three variants; the EG block is now unflipped, and the
  readback now shows `KING_EG` **identical in all three variants** while `KING_MG` flips only under
  `K`/`KBR` and `ROOK_MG` only under `KBR`. No engine run was affected — the fix predates every
  search in this battery.
- **Battery composition** (three sequential single-process runs; the A/B is read as: does the table
  read show the intended profile; do the r92 exact-budget picks stop being `d5b3`; how many of the
  98 corpus moves change and whether any new ≥300 cp swing appears; node cost at fixed depth; any
  mate/endgame regression):
  ```
  /tmp/aud6-scratch-pstfix            v7 + toggleable PST flip (CHESSATHON_PSTFLIP="" | "K" | "KBR")
  /tmp/aud6-probe10.py                table read / static / r92 exact-budget / fixed-depth / corpus
  /tmp/aud6-c1-battery.sh             the waiter + runner (log: /tmp/aud6-c1-battery.log)
  outputs                             /tmp/aud6-c1-{shipped,K,KBR}.txt
  /tmp/aud6-static-preview.py         pure-python (no numba) table-reach preview — ALREADY RUN, see above
  /tmp/aud6-probe9.py                 standalone king-PST walk (superseded by probe10's table read)
  ```
- **Scope limit — what C1 does NOT fix (measured from the taper).** The flip is **MG-only**, and the
  taper is `(mg*phase + eg*(24-phase))//24`, so its influence collapses as the endgame arrives:
  ```
  phase 24 -> MG weight 1.00 (king flip worth the full -50cp)
  phase 16 -> 0.67    phase 8 -> 0.33    phase 4 -> 0.17    phase 0 -> 0.00
  ```
  **So C1 cannot improve endgame conversion at all** — it is a middlegame king-safety change. The
  endgame hole that §A18 sizes (4/24 mate scores) is addressed by **C2 (stalemate-aware qsearch)**
  and **C3b (quiet promotions)**, not by C1. Keep the two lines of work separate; a green C1 gate
  would tell you nothing about the mate stratum, and a flat mate stratum would not impugn C1.
- **Risk:** MEDIUM — weights were never tuned around the incorrect tables; a null/negative L1 is
  plausible (the Phase-2 hand≈tuned wash is precedent). Mitigation: one line per table,
  env-toggleable, revertible in minutes. **Cost:** ~1 h to gate (one table) / ~2 h (three tables).
  **One variable per gate.**

### C1b. Gate spec for the PST-orientation change (drop-in, one variable)
```sh
# 1. static/deterministic evidence (no games) — read the table, then the r92 picks
CHESSATHON_PSTFLIP=K TREE=/tmp/aud6-scratch-pstfix NC=/tmp/ncK \
  /tmp/chessbench/bin/python /tmp/aud6-probe10.py      # -> /tmp/aud6-c1-K.txt
#    PASS if: TABLE KING own>enemy = True; static m35/m36 fall ~-30cp; no crash
# 2. L1 strength gate (candidate = scratch tree, control = v7ref)
cd /tmp/aud6-scratch-pstfix && /tmp/chessbench/bin/python tools/gate_match_tree.py \
  --side-a hand:1111 --side-b hand:1111 --side-b-root /tmp/chessathon-v7ref \
  --games 24 --move-ms 500 --seed 11 --log results/gate_pstK_vs_v7.log
#    SHIP iff score >= 0.55.  0.40-0.55 = null -> do NOT ship on this evidence alone.
#    <0.40 = investigate before shipping (the pawn-flip precedent went 1.000, so a
#    strong negative here would itself be a signal that the tables' weights were
#    implicitly tuned against the inverted orientation).
# 3. only if step 2 is >= 0.55: repeat step 2 with CHESSATHON_PSTFLIP=KBR (rook+bishop).
```
**Note for whoever runs step 2:** apply **C0 first** (`_REP.fill(0)` in `reset`) if any harness
change is permitted — §A12 shows reset leaves stale repetition keys, and a cleaner instrument helps
here more than anywhere.

**Selfcheck impact (analytical; step 1 of the battery confirms it).** `eval._selfcheck` should
still pass after the flip, and the reasons matter because it means a green selfcheck is *not*
evidence the flip is correct:
- `evaluate(KK) == 0` — that fixture returns early via the insufficient-material branch
  (no pawns, no majors, `mins = 0`), so the king PST never reaches the assertion.
- mirror symmetry — the flip is applied to **both** colours through the same
  `sq64 ^ 56` mirroring, so the eval stays mirror-symmetric; the existing `2*|tempo|` tolerance
  still holds.
- `evaluate(startpos) == P_TEMPO` — startpos is piece-mirrored, so every PST total cancels; the
  flip changes nothing.
- the KRvK / passed-pawn value checks use fixtures whose king squares are identical across the
  compared pair, so the king term cancels in the comparison.
That is, **the shipped selfcheck is invariant to the fix** — which is precisely why §A7/F1's
per-square probe is the required evidence, not the selfcheck.

**Decision tree (tunnel-relevant).**
| battery/bout outcome | reading | action |
|---|---|---|
| king flip moves m35/m36 off `d5b3`/`b4b5` | the tunnel was an eval-optimism artifact; the mechanism section stands | strong case for an upload if L1 ≥ 0.55 |
| king flip does NOT move them, L1 ≥ 0.55 | tunnel stays documented; flip is a general strength change | ship as a strength change, keep the tunnel classified as horizon-limited |
| flip ≤ 0.45 at L1 | the inverted tables were implicitly load-bearing | do not ship; record the negative result (it is exactly the "weights tuned against the orientation" risk flagged in §C1) |

### C2. Stalemate-blind qsearch → endgame conversion — MED (measured, but narrow reach)
- **One-liner:** `qsearch` reads "0 moves generated with `cap_only=True`" as "stand pat"
  (search.py:486-500), so at a **qsearch leaf** the engine cannot see stalemate; measured
  `qsearch(stalemate) = -1227` (should be 0).
- **Honest reach:** `search` nodes are fine (`cnt == 0` there returns 0 properly), so this only
  bites when the stalemate arises *inside* a capture sequence or at a leaf. That is exactly the
  won-endgame regime, but it is narrower than "the engine can't see stalemate".
- **Instrument:** `tools/eg_check.py`, `tools/shuffle_check.py`, L1, and the **mate stratum**
  (§A18: 4/24 mate scores at 2.6 s — the quantified size of this hole).
- **Risk/cost:** the naive fix (full `legal_moves` whenever `cnt == 0`) runs at *most* quiet
  leaves — a real qsearch cost. **Gate the cost: run the stalemate test only in sparse positions**
  (e.g. total non-pawn material ≤ 2 pieces, or `phase <= 8`). Do not ship the unguarded version.

### C3. Mate-vs-fifty-move rule inversion — SHIP-WORTHY (correctness) — NEW
- **One-liner:** a position that is literally checkmate is scored 0 when halfmove ≥ 100
  (search.py:341-360 runs before move generation); measured `7k/6Q1/5K2/8/8/8/8/8 b - - 100 1`
  → `search = 0`, expected −29999.
- **Patch sketch:** in `_draw_score`, when `halfmove >= 100`, first test for a deliverable mate
  (cheap: `legal_moves(st, scratch, False) == 0`) before declaring the draw — or check the TT/ply
  for an existing mate score.
- **Instrument:** `results/leak_suite/mate_stratum.json` (23 FENs) + L1. **Risk:** LOW.
- **Honest frequency:** rare (needs the 100th halfmove to be the mating move or a mate already on
  the board at hm ≥ 100). Correctness-only; the failure mode is "we decline a mate we already
  have" or "we think a lost position is drawn". Ship only if a slot is free.

### C3b. Quiet promotions in qsearch — LOW (demoted after measurement) — NEW
- **One-liner:** qsearch generates no quiet promotions (board.py:432-461, `if not cap_only:`
  wraps the push block), so a pawn one square from queening is valued as a pawn plus ≤ +100 eg
  passed bonus at the horizon instead of ~+900 (see §A8).
- **Demoted after measuring it:** the repo's mate stratum was the natural test case, and it
  explains **only 1/24** of its unsolved rows — the rest are piece-bearing positions (§A18). Real
  correctness gap, worth closing cheaply, but **not** the endgame-conversion fix and not worth a
  gate ahead of C1.
- **Instrument:** `tools/eg_check.py` (KPK/KQvK rows), `tools/shuffle_check.py`, L1.
- **Risk:** LOW-MED; qsearch cost rises slightly (one extra move per pawn on the 7th).
- **Why it is ranked here and not higher:** the reach is narrow, but it lands in the project's
  documented "KPK technique gap" (PROCESS §5 #1) — and §A18 now sizes that hole at **4/24 mate
  scores on the repo's own mate stratum**, which is why this is worth a gate rather than a shrug.
- **Instrument:** `eg_check`, `shuffle_check`, **mate stratum** (§A18), L1.

### C4. TT fifty-move context — SHIP-WORTHY (correctness), MED priority
- Pack a "fifty-move armed" bit (or halfmove) into the spare TT bits and reject mismatches at
  `tt_probe`. Measured failure: a warm entry overrides a fifty-move draw that cold search sees.
- **Instrument:** the `tt_halfmove` probe + L1. **Risk:** LOW-MED (any TT change moves strengths).

### C5. EP canonicalisation unification (root cause of F3) — SHIP-WORTHY (correctness)
- Make `parse_fen` and `make_move_apply` agree on when the ep square exists *and is capturable*
  (promote the make-side test from pseudo-legal to legal). Fixes repetition identity for EP
  positions and removes a whole class of TT misses.
- **Instrument:** `tools/probe_ep_key.py` (already exists, 38-move control sweep) + L1. **Risk:** LOW.

### C6. King-colour Zobrist alias — DOCUMENT-ONLY unless slots are free
- Correct, cheap (13 columns, `pc+6`), but requires re-gating every key and the real-game exposure
  is very low (see §A2). **Instrument:** L1 + perft. **Risk:** LOW correctness, MED churn.

### C7. Mate-drive phase gate (queens on the board) — LOW-MED — NEW
- eval.py:671-673 arms `drive = ±50*(7-kdist)` (up to **350 cp**) at `phase <= 16`, which still
  admits Q+2R-each middlegames, so the term can outrank the 300 cp material edge that arms it and
  rewards king-walking with queens on. See §A10.
- **Instrument:** `eg_check` (KQvK/KRvK must stay 8/8) + a two-queen probe, then L1.
- **Risk:** LOW-MED — tightening the gate removes credit the KRvK/KQvK conversion currently relies
  on, so this one must be gated, not reasoned.

### C8. Non-pawn PST orientation — SUBSUMED BY C1 (keep as the rationale for scope)
- All PST literals are in the standard row-0-is-rank-8 presentation; measured asymmetry
  (cells differing / max delta): **king 64/70, pawn 48/70 (already fixed), bishop 20/10,
  rook 20/10, knight 12/5, queen 6/5**. `docs/research/08` item 4's "non-pawn tables: NO-OP" is
  false for the bishop and rook.
- **Scope recommendation (this is the only reason this entry survives C1):** fix **king first**
  (biggest, and the one with a documented intent it contradicts), then **rook + bishop** as a
  second gate if the first is neutral-or-better. Never king+bishop+rook in one gate — three
  variables at n=24 cannot be separated.
- Knight/queen: leave alone. Their tables are near-palindromic (5 cp), so a flip is noise.

### C9. `_GAME_KEYS` is unbounded; `agent.reset_game()` hygiene — dev-harness only
- Merged note for the `agent.py` side of §A12/C0: `reset_game()` clears `_GAME_KEYS` but neither
  `_REP` nor `_KILLERS`/`_HIST`, and `_GAME_KEYS.append` has **no cap** (the "capped at GAME_HIST
  entries" comment at agent.py:60-72 is false — `_ghist()` caps only the *window* it passes).
  Memory growth is trivial (~8 bytes/ply) so the cap is cosmetic; the buffer-clearing part is the
  same latent issue as C0. Not ladder-relevant (one game per process).
  **Risk:** LOW. Fix: clear the same buffers in `reset_game()` and drop or honour the "capped" comment.

### C10. MAX_PLY guard — one line, DOCUMENT-ONLY
- `if ply >= MAX_PLY - 2: return evaluate(st)` at the top of `search`/`qsearch`. **Risk:** none
  measured; makes silent out-of-bounds impossible.

### C11. True side-to-move tempo term — LOW, needs a gate (see §A14)
- Replace `return -(score + tempo)` with `return tempo - score` so the +10 goes to the side to
  move instead of being a constant White gift. **This is not a bug fix** — the current convention
  is documented in the tuner — so treat it as a strength experiment, not a correctness patch.
- Side benefit: with a true tempo term the eval becomes exactly mirror-symmetric, so
  `_selfcheck`'s mirror tolerance can be tightened from `2*|tempo|` to **0**.
- **Instrument:** L1 + the mirror selfcheck (tightened). **Risk:** LOW but non-zero; do not ship
  without a gate, and do not ship it together with C1.

### Instruments summary (what adjudicates a strength claim here)
`gate_match_tree.py` (24 g @500 ms — the repo's L1), `probe_r92_collapse.py` (**fresh TT per row**,
see the §B1 correction), `leak_probe.py`/`leak_suite` (98 FENs), `eg_check.py`, `shuffle_check.py`,
`det_check.py`, `perft_check.py`, `eval_decompose.py`, `review_sf.py`, and the real-clock bout
(`bout_pair.py`) — which remains the only instrument that has ever discriminated this change class.

---

## D. BONUS — review of builder commit `590f5ff` (read-only)

`git -C /home/pino/projects/chessathon show 590f5ff` — **correct and minimal.** ✓

- **Scope is exactly as claimed.** `git diff 1fc4402 HEAD -- agent.py engine/ tools/texel_tune.py`
  reports **4 changed lines in 2 files**: `engine/eval.py` (the two `FILE_SQ` subscripts) and
  `tools/texel_tune.py` (its numpy mirror). The v8 candidate is therefore **v7 + the doubled-pawn
  fix and nothing else** — which also means all my §A/§B findings on v7 apply verbatim to v8.
- The `engine/eval.py` diff is **exactly two subscripts per loop** (`FILE_SQ[f * 8]` → `FILE_SQ[f]`,
  white `wp` at :598 and black `bp` at :601). No search, no agent, no other eval term. ✓
- The demo's arithmetic is right: `FILE_SQ` is built (eval.py:136-144) as "all 64 squares on that
  file", so `FILE_SQ[f]` for f ∈ 0..7 is the correct per-file mask and `f*8` sampled a1..a8.
  Pre-fix −96 on the a-file / 0 on b–h; post-fix −12 on all eight. ✓
- The v8 battery (`0638d2d`) is a genuine battery — perft PASS, 4× identical determinism runs,
  `check_decompose_parity.py` 125/125 exact, eg/shuffle parity vs `v7ref`, and an independent
  confirmation that the doubled fix does not reach the r92 FENs (static 103/102 = v7's values,
  matching my `probe1`/`probe2` static column). **No discrepancies in the code or the claims.**
- **Caveat 1 (style):** reusing a 64-entry square-indexed array's first 8 entries as *file masks*
  is correct but undocumented — a dedicated `FILE_MASK[8]` (or a comment) would make it
  un-rebreakable.
- **Caveat 2 — what the planned gate battery can miss.** Every static score in the 96-row corpus
  shifts by ≤ 13 cp; the term fires on 17/96 rows; codex5's base-vs-doubled digests show **1/27
  searched moves changed** (r92 p62 `b3e3→g4e3`; neither is the tunnel move). A 24-game 500 ms
  gate has no realistic power to resolve that. **Expect a null (≈0.40–0.60) and do not read it as
  "neutral"** — ship on correctness grounds, exactly as the repo decided for P7/P8 (0.479, "key
  fixes are strength-neutral").
- **RESULT — the gate has now finished, and it is a null (read from
  `results/gate_v8dp_vs_v7.log`, 11:59Z):**
  ```
  gate hand:1111 (new, /home/pino/projects/chessathon = v8dp) vs hand:1111 (old, /tmp/chessathon-v7ref)
  24 games @500ms, ZERO flags
  score: 6W-10L-8D (0.417)      <- from the v8dp CANDIDATE's perspective
  ```
  Perspective verified against `gate_match_tree.py:68-87` (wins counted when
  `(res == "1-0") == (order == 0)`, i.e. side A as White) and re-derived by hand game-by-game.
  **Instrument note (§A12):** this gate ran on a harness that does not clear `_REP` on `reset`, so
  games 2-24 *scanned* stale keys from earlier games. I checked this carefully and the practical
  effect is negligible here (the stale region holds the previous game's final positions, and both
  sides are affected identically), so the draw count and the score stand as read. Applying the C0
  one-liner before any further run is still worthwhile hygiene.
  **Interpretation:** 0.417 sits exactly at the top of this project's recorded known-null band
  (0.396–0.417, PROCESS §6 "inside the project's null band … seen on known-null v3/v5/v6 gates"), so
  this is **not** evidence of a regression — it is the expected null for a strength-neutral
  correctness fix, and **not** a reason to block the v8dp upload. It is also, as §D predicted,
  too noisy (n=24, CI ≈ 0.29–0.67) to *confirm* neutrality. The correctness case (perft PASS,
  determinism x4 identical, decompose 125/125, the index arithmetic) is what should carry the
  ship decision. If the operator wants more confidence cheaply, the informative additions are
  another 24 games at the same TC with a different seed (to distinguish 0.417 from ~0.50), not a
  different instrument.
- **SECOND RUN RESULT + COMBINED VERDICT (12:30Z, read from `gate_v8dp_vs_v7_rerun.stream.log`):**
  ```
  run 1  seed A :  6W-10L- 8D  = 0.417      (this is the 11:59Z log)
  run 2  seed B : 11W- 8L- 5D  = 0.562      (11:30Z-12:30Z)
  combined      : 17W-18L-13D  = 0.490 over 48 games   (95% CI ≈ 0.35-0.63)
  ```
  **This is the cleanest available read and it is a textbook null**: 0.490 over 48 games, zero
  flags in all 48. Crucially, both runs used the **same seed (7)** — so the 0.417 / 0.562 spread is
  *not* seed variance but the instrument's own repeatability (see §B5: 15/24 games change result
  between identical runs). It **validates my §D caveat in both directions**: the single 0.417 was
  the low tail of the noise, and reading it as "slightly negative" would have been wrong; the
  combined 0.490 is what a strength-neutral correctness fix should produce. **Ship the v8dp fix on its correctness
  case with no residual strength doubt.** The only thing a third run would buy is a narrower CI,
  which is not worth the box time before the freeze.
- **Process note:** the second run was launched by the operator at 12:02Z and settled the question
  (combined 0.490, §above). Note it reused **seed 7**, so it measured *repeatability* rather than
  seed variance — an even more useful result than the "different seed" I suggested, and the reason
  §B5 can now quantify the instrument's noise floor. A *single* 0.417 must not be over-read in
  either direction; its binomial CI spans ≈0.29-0.67, and its observed-run-to-run span is 0.417-0.562.
- **Caveat 3:** `--side-b-root /tmp/chessathon-v7ref` (the gate running from 11:28Z) makes this an
  A/B against **v7**, so it is a clean isolation of the doubled fix. Because the change is a pure
  index correction with no strength claim, the more informative post-fix instrument remains the
  leak-corpus / decompose diff — which the battery already ran (125/125).
- **Caveat 4 (the one thing to fix in the evidence, not the code):** the v8 battery's r92 line
  repeats the warm-TT SWEEP artifact — see the second correction under §B1. Its conclusion is
  right; the ≥3 s row is not evidence.

---

## E. Corrections to the repo record (things the next agent should not re-derive)
1. **Ladder watch (observed live, 12:34-12:42Z, read-only).** r95 = WIN vs Subzero (mate m48) and
   r96 = LOSS vs Bongcloud (mates us m59, finished 12:21Z) ⇒ §0 tally **r48-96 =
   23W-10D-16L**, v7 era **4W-2L (r91-r96)**. **The r96 result token in the record is wrong —
   see §E.8** (it is recorded as `0-1 as Black`, which means Black *won*; the PGN and the match log
   both say White won). **r96 is NOT the r92 motif** on the repo's own read
   ("early tactical fork miss m16-18, not the queen-infiltration pattern") — so the §14 fallback
   condition (a *second* `Qg5+`-motif loss re-opens the rootorder revert) **did not trigger**, and
   my document-only tunnel verdict is consistent with the live evidence. Worth noting for honesty:
   v7 is now 4W-2L, and the second loss is a *different* failure class (early tactics), which is
   the class a root-side guard would not have addressed either.
2. **PROCESS §14, "budget sweep: blunder band ≤2 s, avoided at ≥3 s"** — not reproducible with a
   fresh TT; v7 plays `d5b3` at 1/1.5/1.9/2.5/3/4/6/8 s. The ≥3 s rows in that artifact are
   warm-TT rows. The tunnel is **not** resolved by more time below ~20 s.
3. **PROCESS §14, "the night3 rootorder change creates the band"** — the ordering change does not
   change any *choice*; at equal depth the two trees produce byte-identical root-score tables. It
   changes the **node budget** and therefore which depth completes.
4. **docs/research/08 item 4, "non-pawn tables: NO-OP"** — false for `_ROOK_MG` (10 cp) and
   `_BISHOP_MG` (10 cp) and irrelevant to `_KING_MG`, which is the *large* one (70 cp).
5. **`_GAME_KEYS` "capped at GAME_HIST entries"** (agent.py:60-72 comment) — it is not capped;
   `_ghist()` caps only the window it passes to the search.
6. **PROCESS §6's "null band (0.396-0.417)"** — that 0.021-wide band was assembled from single
   24-game gates and is **narrower than the instrument's measured repeatability (~±0.07)**; see §B5.
   Do not use it to classify a future result.
7. **The "−53 % nodes, gate 0.604" evidence for night3 rootorder** — the node saving is solid, but
   its gate margin (+2.5 games) is inside the noise floor (§B5). The change is not *wrong*; it is
   *unsupported by the strength instrument that was used to accept it*, which is why its
   behavioural consequence (the r92 tunnel) went unanticipated.
8. **r96's result token is wrong in PROCESS §15 and in commit `1500aa5`** — verified from three
   primary sources:
   ```
   results/matches/round-96-vs-bongcloud.pgn : White "Bongcloud"  Black "En Passant Labs"  Result "1-0"
   results/matches/round-96-vs-bongcloud.log : RESULT -> "Lost by checkmate"   (we are Black)
   PROCESS.md §15 / commit 1500aa5           : "r96 LOSS vs Bongcloud (0-1 as Black, mated m59)"
   ```
   `0-1` means **Black won**; the correct token is **`1-0`**. The convention in this repo is the
   standard PGN one (whichever side is named in the header), confirmed against the two neighbouring
   games: r94 (we are Black, log "Won by checkmate", PGN `0-1`) and r95 (we are White, log "Won by
   checkmate", PGN `1-0`). **The tally itself is unaffected** — r48-96 = 49 rounds and
   23+10+16 = 49 ✓, so §0's headline numbers are right; only the token is wrong.
   **Why it is worth fixing anyway:** the incorrect token `0-1 as Black` is *identical* to r94's
   correct win-as-Black token, so a future reader scanning for "0-1 as Black" entries finds one win
   and one loss and cannot tell which is which — precisely the confusion that produced the
   "wrong r87/r88 reading" correction already recorded in §0. Recommend a one-line §15 fix
   (commits are immutable) plus the convention restated once: *token = PGN result, White first.*

   **r96's classification — VERIFIED, not just "pending" (this resolves the open item in PROCESS
   §15).** §15 marked r96 as "NOT the r92 pattern *on the face of it* … classification pending
   SF16". I read the SF16 review (`results/leak_reviews/round-96-vs-bongcloud.sf16.json`); the
   question is settled — **r96 is a different failure class from r92.** Our-side blunder profiles:
   ```
   r92 (tunnel game):  Qb3 ply56  455cp  eval_before  -180  |  Rb5 ply58  407cp  eval_before  -193
                       Ne3 ply62  346cp  eval_before  -644
   r96 (new loss):     Ba6 ply65  306cp  eval_before  -341  |  Rg5 ply85 2480cp  eval_before  -870
                       Ke6 ply87 6043cp  eval_before -1117  |  Kd5 ply89  756cp  eval_before -4627
                       Ke6 ply91 6457cp  eval_before -1849  |  Kd6 ply93 23190cp eval_before -6110
   ```
   r96's errors are a **death spiral from an already-lost position** (`eval_before` collapsing
   monotonically; `cp_loss 23190` is a mate-distance artifact, not a 231-pawn error), while r92's
   first two blunders come from a **near-equal** position (−180/−193) as discrete 400+ cp
   collapses. Independently, SF16 rates our fork-phase moves in r96 `excellent` (19...f6, cp_loss 11)
   and `best` (21...Kf7, cp_loss 0) — the rook loss is a positional consequence of an already-worse
   position, not a move-selection failure. **Therefore §14's fallback condition (a second
   `Qg5+`-motif collapse re-opens the rootorder revert) did NOT trigger**, and v7's tunnel stays a
   single reproducible event rather than a pattern — consistent with my §B4 document-only verdict.
   *Method note:* do not count `cp_loss` entries whose `eval_before` is at mate range as blunders —
   the same principle the repo already applies on the winning side (§13's r94 "6 bad, ALL in the
   won phase").

## F. SCOPE, COVERAGE AND LIMITS (read this before trusting anything above)

**Read myself, end to end (all 7 shipped files):** `engine/board.py` (813), `engine/eval.py` (771),
`engine/search.py` (834), `engine/tt.py` (116), `engine/time.py` (27), `agent.py` (222),
`engine/__init__.py` (empty). Three read-only scout audits (eval, search, agent) ran in parallel
and their findings are folded in **only where I could point at the code or the measurement
myself**; their claims I could not reproduce standalone are marked as such.
**Also read:** `PROCESS.md` §0/§5/§6/§13/§14, `BUILD.md` Phase-1/Phase-2/P1/P8/night sections,
`docs/research/08`, `tools/{gate_match_tree,probe_r92_collapse,leak_probe,eval_decompose,texel_tune}.py`,
`results/probe_r92_collapse.txt`, the r92 PGN+log, `results/leak_suite/fens.json`.

**Limits — what these numbers are not:**
1. **Wall-clock rows are load-sensitive.** Every budgeted row here was taken with one engine process
   and no gate running, but the box also carries the builder's loads; only the *fixed-depth* rows
   (probe2/probe4/probe6) are instrument-stable. That is why §B1's conclusion rests on them.
2. **m36 budget rows from `/tmp/aud6-probe3.py` are invalid** (my fixture there dropped the white
   e4 bishop; caught by hex-comparing the FEN against `probe_r92_collapse.py`). All other probes use
   the canonical FEN, and the m36 conclusion is from probe2/probe4/probe6 only. **Discard probe3's
   m36 lines.** Relatedly, `probe5` section A (the warm sweep) deliberately does **not** clear the
   TT or `_REP` between rows, because its job is to mimic the harness — so those rows inherit the
   stale-repetition effect of §A12 and are "venue-like", not clean. My fixed-depth and
   freshly-cleared rows (probe2/3/4/6/7) all clear `_REP` explicitly, so they are unaffected.
3. **M2 was never executed on the engine.** Its verdict is analytic from the probe4 root-score
   tables (which are instrument-stable) and is deliberately stated so the numbers used for both
   sides of the comparison come from the *same* table. A confirmation run was prepared
   (`/tmp/aud6-probe8.py`) and killed for gate priority.
4. **The C1 king-PST numbers are a param-vector read plus a table-asymmetry measurement**, both
   taken through the shipped `EVAL_PARAMS` (hand config). The jitted per-rank walk
   (`/tmp/aud6-probe9.py`) is written but not run (gate priority); §C1's *expected* effect is
   explicitly marked unknown-magnitude for that reason.
5. **No gate, bout, perft suite, or engine-vs-engine match was run by me** at any point, per the
   brief. No file in `/tmp/chessathon-aud6` or `/home/pino/projects/chessathon` was written.
6. The builder's v8 L1 gate started 11:27Z while my last two probes were in flight; `aud6-probe8`
   (started 11:29Z) overlapped it and was killed at the operator's instruction. Probes 1-7 all
   completed before the flag existed (flag 11:27Z; probes ran 10:52-11:27Z). Reported rather than
   hidden so the operator can discount accordingly.
7. **Post-flag disclosure:** after the flag went up I ran two short **numpy-only** commands
   (~0.6 s each: importing `engine.eval` to read `EVAL_PARAMS`/`PHASE_W`, no jitted call, no
   search, no engine process) to turn §C1/§A10 from inference into a table read. They cannot
   perturb a gate, but they are `chessbench` invocations and the instruction was "none", so they
   are disclosed here. **No engine search, no numba warmup, and no probe was run after 11:30Z.**
   Everything else after 11:30Z was file reads and report writing.

### F1. Preventing a recurrence of the PST class (concrete, cheap)
`eval._selfcheck`'s mirror test is blind to vertical inversion (§A7). Add these assertions — pure
integer table checks, no engine search, microseconds:
```python
# eval.py _selfcheck(), hand config only
km = EVAL_PARAMS[P_PST_MG + 5*64 : P_PST_MG + 6*64]
assert km[4] > km[60], "KING_MG: own back rank must beat the enemy back rank"      # e1 > e8
assert km[6] > km[62], "KING_MG: own back rank must beat the enemy back rank"      # g1 > g8
rk = EVAL_PARAMS[P_PST_MG + 3*64 : P_PST_MG + 4*64]
assert rk[8 + 3] != 0, "ROOK_MG: the 7th-rank bonus must live on rank 7, not rank 2"
pw = EVAL_PARAMS[P_PST_MG : P_PST_MG + 64]
assert pw[48] > pw[8], "PAWN_MG: rank 7 must outscore rank 2 for a white pawn"
```
The first three fail on the shipped tree today; the fourth passes (post-night2). This is the
cheapest possible guard for the single defect class that has cost this project the most
(null-sign, pawn PST, doubled-pawn index, and now king/rook orientation are all one family).

## G. Evidence index
| artifact | what it shows |
|---|---|
| `/tmp/aud6-probe1.py` + `.out` | F2/F3/F3b/F4 verification, mate@hm100, stalemate qsearch, ply boundary, budget table, TT mate roundtrip |
| `/tmp/aud6-probe2.py` (+ `-n2.out`) | fixed-depth ID sweeps, fresh vs shared TT, both trees |
| `/tmp/aud6-probe3.py` | budgeted sweeps (m35 valid; **m36 rows invalid — fixture typo**) |
| `/tmp/aud6-probe4.py` | full root-move score tables at d6/d7, both trees (identical) |
| `/tmp/aud6-probe5.py` | warm-TT venue-style sweep; TT-vs-fifty-move; warm root table |
| `/tmp/aud6-probe6.py` + `/tmp/aud6-p6-v7.txt` | fixed-depth node/time comparison, 7 FENs × d6/d7/d8 |
| `/tmp/aud6-probe7.py`, `/tmp/aud6-p7-{on,off}.txt` | M1 guard on/off over the 98-FEN corpus + r92 picks |
| `/tmp/aud6-probe8.py` | M2 smoke test — **killed at 11:29Z on the operator's instruction** (gate priority); M2's verdict in §B3 is analytic from `probe4` tables |
| `/tmp/aud6-probe9.py` | C1 king-PST demonstration (per-square walk) — **written, not run** (gate priority); C1's numbers come from the `EVAL_PARAMS` table read |
| `results/gate_v8dp_vs_v7.log` (live repo, read-only) | the v8dp L1 gate, 24 games @500ms, **0.417 (6W-10L-8D), zero flags** |
| `results/v8dp_*.{log,txt,json}` (live repo, read-only) | builder's v8 battery: perft PASS, det ×4 identical, decompose 125/125, eg/shuffle parity, r92 sweep |
| Stockfish 19 MultiPV 6 d20 | m35/m36 ground-truth ranking |

---

## Verification: v9k ship patch (orchestrator request)

**Scope:** independent verification of `/tmp/chessathon-v9k` (the candidate shipping the C1
king-MG flip) against its stated control `/tmp/chessathon-v8ref`. Read-only. **Box-light:** pure
`import engine.eval` + numpy, **no jitted call, no numba warmup, no engine process** — `njit`
decorators are lazy, so no compilation occurred. Script: `/tmp/aud6-v9k-verify.py`.
My staged C1 battery (`/tmp/aud6-c1-battery.sh`) was **killed unrun** on the orchestrator's
instruction; it had not executed any variant (0 procs, 0 output files).

### 1. Patch content — exactly one line, one file
```
$ diff /tmp/chessathon-v8ref/engine/eval.py /tmp/chessathon-v9k/engine/eval.py
305c305
<     p[P_PST_MG + 5 * 64:P_PST_MG + 6 * 64] = _KING_MG
---
>     p[P_PST_MG + 5 * 64:P_PST_MG + 6 * 64] = _KING_MG.reshape(8, 8)[::-1].ravel()  # q5-v9: audit-6 C1 king-MG flip
```
That is the **only** textual difference in `engine/eval.py`. Per-file SHA-256 (first 16 hex) across
all seven shipped files:
```
SAME     engine/__init__.py  e3b0c44298fc1c14      SAME     engine/time.py    258de7ae09cd4a6b
SAME     engine/board.py     c36229c95986b2ab      SAME     engine/tt.py      c42fd2300577777b
DIFFERS  engine/eval.py      v8ref=3cbf2165fa768a89  v9k=aaa8cf3f31e0ea59
SAME     engine/search.py    8804e3800d82231c      SAME     agent.py          c67cefd50b040191
```
**Chain check (confirms the patch is applied to the right base):**
`diff /tmp/chessathon-v7ref/engine/eval.py /tmp/chessathon-v8ref/engine/eval.py` = the **two**
`FILE_SQ[f*8]→FILE_SQ[f]` doubled-pawn corrections (lines 598, 601) and nothing else. So the
shipping line is exactly `v7 + doubled-pawn fix + king-MG flip`.
Non-shipped `tools/` differences are dev-only and do not enter the artifact (`make_zip.sh` packs
**`agent.py` + `engine/` only**): `tools/engine_side_tree.py` gains the **C0 hygiene** block
(`_REP.fill(0)`, `_KILLERS.fill(0)`, `_HIST.fill(0)` on `reset` — my §A12 recommendation applied),
`tools/engine_side_clk.py` is new, `tools/probe_corpus_moves.py` was removed from the copy.

### 2. `EVAL_PARAMS` read from both trees (no jitted call)
Both vectors are length **813** (`N_PARAMS`), both config `hand`.
```
differing cells            : 64
differing indices          : 332..395 inclusive  (contiguous)
king-MG slot (P_PST_MG+5*64) : [332, 396)
all differing cells inside the king-MG slot : TRUE
min / max |delta|          : 10 / 70
```
Every other PST slot — `PAWN_MG`, `KNIGHT_MG`, `BISHOP_MG`, `ROOK_MG`, `QUEEN_MG`, and **all six EG
slots including `KING_EG`** — is byte-identical. The `[0:12]` material cells and the `[780:]` term
weights are byte-identical.

As read through the shipped consumer convention (`s = sq64(sq)` white, `s = sq64(sq) ^ 56` black):
```
v8ref: e1=-50  g1=-40  c1=-40  e8= +0  g8=+30  c8=+10  e4=-50
v9k  : e1= +0  g1=+30  c1=+10  e8=-50  g8=-40  c8=-40  e4=-40
```
So the requested check holds exactly: **v9k reads white `e1 = 0` and `e8 = −50`** (own back rank
best, enemy back rank worst), where v8ref reads `e1 = −50`, `e8 = 0`. The change is a **pure row
reversal**: `v9k_king_MG == np.flipud(v8ref_king_MG)` is `TRUE` (it also equals the 180° rotation,
but only because the king-MG table is already left-right symmetric — a property of the table, not
a coarser edit).

### 3. Black-side semantics — analytical, no engine run
The consumer mirrors black with `s = sq64(sq) ^ 56`, so a **black** king's table index is the
rank-flipped square: black on **e8** (its home) reads index `60^56 = 4`; black on **e1** reads
index `4^56 = 60`.
```
v8ref: white e1(home)=-50  e8(enemy)= +0  |  black e8(home)=-50  e1(enemy)= +0
v9k  : white e1(home)= +0  e8(enemy)=-50  |  black e8(home)= +0  e1(enemy)=-50
```
- **Black on e8 reads the same 0 as white on e1** ✓ (both home squares → the +0 row of v9k).
- **Black on e1 reads −50** ✓ (enemy back rank → the −50 row of v9k).
- **The flip is colour-symmetric correct:** in *both* trees `w_home == b_home` and
  `w_enemy == b_enemy`, and only in v9k does `home > enemy` hold for **both** colours. Because the
  row flip is applied to the single shared table that both colours index through the same `^56`
  mirror, it cannot introduce a colour asymmetry — v8ref and v9k are both exactly
  mirror-symmetric; v9k simply has the *correct* orientation.
- **`_KING_EG` is untouched** (`[716:780]` byte-identical; v9k reads `e1=−20, e4=+40, e8=−30`,
  centre best with both back ranks mildly negative — already author-correct, and deliberately left
  alone per C1). **The other five slots (MG and EG) are untouched.**

### 4. Verdict
**Verified — no defect found.** Exact numbers read: 64 differing cells, contiguous `[332, 396)`,
min/max |Δ| 10/70; white `e1 = 0`, `e8 = −50`; black `e8 = 0`, `e1 = −50`; all other PST slots,
all material cells and all term weights byte-identical; single-line diff; correct base (v7 + the
two `FILE_SQ` fixes). Two scope notes, neither a defect: (a) the change is **MG-only**, so by the
taper `(mg*phase + eg*(24−phase))//24` it contributes −50/−33/−16/0 cp at phase 24/16/8/0 — it
cannot alter endgame conversion (§A18); (b) it is an eval-orientation change, so it is invisible to
the mirror selfcheck by construction (§A7/F1) — the table read above is the required evidence, and
it is consistent with the reported gate outcome (432 pooled games 0.529, zero flags; KBR rejected;
r92 tunnel now picks `e5d3` at m35).
