# 04 — Competition Landscape & Rules

Research KB, AI Chessathon (London, Sep 2026, Optiver). Context per [official docs](https://aichessathon.com/docs): qualification ladder 4–11 Sep (hourly rated rounds, 08:00–22:00), 13-round Swiss over **locked builds** decides 50 London seats; env 1 core / 2GB / no GPU-network, python-chess 1.11.2 + numpy + numba/onnxruntime, 120s+0.5s/move, 60s init, pondering allowed, 50MB unzipped, classical search = full entry, 3rd-party engines banned, books/TBs allowed as data. Uploads close **11 Sep 11:00**. Compliance: see `ORIGINALITY.md` — everything shipped is code written in this repo; this doc cites sources, it contains no code.

## 1. What it takes to win a "build an engine in a week" comp

**Similar events and what they show:**

- **HackChess 2023** (online hackathon, 167 participants, 2 weeks, Arena GUI + UCI, any language, $270 prizes): a pure amateur bracket; winners were strong-but-amateur engines, *not* TCEC-class. Shows an all-original student field converges far below professional engines. [hackchess.devpost.com](https://hackchess.devpost.com/)
- **Lichess bot championships** (double-elim, lichess bot accounts): top entrants are NNUE-family engines (e.g. `EmanPureNN`, per [6th LBC rules thread](https://lichess.org/forum/team-lichess-bots-championship/rules-of-the-6th-lichess-bots-championship)); the tail of the field is hobby engines. Confirms the field splits into "Serious dev engines" and "weekend builds".
- **FIDE/Google/Kaggle Efficient Chess AI Challenge** (Nov 2024–Feb 2025, $50k, low-resource constraint, rated ladder, up to *5 submissions/day* — near-identical ladder mechanics to ours): structure is the closest analog. But the *field* is not: top entries were **Stockfish-family** (Cfish ports, NNUE nets, Syzygy) — see 9th-place "Cfish + SPSA" writeup and [KaggleFish](https://github.com/AndyGrant/KaggleFish). That tier (~3000+ CCRL) is irrelevant to us: stockfish-family code is *banned in our submission*. What Kaggle proves: in a ladder format, sub-count and iteration speed matter, and even 9th place needed a ship-grade engine. [FIDE announcement](https://www.fide.com/fide-and-google-create-the-efficient-chess-ai-challenge-hosted-on-kaggle/), [Kaggle overview](https://www.kaggle.com/competitions/fide-google-efficiency-chess-ai-challenge/overview)
- **Weiss** (Terje Kirstihagen): started from the [Vice](https://chessprogramming.org/Vice) didactic series (87 YouTube videos), C, first release Nov 2019; after ~3 months he estimated **~2500 CCRL blitz with TBs** and the [release thread](https://talkchess.com/viewtopic.php?t=72369) shows ~2.4–3.8M nps single-thread, depth 11–14 in <1s. Its feature list (TT, PVS, LMR, null move, quiescence, tapered PST eval, Sylgy) is the *blueprint* for a strong amateur engine. [CPW: Weiss](https://chessprogramming.org/Weiss)

**Realistic bar for a 50-seat final of UK CS students, 1 core/120s, original code only:**

- Expect the final field to be *mostly Weiss-class or weaker*: a few teams with serious C/C++ search + tuned eval (est. 2200–2600 CCRL), the bulk at Vice/Sunfish level (1600–2000), some incomplete builds. [INFERENCE] — no prior of *this exact event* exists (Optiver sponsors human chess, e.g. [Optiver Chess Championship](https://www.englishchess.org.uk/2025-optiver-chess-championship/); this engine event looks novel), so treat field strength as the dominant uncertainty.
- **Top-3 likely needs ≈ 2200–2400 CCRL-class play on our hardware.** That is reachable *only* with a correct, fast, well-pruned search + decent eval + zero game-losing bugs. A depth-6–8 numba alpha-beta with PST eval and no time control will not place.
- Ladder (qualification) is a *lower* bar than the final: it runs against house bots with public CCRL ratings — presumably TSCP/Vice-class (1500–2000). Beating those ~90% needs ≈ +300 Elo over them, i.e. ≈ 1900–2100. [INFERENCE] about bot strength; check the ladder results after round 1.

## 2. CCRL / strength context

**Verified anchors (measured, not guessed):**

| Engine / stack | Measured strength | Source |
|---|---|---|
| Sunfish (pure Python, minimal, pypy ~30k n/s) | lichess blitz **1788**, bullet 1895, rapid 1944 | [lichess profile](https://lichess.org/@/sunfish-engine) (API) |
| black_numba (numba bitboard, full features) | lichess blitz **1931** | [lichess profile](https://lichess.org/@/black_numba) (API) |
| Vice 1.1 (C, didactic, full basic search) | **~1660–2007** across lists (CCRL stale ~1850; private list 2007) | [CCRL rating thread](https://talkchess.com/viewtopic.php?t=77205) |
| TSCP 1.81 (C, minimal) | ~**1500** CCRL blitz (commonly reported; CPW links list) | [CPW: TSCP](https://chessprogramming.org/TSCP) |
| Weiss 0.6 (C, 3 mo, simple untuned eval, LMR, TBs) | author-est. ~**2500** CCRL fast TC | [release thread](https://talkchess.com/viewtopic.php?t=72369) |
| Kaggle Efficient Chess finalists | SF-family, ~3000+ (banned tier for us) | [KaggleFish](https://github.com/AndyGrant/KaggleFish) |

**NPS / depth expectations on 1 core:**

| Implementation | nps | depth at ~30s (open pos.) | strength band |
|---|---|---|---|
| python-chess movegen, numba search | ~30–150k | 5–8 | ~1600–1900 [INFERENCE] |
| own bitboards + numba jit (cf. black_numba) | ~200–600k | 8–12 | ~1900–2200 [INFERENCE] |
| C bitboards (cf. Weiss, but we're Python) | ~2–4M | 13–18 | ~2200–2600 |

Source for C numbers: Weiss log in [release thread](https://talkchess.com/viewtopic.php?t=72369) — depth 11–14 in 0.2–0.7s at ~2.4M nps. python-chess hot-loop cost is the constraint: its movegen is pure Python (perft only ~7k n/s pure in [black_numba README](https://github.com/Avo-k/black_numba)); jitting search around it does not fix the movegen bottleneck. **Your "depth 6–8 numba + PST" baseline maps to ≈ 1700–2000 CCRL/lichess-class — Vice/Sunfish-and-a-bit-above.** To reach the 2200+ band, invest in (a) own movegen or at least jit-friendly make/unmake, (b) at minimum quiescence + TT + killers/history ordering + null move + LMR, (c) tapered PST+ eval with a few real terms (passed pawns, mobility, king safety, bishop pair). [CPW: Search](https://chessprogramming.org/Search), [CPW: Evaluation](https://chessprogramming.org/Evaluation)

**House bots on the ladder:** if organizers picked engines with *public* CCRL ratings (the natural choice: TSCP/Vice/Sunfish-class), the ladder baseline is ~1500–2000. We need to comfortably out-rate that. Track first ladder round; if house bots are stronger, qualification pressure rises.

## 3. Lessons from winners / strong amateur engines

What separates entries (ordered by impact):

1. **Zero game-losing bugs.** Illegal move, crash, or timeout = instant loss. Weiss shipped his first release admitting "very rare crashes on linux" [release thread](https://talkchess.com/viewtopic.php?t=72369) — the winning habit is *validation, not hope*: perft parity, smoke games, crash/illegal-move guards before every upload.
2. **Quiescence search.** Without it, a tactical engine blunders into hanging pieces at the search horizon — the #1 reason simple engines lose games they "should" win. Non-negotiable. [CPW: Quiescence](https://chessprogramming.org/Quiescence_Search)
3. **Move ordering + TT + ID**: halve-to-tenth the tree for free strength (alpha-beta only prunes well with ordering). This is the classic "didactic engine to 2000+" step (Vice's whole arc). [CPW: Move Ordering](https://chessprogramming.org/Move_Ordering)
4. **Selectivity** (null move, LMR, razor/futility) — the step that took Weiss from Vice-class to ~2500 estimate in months.
5. **Time management.** Rule: never spend > ~30–60s of a 120s budget on one move; keep a 20–30s reserve; early moves cheap (10–20s); complexity (many captures/checks) gets more. 0.5s increment ≈ +17s per 34-move game — negligible safety; *the clock is won by budgeting, not increment*.
6. **Eval quality** (tapered PST + mobility/passed pawns + king safety) beats raw depth at our depths; hand-tune or SPSA-tune against a fixed baseline.
7. **Endgame tables.** With **300-ply material adjudication**, games stop when material is decisive — you never need a mating net, only correct conversion. Probing a small shipped Syzygy subset (see §4) eliminates conversion blunders (stalemate traps, KRvK fumbles, fortress blindness).

**How the rules punish failure modes:** illegal move → loss (platform rejects); crash/timeout → loss; games from "curated level positions" → no safe book exits, engine must play *any* sound position; adjudication on material → the engine that trades down into a drawn fortress when up material *throws away* the win the rules would otherwise award; ponds/exceeds → clock loss. All standard published practice, to implement fresh ([CPW: Time Management](https://chessprogramming.org/Time_Management), [CPW: Pondering](https://chessprogramming.org/Pondering)).

## 4. Rule exploitation / strategy

- **300-ply material adjudication.** Optimize for *material conversion*, not mate: (a) ship a curated **Syzygy subset** as data (allowed; `chess.syzygy` in base image) sized to ~20–40MB — 3-man + 4-man WDL/DTZ (~15–85MB total [INFERENCE — verify actual sizes at build time]) plus *selected* 5-man endings likely in curated positions (KRPK, KQPK, KRvKR…); probe when ≤7 pieces (python-chess supports up to 7-man if files present) and play the DTZ/WDL-correct move. This is *shipped data*, explicitly permitted — the idea is standard published knowledge, the probing code is ours. (b) In search, prefer keeping winning material over "risky forced mate" lines; a fact of *this* rule, not general engine wisdom.
- **Pondering (allowed).** After `get_move` returns, process stays alive on our core: search the opponent's expected replies to our move so the next `get_move` can reply instantly with a pondered PV (and deeper search) — effectively free extra depth. Constraint: never let pondering overrun our own 120s budget or block `get_move`; kill/truncate the pondered thread promptly. Worth ~+50–150 Elo [INFERENCE] if done without bugs.
- **60s init.** Use it: numba JIT warm-up (helps a lot — cold first call is 10–30s per [black_numba README](https://github.com/Avo-k/black_numba)); preload book + TB indices; allocate TT. A numba `cache=True`-compiled kernel avoids most of it.
- **Time control.** 120s+0.5s, games from curated positions: adopt a simple adaptive budget — target 5–10% of remaining + small bonus on clock trouble; **hard cap per move (~45s) and a never-flag floor** (e.g. always keep ≥15s + 30 × increment). If clearly winning on material, the engine should *shorten* search (drawish risk aside) — points are banked at adjudication.
- **Curated level positions** reduce opening theory value: a tiny polyglot book (data, allowed) still helps avoid the worst early lines and saves clock, but the Elo is in eval/search robustness on *arbitrary* positions (closed positions, opposite wings, fortress-ish material) — tune eval against those, not only book play.
- **Draw avoidance/recognition.** Implement repetition + 50-move awareness in search (standard practice) so we don't steer into a draw when adjudication would award a win, and don't waste time searching drawn repeats.
- **Daily Five (6–10 Sep, human-only, UK students, 5 positions/20min, no engines):** separate track, separate wildcard seats. Nothing for the engine build; if we have a strong human, that's a *separate* entry — fair-play: it must be genuinely human play; do not connect it to our engine or any third-party aid. No further strategy here.

## 5. Team + logistics (7–11 Sep, we're mid-qualification)

Hard facts: 1–3 people; **≤6 uploads/day**; validation smoke games before upload; uploads close **11 Sep 11:00**. Qualification ladder runs through Sep 11 — every uploaded build plays the ladder, but London seats come from the Swiss over **locked builds** (interpretation: the build locked at close; [UNCERTAIN] whether per-round locks exist — check official docs, plan for final-lock).

**Priority: correctness > strength > speed** (in our stack, speed *is* strength — NPS is the multiplier on everything else — but an illegal-move engine loses 13/13 Swiss games).

**Solo-dev schedule (Sep 7–11):**

- **Sep 7 (today):** minimal legal agent (get_move(fen, ms) → uci) on python-chess; perft/smoke harness; first submission — a *safe* build plays the ladder all day. Set up git tags + `make_zip.sh` now.
- **Sep 8:** search core — ID + alpha-beta/PVS, quiescence, TT (fixed-size, e.g. 64–256MB of the 2GB), killers/history ordering. Biggest Elo/day available.
- **Sep 9:** selectivity — null move, LMR, futility/razor; eval v2 (tapered PST + passed pawn/mobility/king safety/bishop pair); time management.
- **Sep 10:** book + Syzygy subset probing; pondering (careful, after core is solid); SPSA/tuning pass vs fixed baseline; stress tests (long games, perft).
- **Sep 11:** freeze by **09:30**, final validation smoke set, upload **10:30**; keep yesterday's build zipped as rollback. No risky change in the final 3h.

**2-person variant:** dev owns search/eval, second person owns harness/tuning/robustness (perft parity, crash fuzz with random FENs, time-safety audits) and manages the 6/day upload cadence — integrate via branch+merge; never let a broken build reach main (main = always uploadable). Two pairs of eyes on move-gen legality and clock code specifically.

**Upload cadence:** use all 6/day *only when* the change passed (a) perft parity, (b) ≥200 self-play games vs previous build (approx ±30 Elo resolution [INFERENCE]), (c) smoke games incl. clock edge cases. A regression that ships to the ladder costs ladder points; a regression that ships to the locked Swiss costs a final seat.

**Lock question:** if per-round lock is on, upload conservatively late in each day; if final-lock, iterate hard until 10 Sep, then freeze.

---

### Originality notes (per ORIGINALITY.md)

- **Standard published knowledge, to implement fresh:** negamax/alpha-beta, ID, TT, quiescence, MVV-LVA/killer/history, null-move, LMR, futility/razor, tapered PST eval, repetition/50-move detection, time management, pondering, SPSA tuning — concepts only, code written by us in-repo.
- **Shipped data (allowed):** polyglot book(s), Syzygy subset (verify size), any published PST/weight *values* only with attribution in BUILD.md; prefer our own tuned values.
- **Never:** any engine source (sunfish, python-chess examples, Stockfish/Cfish derivatives), any NN weights, internet fetch at build time. Stockfish only as an external local sparring partner, outside the repo.

### Sources
Official: [aichessathon.com/docs](https://aichessathon.com/docs) · HackChess: [devpost](https://hackchess.devpost.com/) · Lichess LBC: [6th rules](https://lichess.org/forum/team-lichess-bots-championship/rules-of-the-6th-lichess-bots-championship) · Kaggle: [FIDE](https://www.fide.com/fide-and-google-create-the-efficient-chess-ai-challenge-hosted-on-kaggle/), [overview](https://www.kaggle.com/competitions/fide-google-efficiency-chess-ai-challenge/overview), [KaggleFish](https://github.com/AndyGrant/KaggleFish) · CPW: [Weiss](https://chessprogramming.org/Weiss), [Vice](https://chessprogramming.org/Vice), [TSCP](https://chessprogramming.org/TSCP), [CCRL](https://chessprogramming.org/CCRL), [Search](https://chessprogramming.org/Search), [Time Management](https://chessprogramming.org/Time_Management) · TalkChess: [Weiss release](https://talkchess.com/viewtopic.php?t=72369), [Vice CCRL](https://talkchess.com/viewtopic.php?t=77205) · Lichess: [sunfish-engine](https://lichess.org/@/sunfish-engine), [black_numba](https://lichess.org/@/black_numba), [black_numba README](https://github.com/Avo-k/black_numba).