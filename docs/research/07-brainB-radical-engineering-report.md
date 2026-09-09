# Chess brainstorm — AGENT B: meta / wild / different-approach probes

Mission: radical, rules-legal, ≤1-day, head-to-head-testable probes vs the
shipped V5 engine, grounded in repo + ladder corpus. Everything below is
READ-ONLY analysis; no repo files were touched. Analysis scripts used:

- `/tmp/corpus_stats.py`, `/tmp/corpus_spend.py` (run with
  `/tmp/chessbench/bin/python`) — derived from `results/matches/*.pgn`.

---

## 0. Corpus evidence digest (r49–r71, 13 rated games with full %clk)

Ladder facts (PROCESS.md §6 P4): rank 336/387, ~45–50 rated rounds left
(brief says 45–50; PROCESS says "~45–50 rated rounds remain"), uploads
≤6/day until Sep 11 11:00, latest-passing upload plays. Every game starts
from a **curated injected FEN** (all 13 games have `[SetUp "1"]` +
non-start FEN, mid-book position ~move 6–9, clock set to 120+0.5
regardless of history — r48 log confirms).

**Our time usage (V3–V5 era, per-move SPEND derived from %clk):**
- Spend avg 1.1–3.6 s/move, max 2.5–7.7 s. End-of-game clock unused:
  r62 **97.9 s**, r61 88.7, r67 70.0, r70 67.3, r65 55.1, r69 50.3,
  r68 42.7, … r71 15.4, r64 14.9, r66 7.4, **r63 3.7 s**. Median ≈ 55 s
  of 120 s unused. We routinely leave half the clock on the table.
- Long games drain us to single digits on the venue box: r63 (95 plies)
  ended at 3.7 s, r66 (151) at 7.4 s, r64 (224!) at 14.9 s. r64 was a
  112-move marathon vs a weak bot where we were winning +1.5 from ply 76
  and still lost. The venue box runs ~1.5× slower than budget (r63
  replay: move-1 4.9 s vs 3.2 s budget, PROCESS P2) — geometric R/45 is
  calibrated for the dev box, not the venue.

**Opponent time profiles (%clk):**
| Opponent (r) | result | our spend | opp spend | opp end clock |
|---|---|---|---|---|
| AlphaGambit 49 | L | 2.2 avg | 4.4 avg, 6.6 max | 15.5 s |
| Veritys 50 | L | 2.1 | 3.0, 6.2 | 18.8 s |
| CrimsonBot 61 | D | 2.9 | 4.5, 5.7 | 63.8 s |
| Forking squad 62 | W | 1.1 | 2.1, 3.6 | 57.8 s |
| Ultimate32 63 | D | 2.9, 7.7 max | 2.2 | 41.3 s |
| Snake 64 | L | 1.4 | 1.4, 6.0 | 14.0 s |
| Magnus 65/71 | W/W | 2.1/3.0 | 2.7/2.1 | 31.6/52.6 |
| Benko 66 | W | 2.0 | 1.7 | 27.3 s |
| Chess 67 | W | 3.6 | 2.2 | 90.8 s |
| Rook&Roll 68 | L | 2.5 | 1.8 | 69.3 s |
| Stockfish 69 | W | 1.9 | 1.9 | 46.4 s |
| **KingsGuard 70** | L | 2.2 | **4.2 avg, 19.8 max** | **4.4 s** |

- **Nobody has flagged yet, but the window is real:** KingsGuard — the
  strongest opponent in the corpus (deep-ponder signature: 19.8 s opening
  burn, then 3.5 s+inc recovery) — mated us with **4.4 s left ≈ 8.8 moves
  of runway** at +0.5 s inc. r64 (Snake) both sides at ~14 s after 224
  plies. Weak/mid bots spend 1.4–4.5 s/move and survive; only
  ponder-heavy bots self-endanger, and only in long games.
- **Opponent opening spends:** nobody saves for the end; everyone spends
  2–4.5 s flat with 0.5 inc. Elo-correlated with spend (KingsGuard 4.2 avg
  is the outlier high).

**Loss anatomy (our 5 losses since r48):**
- r48 SkyLab: stateless-era shuffle into mate (22 king/rook/bishop
  shuffles, fixed 1.3 s/move) — FIXED by Phase 4, do not revisit.
- r64 Snake: won +1.5 at ply 76, fork at ply 76, Q-endgame perpetual
  failed, lost at ply 224 on the clock edge.
- r68 Rook and Roll: even at ply 49, **−3 by 57, −10 by 65** — material
  leak in the Q-ending transition (conversion-failure class).
- r70 KingsGuard: **eval-skew loss** — V5 rated the knight-down
  post-Na2/Qxb2 position −92..−104 cp when it should be −250..−350
  (sims-v5 Quirk 1); believed it was near-equal, played on, collapsed.
- Wins (r62/65/66/67/69/71): all conversions of small material edges
  against blundering bots. r66 we won **while finishing −7 material**
  (Benko hung pieces); r67 mated in 17 down a queen (−15 material!);
  r63 held a −2 draw by repetition. **Weak bots blunder big, late.**

**Draws:** r61 dead-equal threefold created by THEIR king shuffle; r63
−2 hold by repetition. No draw offers exist in the protocol (get_move
only returns moves) — the flag game is the only clock lever, and it is
asymmetric: we never flag by design, opponents sometimes nearly do.

---

## 1. Legality verdict on the "meta" questions (read this first)

- **What can agent.py read at init/match time?** Only: env vars the
  harness sets (we observe `CHESSATHON_INC_MS`, `NUMBA_*`, our own
  `CHESSATHON_*` toggles), the start FEN, `time_left_ms`, and files we
  ship in the zip. **No network, no process arguments visible, 60 s init
  (r48 log showed 90 s budget, 3.1 s used — init is ~97% idle).** The
  competition may announce pairings, but a match-time process cannot see
  them: no network. Identity-based adaptation is impossible *live*; it
  would require shipping an opponent database as data.
- **Is shipping an opponent-game database legal?** Gray. ORIGINALITY.md
  permits shipped *data*: books, tablebases, our own model weights, and
  training data is unrestricted *for training*. A scraped PGN corpus used
  as a runtime lookup is not a book, a tablebase, or trained weights —
  closest reading: NOT clearly permitted. **Ask Pino before any
  opponent-data ship.** A book *derived by our own analysis* sits in the
  allowed "books as data" slot (research 03 §1 confirms polyglot = fine,
  weights = our own scores).
- **In-game, position-based adaptation is unconditionally legal** —
  zero shipped data, pure code: observe the opponent's *moves*, classify
  from their move quality, adapt policy. No identity, no database.
- **Pondering is explicitly allowed** (box: "pondering allowed"); compute
  between `get_move` calls is our own core's time. Current process model:
  module-global TT/killers/hist persist; `reset_game()` clears only the
  game-history window between games (dev harness sends `reset`; the
  competition harness's inter-game lifecycle is unknown — design
  defensively for both).
- **Syzygy 3–4 piece (4.2 MB) is permitted shipped data** and the
  libraries (`chess.syzygy`, `chess.polyglot`) are in the base image;
  research 03 §6 already decided "ship 3–4 piece WDL+DTZ — always". It
  was never executed; backlog #1 (KPK) is the live consequence.

---

## 2. Ranked probes

### P1 — SPEND OUR CLOCK: real-TC time policy (spend-more + endgame reserve) ★★★★★

*Idea.* Replace the R/45+inc budget with a real-clock policy: spend
R/35–R/40 with a hard reserve floor (keep ≥ 20–25 s when ≤ 6 men and
winning) and a ~1.5× venue-slowness headroom factor on the deadline. Add
an "endgame conversion reserve" (never let a winning K+P/R ending run
below ~15 s). Fold-in knobs: 2× TT size (1<<22 → 1<<24, 64→256 MB,
still ≪ 2 GB) and root-stability tie-break (Quirk 2: prefer the previous
iteration's PV move within a small score delta).

*Why it wins games (evidence).* We leave 50–98 s unused in 9/13 games
(r62 ended 97.9 s; spend avg 1.1 s/move). KingsGuard's Elo edge is
correlated with spending 2× our time (4.2 vs 2.2 avg). Depth instability
(Quirk 2) is a *depth* problem — more time is the direct fix, and the
r70/r71 replays prove move choice varies with the box's nps. Meanwhile
the current policy is over-conservative on the short end and unsafe on
the long end: the venue box runs ~1.5× over budget (r63 move-1 overrun,
PROCESS P2), and long games vs weak bots drain us to 3.7–14.9 s
(r63/64/66/71) — the never-flag property holds only as an average, not
under venue jitter and 95–224-ply games. A reserve cap converts "nearly
flagged" into "guaranteed conversion depth".

*Legality.* Pure code, our own policy. Nothing ships. 100% clean.

*Implementation (~half day + gate time).* `engine/time.py` budget
function + deadline headroom in `agent.py`; TT size constant; root-stability
selection in `search_root` (keep previous best within ε). Use the existing
env-toggle A/B pattern (`CHESSATHON_LMR`/`CHESSATHON_EVAL_GATE` precedent).

*Test design.* Head-to-head V5-policy vs new-policy at TWO regimes:
(i) existing 500 ms gates as a no-regression floor (Quirk 2 probes from
`results/sims-v5/` re-run: r70 p28, r71 p16 fixed-budget flips), and
(ii) **full 120s+0.5 clock sims** (`tools/local_game.py` + engine_side
harness — the regime that matters; aspiration was rejected at 500 ms and
may be *kept* at real TC, backlog #3). Replay r63/r64/r66 at exact clocks
and require single-digit remainders to stay ≥ reserve. SPRT at the event
clock, elo0=0/elo1=10 per research 02.

*Risk.* LOW — pure policy, revertable, zero eval/search semantics change.
Biggest failure mode: spending more without converting it to depth
(venue box is slow); the headroom factor + sims catch it before upload.

---

### P2 — SHIP THE 3–4 PIECE SYZYGY TBs (4.2 MB), probe root + near-leaves ★★★★☆

*Idea.* Download 3–4 man syzygy WDL+DTZ (~4.2 MB) *outside the repo*
(dev-time data, exactly as ORIGINALITY.md permits for books/TBs), ship in
the zip, probe at root + at search leaves when men ≤ 4: WDL for
win/draw/loss, DTZ for zeroing progress when winning. KBNvK, KQvKR,
KPKR (longest 4-piece mates 33–43) become perfect; KPK (the documented
gap, BUILD.md "OPTION A") closes; "material decides by 300 plies" rules
are trivially satisfied by DTZ progress.

*Why it wins games (evidence).* Backlog #1 (KPK both colours) is
explicitly the one documented endgame hole left; KRvK/KQvK flakiness
under load is backlog #4; our two post-stateful losses r64/r68 both died
in endgame *transitions* (fork leak at ply 76, Q-ending −10 by 65); wins
r69/r71 were clean conversions of exactly the ≤4-man material classes
the TBs make bulletproof (r69: Q-vs-K-ish after Rxd6/cxb4/b-pawn run).
Elo upside is larger for a shallow engine than Stockfish's published
−7/+2/+13 (research 03 §2): our gap-to-perfect in these endgames is
huge (KPK never converts at 300 ms). Direct win-currency: weak bots play
on into these endgames constantly (r62–r71 all ended ≤12-material
configs); converting them instead of shuffling/drawing flips ~1–2 ladder
games/week.

*Legality.* Explicitly permitted data (research 03 §0; ORIGINALITY books
+ tablebases = shipped data; `chess.syzygy` is a base-image *library*).
Probe code is ours. Downloaded files stay out of git (sign a manifest in
BUILD.md; make_zip.sh picks them up).

*Implementation (~half–1 day).* Mirror 3–4 piece rtbw+rtbz (~4.2 MB,
research 03 sizes verified 2026-09-07), `chess.syzygy.open_tables(dir)`;
probe at root before search (pure-Python probe ~100 µs+ — root only, not
qsearch per research 03 §2); WDL at leaves near depth cap. Fifty-move
awareness: prefer DTZ moves; cursed-win awareness for any 5-piece we
later add.

*Test design.* Existing `tools/eg_check.py` suite extended to KPK both
colours (the failing case today), KBNvK, KQvKR, KPKR, KPvKP opposition,
stalemate traps (research 03 §6 list). Then head-to-head V5 vs V5+TB at
500 ms AND full-clock sims; also 300-ply/material-rule simulated
acceptance (assert material preserved + zeroing progress, not just mate).

*Risk.* LOW-MED. Pure addition; probe wiring can only help or be inert.
Risks: TB probe bug at a critical node (gate catches), DTZ-vs-WDL subtlety
(cursed wins), and 4.2 MB of zip budget (trivial). This was *already
decided* in research 03 and never executed — the cheapest done-decision.

---

### P3 — PONDERING between moves (opponent-clock exploitation) ★★★★☆ (highest raw upside, highest engineering risk)

*Idea.* After `get_move` returns, spawn a background search on the
predicted opponent reply (standard ponder: search the position after the
most likely reply — test captures/checks first, then root-PV opposition;
with the game-history window extended by our move + their predicted
reply). When the real `get_move` FEN arrives, if it matches the pondered
position, hand the search a warm TT + ready PV and verify on the real
deadline; else discard and search fresh. Use private scratch arrays
(`_SCRATCH/_SSCRATCH/_REP/_NODES` are module-global and would race) and a
private TT for the ponder thread; merge on match. The existing search is
already abortable mid-iteration (ctypes monotonic callback, deadline
checked every 1024 nodes) — a pondering thread with a far deadline can be
stopped at the next `get_move`.

*Why it wins games (evidence).* Every opponent move is 1.4–4.5 s of free
CPU we currently idle (KingsGuard gave us 19.8 s on one move). For a
depth-limited engine, effectively doubling our move time is the largest
single Elo lever available in the box. It also *reduces* Quirk-2 flip
instability (deeper = stabler) and synergizes with P1 (pondering harvests
the waste the policy leaves). The ladder's curated FENs start mid-book,
so ponder positions are diverse — fine, the mechanism doesn't need
opening theory.

*Legality.* Explicitly allowed ("pondering allowed"). All our code, our
core, our clock. Reset-safety: `reset_game()` must also kill the ponder
thread; design for both competition lifecycles (same process across games
= thread must die on `reset`; fresh process = nothing to do).

*Implementation (1 day+).* Threading wrapper in `agent.py`; private
buffers; TT merge policy; predicted-reply generation (use previous
`search_root` PV + tactical fallback); ghist extension for the pondered
position must include BOTH our moved position and their reply so the
repetition window is correct on hit. Determinism caveat: pondering makes
replays nondeterministic-ish (whose CPU arrives first) — replay tooling
must clamp or disable it for exact-clock forensics (keep an env toggle).

*Test design.* Extend the engine_side harness with opponent-think sleeps
(simulate 2–5 s opponent clocks), gate pondering vs non-pondering at real
120+0.5 clock; require ≥ the non-pondering result with zero
flags/illegals; verify a warm-TT hit path returns within the budget even
when the box is slow. Re-run the sims-v5 replay battery with pondering OFF
to prove the baseline path is bit-identical.

*Risk.* MED-HIGH. Threading + numba + shared TT = the classic
heisenbug zone; a race that corrupts the TT costs a ladder game, not just
a gate. Mitigation: private buffers everywhere except the shared TT
(merge, don't share), lock-free by construction, gate first. This is the
one probe where "gamble an upload near the freeze" is a real question —
sequence it after P1/P2, and only if the gate is decisive.

---

### P4 — FIX THE QUIRK-1 EVAL SKEW (material-compensation audit) ★★★★☆

*Idea.* Targeted audit of the mobility/activity/pawn-structure terms vs
material in semi-closed piece-down positions. The Na2/Qxb2 line from r70:
reproduce, bisect eval terms, identify what over-credits ~200 cp, fix the
specific term (anchor: piece-down in semi-closed structures should read
−250..−350).

*Why it wins games (evidence).* r70's loss anatomy is a *belief* bug, not
a search bug: V5 thought it was near-equal while a clean knight down and
played on into a collapse; sims-v5 Quirk 1 is the measured signature
(−92..−104 at depth 6–10). This skew is active in every game where we're
piece-down in such structures: it degrades our defensive play *when
losing* (we don't know we're losing) and lets us misjudge compensation
*when winning* (we may dodge or enter wrong trades).

*Legality.* Pure code. 100% clean.

*Implementation (half day).* Reuse `tools/probe_*` infra; a feature-
ablation probe over the r70 position (disable each eval term, measure
delta vs the −250..−350 reference); fix the responsible term with a
regression guard. Do NOT re-tune (Phase-2 trauma: tuning is not the
default lever) — this is a specific measured bug, not a fitting run.

*Test design.* Regression probe on the r70 position (must read
≤ −250 at depth ≥ 6); PGN-scan our own losses for piece-down eval
signatures; then the standard 500 ms + full-clock gates, and specifically
re-sim r70 to confirm the collapse line is avoided at the decision ply.

*Risk.* MED — eval touch is psy-risky after Phase 2, but scoped to one
measured term with a hard regression assertion. Revert if the gate shows
any wash.

---

### P5 — WEAK-BOT ADAPTIVE POLICY (in-game strength estimator) ★★★☆☆

*Idea.* Classify the opponent in-game from their *move quality*: keep a
rolling count of their moves that lose ≥ 80 cp vs our root score at the
time. After ~6–8 observed moves, branch policy:
- **Weak** (≥ 2 blunders): when we're equal/winning → prefer
  simplification toward ≤4-man technical endgames (they misplay them —
  pair with P2's TBs: simplify INTO tablebase range); when losing →
  **keep material on the board and play on** (their blunder rate makes
  −2..−7 non-terminal; r66 we won *while −7*, r67 mated down a queen,
  r63 held −2).
- **Strong** (≤ 1 blunder): standard solid play; simplification only
  when provably winning; accept draws.

*Why it wins games (evidence).* The corpus is an 8–1 win/loss against
blundering bots and 0–3 vs non-blundering ones (r49/50/64/68/70 losses:
AlphaGambit/Veritys/Snake/R&R/KingsGuard are exactly the non-blunderers;
KingsGuard's only "mistake" was their clock). Weak-bot wins converted
only *because* they cooperated; the policy just maximizes cooperation
rate. Playing on from −2..−7 vs weak bots is directly supported (r63/66/
67). Never resign/assume-lost material logic against the weak class:
"material decides by 300 plies" only bites if they convert — they
blunder instead.

*Legality.* Zero data, pure in-game code — the cleanest adaptation form.
100% clean, no Pino question needed.

*Implementation (half day).* Small scoring hook in `agent.py` around the
root score; a policy gate applied in root move selection (simplification
bias = prefer captures/trades when winning-weak; keep-complexity bias =
avoid forced trades when losing-weak). Keep it a *soft* nudge
(±handicap in root ordering within a band), not a hard rule — hard rules
are how endgame terms regressed in Phase 3.1.

*Test design.* Head-to-head with a blunder-injected baseline: make the B
side play V5 but force a blunder every N moves (our own corpus shows
weak-bot blunder rates — r66/r67 had 2–3+ hanging-piece events); verify
the adaptive side converts more of the ± small-edge games. Both clocks.

*Risk.* LOW-MED. Misclassification (3 quiet moves ≠ weak) is the
failure; the soft-nudge band and the 6–8-move warmup limit damage. Gate
catches regression on the non-blunder baseline (policy must be inert
against strong opponents — require ≈ parity vs plain V5 there).

---

### P6 — ROOT-MOVE STABILITY (Quirk 2 fix) ★★★☆☆

*Idea.* PV-preserving root move selection: across ID iterations, keep the
previous iteration's best move when the new best is within a small score
band (ε ~ 10–20 cp); optionally re-confirm on the real clock (backlog #3:
aspiration/stable-PV early stop at long TC is a re-test candidate after
the 500 ms rejection).

*Why it wins games (evidence).* sims-v5 Quirk 2: r70 p28 flipped
Rb8→c4→Bg7 across 1s/5s/25s budgets; r71 p16's real move appeared at NO
budget — the shipped build's *personality changes with host nps*. Replays
diverged from real games at exactly these points. Stability is a
behavioural defect (same position, different box → different plans), it
matters across a fleet of venue boxes, and it's the difference between
"r71's plan" and "what the venue actually played".

*Legality.* Pure code. Clean.

*Implementation (half day).* Band-preference in `search_root`'s final
selection; keep the full-window re-search (Phase-3 aspiration revert was
about *window* discipline, not PV preference — do not re-litigate
aspiration). New env toggle for A/B.

*Test design.* Re-run the fixed-budget probes (1s/5s/25s) and require
monotone-or-band-consistent PVs on r70 p28 / r71 p16; then standard
gates. Determinism note: this *improves* replay fidelity.

*Risk.* LOW. Worst case a +10cp worse move kept; ‒ can ship independently
or bundled with P1.

---

### P7 — TIED-MOVE RANDOMIZATION (anti-replay / anti-fingerprint) ★★☆☆☆

*Idea.* When several root moves score within ~1–2 cp, choose uniformly at
random (seeded by wall clock + FEN) instead of first-found. Kills exact
determinism of our public ladder games (opponents replay our games; our
reply at a given FEN is currently a pure function of position+clock).

*Why it matters.* PROCESS §5 #8 (build fingerprint) + the determinism
question: our games are public; a replaying opponent gets our exact
answers at every position they replicate. Cost ≈ 0 (score-equal band);
benefit = defense in depth + our own replay forensics stays useful
(which of their games matched which seed is knowable from PGN + clock).

*Implementation.* 10 lines in `search_root` selection. *Risk.* LOW.
*Test.* Byte-parity suite (tools have determinism checks) updated to
allow tie jitter; standard gates. Not a ladder-points probe by itself —
ship as a hygiene rider on P1/P6.

---

### P8 — INIT-TIME SELF-GENERATED ENDGAME TABLES (the 97% idle init) ★★☆☆☆
*→ see "too weird" note below; ranked separately.*

### Not ranked (dead ends, with reasons)
- **Opening book from curated FENs (backlog #5 / research 03 §1):** all 13
  games start from *distinct* injected FENs; we choose no moves until
  ~move 6–9; a book only pays if the pool is small AND published — and
  even then, prep is self-analyzed PVs which is P2-adjacent work for a
  side gain (clock economy). Revisit only if the curated set is published.
- **Identity-based opponent database:** impossible live (no network, no
  identity signal at init) and gray to ship (see §1). Position-based P5
  supersedes it.
- **Deliberate flag-pressure via complexity:** we cannot see the
  opponent clock; "make sharp positions" is unmeasurable in-game and
  hurts us (we're the weaker searcher — r70's sharp line is where we
  died). The *observed* flag lever is one-sided: opponents self-endanger
  in long games (KingsGuard 4.4 s). Folded into P5 (keep-game-alive when
  losing-weak) where it is policy, not hoping.
- **Deliberate repetition-seeking:** already in the engine (search treats
  repeats as draws; r63 held −2 by design — PROCESS P1/D10). Nothing to
  build; verify the *winning* side of the policy stays active (it does,
  r69/r71 converts).
- **Bigger TT alone:** fold into P1's test bed (1-line, free at 2 GB).

---

## 3. TOP-3 for this week (freeze 11 Sep 11:00, ≤6 uploads/day)

Sequence for maximum EV under D11 (no engine change without a 0.750-referenced gate):

1. **P1 — real-clock time policy** (spend-more + reserve + venue headroom,
   + optional TT size + root stability). Best EV/effort ratio; directly
   fixes the measured "idle clock" (median 55 s unused) AND the measured
   "nearly flagged" long games; the full-clock sim gate is the regime the
   ladder actually runs. Upload 1–2.
2. **P2 — ship 3–4 piece syzygy (4.2 MB)**. Already-decided in research
   03, never executed; closes KPK + conversion leaks (r64/r68 class);
   pure addition, lowest risk decisive-point lever. Upload after P1 or
   bundled.
3. **P4 — Quirk-1 eval-skew fix** (knight-down reads −250..−350). r70's
   loss was a *belief* failure; one measured term, hard regression guard.
   Upload 3–4.

Then, if gates are clean and uploads remain: **P5** (weak-bot adaptive;
highest novelty, complements P2's TBs: simplify INTO tablebase range vs
weak, keep-game-alive when losing-weak). **P3 (pondering)** is the
biggest raw lever but the only MED-HIGH risk item — do it only after
P1/P2/P4 are banked and a sleeps-injected gate is decisive; otherwise
leave it as the documented "why we didn't gamble near the freeze" note.
P6/P7 ride along with P1.

## 4. Too weird — but note for the write-up: "the 95% idle init does the
work nobody ships"

The 60 s init (we use ~3 s) can run a **retrograde tablebase generator**
for a cherry-picked class: KQvKR / KPK (3–4 man, ~1–32 M states) or, at
the edge of feasibility, one 5-man pawnful pair (KPPvKP, longest mate
127 — WDL only, cursed-win-aware). Zero shipped data (all code), perfect
endgame play *beyond* the 4.2 MB syzygy set without spending zip budget,
and judge-bait: "our engine computes its own endgame tables while the
harness boots." Why it stays a note: 60 s of numba retrograde on 1 core
is borderline for the useful classes (KPPvKP ≈ 11 G ops, measured risk of
not converging in time), and P2 already covers the 4-man space — the
incremental value is the 5-man pawnful classes, which are exactly the
weak-bot endgames. If P2 lands and the box init proves fast (r48: 3.1 s,
budget 90 s), the leftover init seconds are almost free: generate KQvKR +
KPK and fall back to shipped TBs if the generator times out. Best
"different approach" story material for the finalist walkthrough either
way.

---

*Verdict summary (last section as required by brief):* the ladder is won
with **clock discipline, tablebase-perfect endgames, and a belief fix** —
P1 (spend the idle 55 s median + reserve for long games), P2 (the
decided-but-unexecuted 4.2 MB TB ship), P4 (r70's −100-vs-−300 eval
skew). The radical *legal* differentiators nobody else will have:
P5's in-game weak-bot classifier (won −7-material games prove the
strategy) and the init-time TB generator. Identity-based meta is
impossible and half-gray (needs Pino sign-off if ever pursued); the
clean version is move-based adaptation, which needs no data at all.
Pondering is the biggest single lever but the only MED-HIGH risk — gate
it after the three banks land, or document it as the disciplined pass.