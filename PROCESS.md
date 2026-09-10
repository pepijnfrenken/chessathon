# PROCESS.md — project master log

**The one place for everything: decisions, traces, progress, setbacks,
ideas, problems.** Updated by the orchestrator (Hermes) at every milestone —
keep the TL;DR fresh, append to the right section, never delete history.

- Deep engineering detail per phase → `BUILD.md` (the judge-facing design log)
- Agentic record (briefs, raw session traces, builder×auditor narratives) →
  `docs/agentic-process/` · research KB → `docs/research/` · evidence → `results/`

---

## 0. TL;DR — current state (2026-09-10; ladder standings corrected below)

**CURRENT (supersedes the Sep 8-era text further down this section):**
**v7 is live** — night3 build (null-sign fix + KBN zeroing fix + pawn-PST
flip + root-best ordering), uploaded Sep 10 06:19Z, ACTIVE from 06:22Z.
**Debut r91: WIN vs Epoch & Mate (0-1 as Black, mate m63, 112 plies, zero
flags)** — grind-then-finish: +1 pawn from the Nxd4/Bxb5 trade, queen trade
m17, rook endgame ground down (+4 pawns), a-pawn promotion, then QUEEN SAC
Qxg1+ forcing Rh1#; mate played at 0.0s/move (precomputed). Full ship
record + release identity: §13. v6 (null fix) was live Sep 9 20:42Z → r90; V5 before it (r70-89). **Authoritative ladder record (PGN headers × platform export, cross-checked 2026-09-10, 0
mismatches; supersedes every earlier tally incl. the wrong "r87/r88
losses" reading):** r48-91 = **20W-10D-14L** — v1/v2 era r48-60 3W-5D-5L ·
v3/v4 r61-69 5W-2D-2L · **V5 r70-89 11W-3D-6L** · v6 r90 0-0-1 (single
tactical miss, not leak-family) · **v7 r91 1-0-0 — reviewed clean: 54/56
moves good-or-better, both flags are won-position artifacts**. Leak-family losses with committed SF16
reviews = r64/r68/r70/r74/r76/r83 — each carries 5-20 SF-visible bad moves
vs 0-4 for reviewed wins/draws; r85/r87/r88/r89 await reviews (r90 =
reviewed, single tactical miss, not leak-family).
**Engine:** original numba-jitted alpha-beta (own board+movegen, perft-exact),
hand-tapered eval, stateful anti-threefold (game-history repetition).
`agent.zip` 30 KB — `agent.py` + `engine/` only. HEAD `49c4c0e` + process commits.

**Ladder (r61–69 = V4, the 08:46 upload `49c4c0e`, no P7/P8; r70+ = V5,
`73c7d44` + P7/P8, uploaded Sep 8 ~16:00 — D12):** v3 line D W D L W W W L
→ 4W-2D-2L. r62 **WIN** vs Forking squad (checkmate — first real conversion) ·
r61 draw vs CrimsonBot (material +0 even; threefold created by *their* king
shuffle) · r63 draw vs Ultimate32 (we were −2 — repetition **held a lost
game**) · r65 WIN Magnus · r66 WIN Benko · r67 WIN Chess (17-move mate) ·
**r68 LOSS vs Rook and Roll** (even at ply 49, −3 by 57, −10 by 65: second
material-leak loss — Q-ending transition).
**r69 WIN vs Stockfish (checkmate, 57 moves, 2026-09-08, `results/matches/
round-69-vs-stockfish.pgn`)** — played by the **V4 upload (49c4c0e)**:
textbook conversion: +3 by move 24 (Nxf6/
Bxf6/Bxh8 raid vs their uncastled-h8 rook after their O-O-O), then model
endgame: rooks simplified, Rxd6+ sac, cxb4, king march Ka4-Kb5-Ka6, b-pawn
run b5-b6-b7-b8=Q, Qxg4, mate Qc2#. No flags; clock healthy throughout
(~2s/move). Exactly the stateful anti-threefold's promise: won game
converted to mate, no shuffle-draw. v3 line now D W D L W W W L **W** →
5W-2D-2L. P7/P8 were NOT in this build (post-upload fixes).
**r70 LOSS vs KingsGuard (mated m31, 2026-09-08, `results/matches/
round-70-vs-kingsguard.pgn`)** — first V5 game (`73c7d44`+P7/P8): 0-1.
V5 clean: **zero repetition events** (nothing for the key fix to engage),
no flags/fingerprints/illegals, our clock never below 1:05. Loss anatomy:
a3/Na2/Ra1/Qxb2 skirmish (m15–23) left us a clean piece down from m23
(+2 W); king walk Kg7-Kh6-Kxh5 (m19–22 for us) = positional collapse;
Bh4-g5 dropped to f4-push, Rf5 hung to Bxf5 — sealed from a lost position.
Opponent clock profile: 7–20s/move opening burn (deep pondering), then ran
the rest of the game on ~3.5s+0.5 increment — tactical midgame outclass,
NOT time-forced (we had 1:05 when mated). Ladder now 5W-2D-3L through r70.
**r71 WIN vs Magnus (1-0, mate m42, 2026-09-08, `results/matches/
round-71-vs-magnus.pgn`)** — White (us). V5's first win (2-0 vs Magnus
overall). Queens traded off after Nc3+/bxc3/Qxf6 skirmish, then clean
conversion: Bxf8, Rxa7 Kxa7, Rxf6, king march Kb5-Ka6, Rb7+/Rxb6, Bc6#
mate net. No flags/illegals. Ladder 6W-2D-3L through r71.
**V5 simulation probe (r70+r71, 2026-09-08, `results/sims-v5/README.md`):**
core hygiene CLEAN (no illegals/flags/threefold; time mgmt by design).
Three findings: (1) **eval skew** — V5 rates the knight-down post-skirmish
position ~-100cp (should be -250..-350): it *believed* the Na2 line was
near-equal; fix candidate = material/compensation term audit. (2) **depth
instability in sharp middlegames** — moves flip with budget (r70 p28:
Rb8@1s/c4@5s/Bg7@25s; r71 p16: real Rg1 at no budget) → play varies with
host CPU nps; fix direction = root-move stability, not eval. (3) Kxh5/Rf5
= correct desperation (eval knew -4, played best defense) — not defects.

**All three verified correct behaviour of the shipped build** (exact-clock
replay + eval probe, see §6 P1): r61 = dead-equal hold (raw 0.00, every
alternative ≤ −21), r62 = converts, r63 = defensive draw allowed by design.

**Ladder updates (dashboard export, 2026-09-09):** r75 **WIN** vs Prophylaxis
(White, checkmate, 21:30 Sep 8, `results/matches/round-75-vs-prophylaxis.pgn`)
· r76 **LOSS** vs MCAI (White, checkmate, 07:30 Sep 9 — the newest game;
`results/matches/round-76-vs-mcai.pgn`). Dashboard standing 09:40 UTC:
**rank #267/410 · rating 1461 (peak 1466) · 12W-7D-10L** (v5 upload
`6abb1ca1affa` Active). Gap **r51–60 PGNs+logs CLOSED** — full set r48–r76
now in `results/matches/` (dashboard fetch, moves byte-verified vs chat
copies for r61–74) + per-round metadata in `results/dashboard/games.csv`.

**Open items:** · uploads freeze
11 Sep 11:00 (freeze strategy: §5/#5, §6 P5) · **rank 336/387 (Sep 8) —
the crater is stateless-era damage (r48–60); stateful build r61+ = W/D,
climbing** (recovery tracker: §6 P4; dashboard now shows #267/410 — see
above).

**Deadlines:** qualifier rated rounds 4–11 Sep (hourly 08:00–22:00 UTC) ·
50 London seats in finishing order · final Swiss 12 Sep, Encode Club.

---

## 1. What we're building & why

AI Chessathon entry: `get_move(fen, time_left_ms) -> uci`. Box = 1 core,
2 GB, no GPU/network, 120s+0.5s clock, 60s init, pondering allowed,
classical search = full entry, third-party engines banned in the zip.
Strategy (decided early, holds): **original classical engine, numba-jitted,
hand evaluation** — highest-EV legal path vs self-training an NN on 1 core.

## 2. Timeline — progress & ladder record

| When (2026) | What | Result / evidence |
|---|---|---|
| Sep 6–7 | Research KB, 4 parallel workstreams | `docs/research/01–05` |
| Sep 7 07:00 | Phase 1a — minimal pure-Python agent + harness | Uploaded; ladder **47/351**; 17-7-0 local gate |
| Sep 7 09:00 | Phase 1b — numba engine core | perft-exact, ~865 knps; gate 22-0-0 vs 1a |
| Sep 7 10–13 | Phase 2 — eval terms + Texel tuning tooling | **Negative: hand eval ships** (see §4) |
| Sep 7 13–16 | Phase 3 — aspiration + LMR (+ 4 forensics fixes) | Aspiration **rejected** 0.438; LMR **kept** 0.542 |
| Sep 7 16–19 | Phase 3.1 — endgame conversion fixer | **Reverted**: 0.417/0.396; pinned to qsearch stalemate probes |
| Sep 7 19–21 | Phase 4 — stateful anti-threefold + qsearch knight fix | **Shipped**: gate 0.750, eg_check 8/8, zero threefolds |
| Sep 8 08:30 | Upload → ladder r61–63 | see §0; record in `results/matches/` |
| Sep 8 | r64 vs Snake — **LOSS** (first v3 loss) | won position +1.5 leaked at ply 76 (fork), Q-endgame perpetual failed; full post-mortem in `5a88dd4` |
| Sep 8 | r65 vs Magnus — **WIN** (mate) | Qc7# king-hunt finish; `f4a8d58` |
| Sep 8 | r66 vs Benko — **WIN** (mate) |
| Sep 8 | r67 vs Chess — **WIN** (17-move mate) | quickest win yet, no flag; `ca7dc96` |
| Sep 8 | r68 vs Rook and Roll — **LOSS** (checkmate, 39 moves) | even at ply 49, −3 by 57, −10 by 65 — material leak in Q-ending transition; `bf9d364` (results) | survived sac attack, converted R-endgame vs their perpetual; `ee4777b` |

**Ladder results (logged):** r48 loss SkyLab · r49 loss AlphaGambit (1b
first game) · r50 loss The Veritys · **r51–60: no records saved** ·
r54/55 (from Phase-4 trigger notes): won endgames shuffled into threefold
draws · r61 draw CrimsonBot · r62 WIN Forking squad · r63 draw Ultimate32.
Early rating 47/351 was the Phase-1a build; current rating: check leaderboard.

## 3. Decision log — the spine of the story

Every major decision, with the evidence that made it. (Full narratives:
`docs/agentic-process/AGENTIC-PROCESS.md` §3.)

| # | Decision | When / commit | Evidence |
|---|---|---|---|
| D1 | Classical search, not an NN | Sep 6 | Box constraints; "classical = full entry" |
| D2 | Correctness gates before strength (perft parity = gate #1) | 1a/1b briefs | 1b shipped only after perft-exact; en-passant crash caught by harness |
| D3 | Ship 1a same-day (minimal) | 1a | Ladder data > local theory; 47/351 |
| D4 | **Hand eval ships; Texel-tuned rejected** | Phase 2, `6dc3dcb` | hand≈flat 0.479 wash; tuned 0.104 (0W-19L-5D); SPRT aborts 0-41-9/0-10-10; 60k-pos selfplay provenance |
| D5 | Aspiration windows rejected & reverted | Phase 3, `f621ba1` | gate 0.438 @500ms; re-search burns budget at short TC — retry at real TC is a stored idea (§5) |
| D6 | LMR kept | Phase 3, `1132a4b` | gate 0.542, zero flags |
| D7 | 4 latent search bugs fixed (PVS sign, qsearch stand-pat ×2, ep default) | Phase 3 | auditor + forensics; byte-parity tests |
| D8 | Endgame conversion fixer reverted, experiment preserved | `fc0098e`, `bcc1efa` | gates 0.417/0.396 regress; invariant across net scopes v3–v6 → pinned to qsearch stalemate probes |
| D9 | **Stateful agent + qsearch knight fix shipped** | `caede75`, `496b86a` | gate **0.750** (first decisive pass); eg_check 8/8; shuffle suite zero threefolds; empty-history byte-identical (provably inert) |
| D10 | Round 61–63: **no code change — verified correct behaviour** | Sep 8 | exact-clock replay: r61 13/13 move reproduction; probe: raw 0.00, penalty applied, all alternatives ≤ −21 → correct equal-position hold. r62 win converts; r63 −2 defensive hold by design |
| D11 | Freeze policy: no engine change without a gate (0.750 stateful build is the reference) | Sep 8 | uploads freeze 11 Sep 11:00; every idea in §5 must gate before ship |
| D12 | **P7/P8 key-correctness fixes shipped as V5** (`73c7d44`, uploaded Sep 8 ~16:00 UTC) | Sep 8 | EP-capture + rights-vanish zobrist fixes: probes pass on fixed tree AND fail on unfixed (sensitivity proven); tree A/B gate 0.479 null, zero flags → strength-neutral; ship on correctness (closes last hole in the repetition defense). r69 WIN vs Stockfish was V4 (49c4c0e); r70+ = first V5 ladder games |

## 4. Setbacks & what they taught

- **Texel-tuned eval disaster (Phase 2):** degenerate fit 0-wins-in-50
  (0.104); a garbage-tuned commit briefly landed (`516ef8c`) and was
  reverted (`b1df520`). *Lesson: anchor weights, gate before commit, and
  trust SPRT aborts.* Also: tuning is not the default lever here.
- **Phase-2 finisher died 3×** (12:01/12:03/12:12 runs): provider
  cold-start stall, stale-SPRT conflict killing a live run, timeout hunt.
  *Lesson: re-probe endpoints; never run SPRT in the same agent run as code
  edits; kill stale processes before gates.*
- **"It broke too many times" (Pino, end of Phase 2)** → operational rules,
  written into every later brief — see §8.
- **Phase 3.1 revert after hours of work:** conversions were real but cost
  more than they returned at short TC (0.417/0.396, colour-symmetric).
  *Lesson: local eg wins can be net-negative at gate TC; the revert with
  preserved experiment is a good outcome.*
- **r54/r55 shuffle-draws (the trigger for Phase 4):** won endgames drawn
  by threefold with time on the clock — the agent was stateless.
  *Lesson: the harness contract (FEN per call) breaks any engine that
  can't remember the game; fixed in Phase 4.*
- **Replay tool crash + clock-drift (today):** first replay of r61 deviated
  at ply 10 (agent chose Qd6 where the game played Ne4) — the simulator's
  clock drifted from the ladder's real per-move times, and the tool then
  crashed on an illegal `san()` after divergence. *Lesson: reproduce with
  the exact clock-left values from the match log, and report-before-push
  in the tool. See §6 P1/P2.*
- **Ladder record gap r51–60:** rounds were played but match files were not
  saved/committed. *Lesson: save every round file immediately; the git
  history is the only durable record.*

## 5. Ideas backlog (not yet tried — with rationale)

1. **KPK technique gap (both colours)** — the one documented endgame hole
   left after Phase 4 (shuffle-suite KPK-b @2s; BUILD.md "OPTION A").
   Small scope, existing gates can validate. Ladder-relevant: K+P endgames
   are common vs weak bots. *Risk: low; Phase 3.1 showed endgame terms can
   regress at gate TC — gate before ship.*
2. **Pondering** — allowed by the box (process alive, own core after
   `get_move` returns); free depth on opponent time. *Needs harness change
   to gate-test (opponent clock); listed "pending" since Phase 4.*
3. **Aspiration windows at real-clock TC / stable-PV early stop** — the
   Phase-3 rejection was @500ms gates; the failure mode (re-search burns
   budget) is weaker at 120s. Re-test with long-TC simulation games.
4. **KQvK/KRvK conversion flakiness under box load** — eg_check passes
   8/8 @300ms locally but flaked under load (BUILD.md Phase 4 risks).
5. **Opening book** — books allowed as data; a *self-generated* book from
   our own engine's games keeps originality clean. Marginal at deep search;
   real value is clock management in known lines.
6. **Time management at real TC** — current remaining/45 + inc is crude;
   simulate full 120s+0.5 games, watch flag risk and endgame reserves.
7. **Eval enrichment** — only with NEW evidence: Phase 2's negative
   (0.479 wash) says eval features aren't the bottleneck; search/endgame
   are.
8. **Build-version fingerprint in the warmup stderr line** — ladder logs
   are otherwise unidentifiable (old and new builds print the same line).
   Only worth it if we upload again; touching agent.py near the freeze has
   risk.

## 6. Open problems / questions

- **P1 — r61–63 classification: RESOLVED (2026-09-08).** Exact-clock replay
  (`tools/replay_pgn.py --clkfile`, clocks from match log) reproduced r61
  **13/13 moves** — the real game WAS the shipped build's deterministic
  behaviour. Eval probe at the final Qd6 (`tools/probe_r61_decision.py`,
  history window rebuilt from the PGN): **raw score 0.00, 2nd-occurrence
  penalty applied (eff −20), still the best move — every alternative ≤
  −21cp**. Verdict: r61 = correct hold of a dead-equal position (White
  created the 3rd occurrence); r62 = win, converts; r63 = defensive draw
  from −2 by design. No code action needed.
- **P2 — replay tool bug: FIXED** (`6d5418e`): san() assertion on diverged
  branch → reports uci instead; first-attempt ply-10 deviation traced to
  simulated-clock drift, fixed with exact per-move clocks. NOTE: exact
  reproduction only holds when no move overruns its budget on the replay
  machine (r63's move-1 overrun, 4.9s vs 3.2s budget, caused a TT-state
  divergence that is a machine artifact, not behaviour — r61's clean
  13/13 proves the path is sound).
- **P3 — ladder record r51–60 missing** — RESOLVED 2026-09-09: full set
  r48–r76 fetched from the dashboard (PGN+log, `results/matches/`,
  metadata `results/dashboard/games.csv`); r51–60 gap closed.
- **P4 — ladder standing: SUPERSEDED (2026-09-10).** Authoritative record
  now in §0 (TL;DR): r48-90 = 19W-10D-14L; V5 era r70-89 = 11W-3D-6L.
  The per-era numbers below are historical (as of Sep 8-9) and the "through
  r74/r76" tallies they rest on are among the stale readings corrected in
  §0. Historical text follows. Attribution:
  v1 = 1a pure-Python (rated 47/351 at launch), v2 = stateless 1b→Phase-3
  (r48-60 crater), v3 = stateful Phase-4 (r61+). V5 (r70+)
  record: W-L-W-W-L (r70 L KingsGuard, r71 W Magnus, r72 W Stocked Fish,
  r73 W SkyLab, r74 L Rohan). Full line through r74: 8W-2D-4L (v3/V5 era
  r61-74: W D D L W W W L W W W L). r72 W (Black, mate m107, +15 by ply 96 —
  conversion of a swingy midgame), r73 W (Black, mate m75, +10 by ply 60 —
  REVENGE over SkyLab, the r48 stateless-era nemesis; level→won midgame),
  r74 L (White, mated m127 vs Rohan — third won-position leak: +4 by ply 48,
  +3 at ply 72, level by 84, −6 by 96, −9 by 108; same family as r64/r68
  (leak in long-game transition under thinning clock; ended 24.4s left,
  127 plies). Ladder-race note: leak losses (r64/68/74) are now the ONLY
  loss class left — 3 of 4 V5-era losses; conversions vs weak bots are
  consistent (r72/r73 both converts).
  ~45-50 rated rounds remain before the freeze. Track Elo + per-round
  results here; round logs r64+ go to `results/matches/` as they come in.
- **P5 — freeze strategy:** uploads close 11 Sep 11:00. Every change after
  r61-63 carries regression risk vs the 0.750-gated stateful build. Decide
  per idea (§5) on evidence, not on time-to-freeze anxiety.
- **P6 — round-61 stderr fingerprinting impossible** (identical warmup
  lines) — see §5 #8.

- **P7 — EP-capture zobrist bug — FIXED** (`73c7d44`, builder round B4,
  2026-09-08): found by audit 2-A F1; probe_ep_key.py caught it plus the
  sibling P8 (below). One-line guard `captured != EMPTY and fl != F_EP`.
  Validation: EP parity battery ALL PASS, control sweep 38/38, replay
  parity 211 plies, determinism PASS. Gate result appended when done.

- **P8 — rights-vanish spurious ZCASTLE[0] — FOUND + FIXED** (`73c7d44`,
  builder round B4, 2026-09-08): when the last castling right died
  (castle -> 0) make XORed `ZCASTLE[old]^ZCASTLE[0]`, but ZCASTLE[0] is
  random and parse_fen never hashes it (`if c:`) — every rights-vanish
  move left a spurious entry in the key, breaking parse_fen parity for
  all post-vanish positions (repetition pre-seed / TT). Discovered by
  probe_ep_key.py's full 38-move control sweep; audit 2-A missed it
  (its sanity moves never hit the ->0 transition). Fix: XOR ZCASTLE[old]
  only, add ZCASTLE[new] only when nonzero.

- **GATE P7+P8 vs pre-fix tree** (`results/gate_p7p8_vs_prefix.log`,
  2026-09-08): gate_match_tree.py hand:1111 (fixed) vs hand:1111
  (73c7d44~1 snapshot), 24 games @500ms: **9W-10L-5D = 0.479, ZERO
  flags** — clean null. Key fixes are strength-neutral (expected: they
  fix soundness, not search). n=24 CI wide (~0.29-0.67); no signal
  either way → ship on correctness grounds. NOTE: the earlier
  tuned:1111-vs-hand:0000 run (0.062) was the WRONG harness — that
  matchup measures the known-dud tuned eval (0.104 on Sep 7 pre-fix);
  both sides carried the fixes. Real A/B is this entry.

- **Independent replication (audit-3 agent, sides-swapped A/B pair,
  2026-09-08):** same matchup, seed 7, 24 games per direction @500ms, fresh
  JIT caches: fixed-as-A **11W-7L-6D = 0.583**; baseline-as-A 16W-4L-4D =
  0.750 → fix perspective over 48 combined games **0.417, inside the
  project's null band** (0.396–0.417 seen on known-null v3/v5/v6 gates).
  ZERO flags in all 48. Logs: `results/gate_b4fix_asA_vs_shipped.log`,
  `results/gate_b4fix_vs_shipped_asB.log`. Also verified: on-disk
  agent.zip carries the fixed board.py (md5 == tree; import+JIT warmup
  46.7s < 60s); ladder PGN scan r49–r68: rights-vanish occurred in 7/10
  games, EP in 1/10 — the fixed key classes hit most real games, so the
  fix protects the repetition defense in practice, not just in theory.

## 7. Provenance map — where everything lives

- **Git log** = the chronological spine; commit style `N (label): what +
  why + evidence` — every claim checkable at its revision.
- `BUILD.md` — per-phase engineering detail: design decisions, gate
  tables, risks (judge-facing).
- `docs/agentic-process/AGENTIC-PROCESS.md` — who did what and why
  (roles, timeline, decision narratives, retrospective).
- `docs/agentic-process/briefs/` — all 13 mission briefs (verbatim).
- `docs/agentic-process/sessions/` — 16 raw agent traces (gzipped, 3.6 MB)
  with index README. Originals: `~/.omp/agent/sessions/-projects-chessathon/`.
- `results/` — gate/eg/shuffle/SPRT logs + `.stdout` (score headers) +
  `results/matches/*.pgn` (ladder rounds) + `results/phase31/`.
- `docs/research/` — the KB that grounded the build.
- `tools/` — gates & harnesses (see AGENTIC-PROCESS.md §1 for the map).

## 8. Operating rules (from the Phase-2 retrospective — "it broke too many times")

1. One feature per agent run; commit + validate before the next.
2. No long SPRT in the same run as code edits; start gates as background
   processes and poll.
3. Kill leftover `sprt.py`/`engine_side.py`/`gate_match.py` processes and
   check for stale logs before every gate.
4. Verify emptiness (`ps aux | grep …`) before each SPRT/gate run.
5. Model cold-starts kill agents — re-probe an endpoint before burning a
   run; deepseek preferred, qwen fallback, no OpenRouter.
6. Tuning is not the default lever after Phase 2's negative.
7. Commit granularly: message = what + why + evidence.
8. Honesty is a gate: negative SPRT → revert and say so; preserve the
   experiment and evidence.
9. Auditors are read-only and parallel (md5 snapshot → /tmp copy → verify);
   never let them write the tree.
10. Save every ladder round file immediately (`results/matches/`) —
    git history is the only durable record.

## 9. 2026-09-09 — quality_ab instrument validated (tooling mission)

Validated `tools/quality_ab.py` (89971a6) per its self-test contract.
Two tool bugs found and fixed (minimal diffs, CLI stable):
(1) `--game name.pgn:side` kept the `.pgn` suffix → looked for
`round-X.pgn.pgn` and missed the cached `results/leak_reviews/*.sf16.json`
reviews (would have re-run all 7 SF reviews); (2) replay worker assigned a
plain dict over `Game.headers` → python-chess `Game.__str__` needs its
`Headers` object (crash on PGN write). Commits 051a2cf, 5472968.

Self-test ran twice (single r74, then the full 7-game corpus —
`results/quality_ab/selftest-r74{,-retry}/`, `selftest-corpus/`).
Fidelity per game: **0/2, 16/21, 16/25, 2/10, 7/11, 3/6, 3/6** — below
the 90% bar, but every divergence traces to one **machine-artifact
class, not a tool bug**: move choice flips with which iterative-deepening
iteration completes inside the time budget. Proven on r74 move 1: the
venue's own log says "Slowest 4.2 s" (over its 3.17 s budget) and played
Nf3; the byte-identical `agent.zip` build replayed here answers Bd2 in
4.5–5.1 s (JIT-cold first call; deterministic across quiet-box retries;
zip == tree except default-OFF P4/P1 toggles). Every replay stop is the
designed post-divergence halt ("opponent PGN move illegal after
deviation"); clock extraction (r64 full 224/%clk), SetUp/FEN start boards,
review caching and leak k-alignment all verified correct end-to-end.

**Self-A/B signature confirmed:** pre-divergence V5 leaks classify
retained 5 / avoided 0 / replaced-worse 0, cand mean cp_loss 77.7 vs V5
768.1 — the candidate cannot beat itself, so WEAK verdict is the expected
HEAD result (documented in `tools/QUALITY_AB.md`). Instrument ready for
candidate A/B; treat first-our-move divergences after budget overruns as
machine artifacts, judge candidates on leak classification + cp_loss
deltas, not fidelity.

## 10. 2026-09-09 — quality_ab's first candidate A/Bs: both probes stay OFF; KPK scoped next

With the instrument validated (§9), ran the two in-tree, gate-negative
probes through the real-clock corpus (`--env` only, zero code changes,
evidence `results/quality_ab/ab-seeprune/`, `ab-nulldeep/`, commit
84815a4). Decision rule = the tool's verdict checks; tie-break = leak
classification + mean cp_loss delta.

- **SEEPRUNE** (P1 pruning; 0.458 @500ms): **NULL at real clocks** —
  retained 1 (r71 Qg3, 243→275cp), avoided 0, replaced-worse 0, cand
  mean 55.7. Matches the gate; stays OFF; the leak family is confirmed
  NOT a qsearch capture-blindness class (consistent with the 3-FEN leak
  suite in BUILD.md P1).
- **NULL_DEEP** (P4; 0.438 @500ms): **NEGATIVE at real clocks, first
  mean_not_worse FAIL of the instrument** — cand mean 845.0 vs V5 768.1
  (n=70 vs 378). The r70 replay is the mechanism on tape: deepest run of
  the corpus (25/30 fidelity, played to end), then at the thinning clock
  it walked into a mating attack — f6?? 27870cp, fxg5 28213cp. R=3 at
  deep nodes skips exactly the refutation horizon the leak family lives
  in. The 500ms negative is confirmed; stays OFF.
  - **AUDIT CORRECTION (q5-audit2c, 2026-09-09, /tmp/chess-q5-audit2-report.md):
    the quality_ab leg of this negative is RETRACTED as evidence.**
    (F1) aggregate means are dominated by the referee's ±30000 mate-clamp
    (r70 = 97.6% of cand total; trimmed <1000cp the difference flips to
    n.s., Welch t=0.53); (F3) "fxg5 28113" (ply 51) and "Bf5 28878"
    (ply 59) are WHITE/opponent moves — the candidate's actual clamp
    blunders are f6 (27870, ply 50) + fxg5 (28213, ply 52); (F4) the
    R=3-horizon mechanism is not established — V5 walked into the same
    mating attack in the REAL game (f6?? is in the V5 baseline) and the
    rerun produced different blunder moves of the same class (h6??/g4??),
    i.e. real-clock-timing dice, not a deterministic signature. Stays
    OFF on the 500ms gate alone (0.438).

**Verdict: ship state stands — every toggle OFF, V5 is the best known
build on this corpus.** SEE ordering not re-run (no leak mechanism +
strictly negative gate); aspiration re-test at real TC stays backlog
#3. quality_ab is now the standing ship gate for any pre-freeze change:
PASS = leaks avoided ≥1 AND replaced-worse 0 AND b+m not up AND mean
within +10cp.

**Next mission scoped (backlog #1, KPK technique gap, "OPTION A"):** the
residual endgame hole is KPK-b @2s (shuffle-suite 11/12; defender held
opposition) and |mat|=100 < the 300 gate means conversion terms
deliberately don't fire there. Two routes, decide on evidence:
(a) **Syzygy tablebase as shipped data** — explicitly permitted
(ORIGINALITY.md allowed-4, chess.syzygy in the base image): ship a
selective ≤5-men WDL subset under the 50MB zip cap, probe in get_move
when men ≤ 5 (win → DTZ-min move, loss → hardest defense, else search).
Exact, kills the whole late-endgame class incl. KRvK flakiness (§5 #4);
risks: init-time TB load vs 60s budget, 2GB RAM mmap, zip budget.
(b) **KPK technique terms in the hand eval** (passed-pawn push +
king-opposition proxies) — Phase 3.1 precedent says endgame terms can
regress at gate TC; gate at BOTH 300ms and 2s + full quality_ab corpus.
Either route: perft/eg_check/shuffle suites + 60s init check mandatory,
quality_ab PASS required before rebuild of agent.zip.

## 11. 2026-09-09 — P8 COMPCLAMP probe: fully gated, stays OFF; quality_ab stats patch shipped

Implemented the P8 compensation-aware clamp behind CHESSATHON_COMPCLAMP
(default OFF; commit 2a115cd, design pre-registered in BUILD.md "P8"
BEFORE gating). Rule: at phase ≤ 16 with raw |mat| ≥ 200, White-POV
score clamps to within 120cp of material (min for the deficit side, max
for the rich side). Integer-only, no tuner params, mate-drive untouched.
Tooling: quality_ab stats patch per audit F1/F2/F5 (a2d7003) —
winsorized+median cp_loss, faced/total denominators, trimmed-mean
verdict check; det_check.py fresh-process determinism probe; leak_probe.py
list-format leak-suite runner.

**Gates (BUILD.md "P8" has full numbers):**
- OFF = byte-identical V5: static parity 5/5 + node-identity 1,686,741
  @d8 both trees. perft ALL PASS. Clamp-effective: every deficit-mover
  armed FEN stops reading equal (r68 p65: −1100 where V5 read +1100).
- L1: 24@500ms vs HEAD seed 7 zero flags — **8W-12L-4D = 0.417, below
  the 0.45 line → NEGATIVE, decision made at L1.** eg_check 7/8 (KPK-b
  draw = pre-existing gap: V5 control drew it too, same box/session);
  shuffle 7/10 vs control 9/10, no threefolds either side.
- L2 leak probes @2.6s: non-regressive (0 new ≥300cp degradations, 2/54
  moves changed on non-armed FENs, +25/−8cp); searched scores on armed
  FENs shift ~0 — the clamp fixes STATIC leaf texts; V5's 2.6s search
  already saw the material truth at leak plies. (Operator later flagged
  the FEN corpus for wrong-side rows; re-verified by FEN-turn — 0
  mismatches on disk, verdict unchanged excluding the flagged games.)
- L3: SF19-e2200 @1200ms **5W-5L-0D/10** (driver wedged at game 11,
  operator killed it, 10 count) vs V5 reference 1W-4L+1aborted — not
  worse, small n.
- L4: not run (no new heavy runs; window consumed). Patched instrument
  self-tested on r70 HEAD: fidelity 25/30, trimmed 111.1 vs 120.5.

**Verdict: ship state unchanged — every toggle OFF, V5 remains the
best-supported build.** Fourth consecutive probe in the 0.41-0.46 gate
band (asp 0.438 / SEE 0.438 / SEEPRUNE 0.458 / COMPCLAMP 0.417): the
500ms n=24 gate cannot discriminate eval-surface changes. Standing
lesson recorded in BUILD.md: a deficit signal that changes MOVE
SELECTION (root-layer, e.g. contempt-style) is the shape that could
actually move games — it would need the real-clock SF bout as primary
instrument, not this gate. quality_ab now carries audit-proof stats as
the standing A/B instrument (F1/F2/F5 fixed; F3/F4 narrative already
corrected in §10).

## 12. 2026-09-09/10 — night build session: 3 correctness fixes, all gated PASS; v6 uploaded; r90 loss

Post-codex1 fix round (brief: /tmp/brief-chess-q5-fix1.md + night extension).
Uploads close 11 Sep 10:00 UTC; ladder resumes 07:00 UTC.

**v6 (null-sign fix) uploaded ~20:45 UTC by Pino** on L1 0.708 + clean L2 +
corrected-algebra argument (commit aebee58).

**q5-fix1 gates (aebee58):**
- L1: 24@500ms vs V5 (3aaaf99) — **16W-6L-2D = 0.708**, zero flags. First
  above-null-band L1 since Phase 4 (null band was 0.41-0.46).
- L2: corrected 78-FEN corpus @2.6s — mean score delta -5.0cp, 18/78 moves
  changed, one >=300cp row (r76 p122: mate-range, eval_before -959 — score
  noise on a lost position, not a leak). mate_stratum (20 rows, labeled):
  3 changed; candidate FINDS MATE at r81 p82 (29987 vs V5's 1853) — the
  corrected null sign converts deep mate lines the old sign rejected.

**q5-night1 (3c06692) — insufficient-material zeroing:** `mins` counted only
bishops → KBN-v-K (FORCED WIN) evaluated 0; KNNN also 0. Knights now counted;
rule simplified to total-minors<=1 (KB/KN/KvK still 0). KBN +875, KBB +902,
KNNN +864; mate-drive now arms on these. Tuner forced_zero mirrored.
eg_check 8/8 @300ms (KPK-b converts); **L1 vs v6 12W-6L-6D = 0.625 PASS**,
zero flags. KBN conversion at 300ms/2000ms still horizon-limited (pre-existing
Phase-3.1-class limit — eval correct, search can't see the 15+ ply mate net).
Known pre-existing: tuner check_parity 7/50 fails on the OLD tree too
(score_white doesn't model mate-drive; training-side only).

**q5-night2 (f5ce5de) — pawn PST rows flipped at hand-assembly** (docs/
research/07 spec item 1): tables authored rank-8-first, consumer rank-1-first;
both sides' home pawns read the 50/80 row; advancement cost ~45mg/69eg. THE
phantom mechanism. **r83 pre-leak statics collapse +78..+318 -> -21..+92**
(referee -43..-174); r70-B -26 -> -185 (referee ~-500). Startpos unchanged
(symmetry). Selfcheck: dropped st4<st5 (shape-contingent: blocked-bonus vs
doubled-penalty nets +4cp under the intended orientation — intended semantics);
kept advance-reward invariants. perft ALL PASS; **L1 vs night1 24W-0L-0D
= 1.000**, zero flags (the flip is decisive at gate TC: removes a ~1-pawn-level
error every position); L2: our-side leak scores drop mean -95.9cp toward
referee truth, moves changed on the exact leak rows in the intended direction,
one nominal >=300 row (r68 p41: V5's 0 was the wrong read, candidate -771
closer to -1276 truth); eg 8/8; shuffle 11/12 (KRvK-close-w threefold —
CORRECTED in §13: the quiet-box re-run Sep 10 shows night3 WINS this case
both colors; the threefold was load contention. The control artifact also
reads 11/12 with a DIFFERENT failed case (KPK-w), not this one — the
"10/12 / V5 control 10/12" phrasing committed in 2615f8a was a miscount);
det identical 493,820 nodes.

**q5-night3 (9a85717) — root ordering uses previous best_move:** root re-
ordered with ttmove=0 every iteration; prior best lost its priority slot and
PVS re-searched it full-window. Pass best_move into the ttmove slot (0-safe
iteration 1). Node-level: r83-p21 d8 493,820 -> 230,245 (-53%), same best
move. **L1 vs night2 12W-7L-5D = 0.604 PASS**, zero flags. det identical x2.

**r90 WATCH (v6's first ladder game): LOSS 0-1 vs Chessbuster 9000 (Black,
mated).** SF19 review: 35 best/7 exc/3 good/9 inaccur/3 mist/**2 blunder**.
Only ONE real error (Nf8 ply 63, 508cp); Ke1 (26534) is the forced-mate clamp
— game already lost; tail all best. NOT the leak family: a single tactical
miss vs an 1800+ opponent, then correct desperation.

**Record bout (real-clock-mode 120s+0.5):** infra took 3 attempts (budget
line not honored → `global` missing in the patched side → per-tree numba
caches); driver+deep-warmup engine_side preserved at /tmp/q5l3/. ONE completed
game before the queue reprioritized: **pair3_g1: v5-as-White 0-1 vs candidate
in 154 plies — candidate WON as Black**, zero flags
(results/bout_q5fix1/). Partial record; the night queue superseded it.

**Staged (NOT uploaded): /tmp/night-candidates/**
`chess-v7-night1-egfix.zip` (3c06692), `chess-v7-night2-pstflip.zip`
(a1feaf5), `chess-v7-night3-rootorder.zip` (2615f8a — lead candidate; all
files md5==commit, init 48.5s, first move legal, 34.5KB).

Night verdicts: item1 FIXED+PASS (0.625), item2 FIXED+PASS (1.000 —
strongest gate result of the event, mechanistically explained), item3
FIXED+PASS (0.604 + -53% nodes). Ship recommendation for the morning:
night3 (2615f8a) is the gated build. **L3 REAL-CLOCK BOUT DONE (01:20 UTC
Sep 10): night3 vs V5 12-0** (6 pairs x 2 games, 120s+0.5 emulation via
tools/bout_pair.py — per-move budget = time.py policy, per-tree numba
caches, banner-sync warmup; 6W as White + 6W as Black, 61-154 plies,
zero flags; results/bout_l3_v7/). The 1.000 L1 sweep reproduces at real
clocks — the inverted-PST error was a real ~1-pawn-class tax on every
position and night3 collects it both colors. Remaining pre-freeze
instruments for night3 (SF19-e2200 bout + quality_ab corpus) were NOT run
before upload — that waiver is recorded explicitly in §13 (audit-4 ask 4).
**v7 = night3 was uploaded Sep 10 06:19Z and is ACTIVE** (release-
identity + full ship record in §13).

## 13. 2026-09-10 — v7 ship record, audit-4 (codex4) resolution, repo hygiene pass

**v7 shipped (night3 = q5-fix1 + egfix + pstflip + rootorder).** Uploaded
Sep 10 06:19Z (07:19 London); validation building->valid 06:20-06:22Z
(init 48.7s / 39.8s warmup in the two smoke games, both draws by
ply_cap); status Active — v7 plays r91 and every round after. **Release
identity:** the dashboard's published submission sha `d5d57f6a6e4a` equals
the sha256 of the staged artifact `/tmp/night-candidates/
chess-v7-night3-rootorder.zip` (`d5d57f6a6e4a42b8...`); all 7 shipped
files in the zip are byte-identical to the working tree, and
`git diff 2615f8a..HEAD -- agent.py engine/` is empty — the uploaded
artifact == the gated night3 tree == the commit record. (Same pattern
corroborates v6: zip sha256 `71c172ee28a7...` == its dashboard sha.)
All seven submission validation logs are preserved at
`results/dashboard/aichessathon-v*.log`.

**v6 ship record (backfilled).** Submitted Sep 9 20:39Z, validated/Active
20:42Z (sha 71c172ee28a7) = the null-sign fix (aebee58), gated L1 0.708;
played r90 as its first ladder game (review: report 16). Superseded by v7
Sep 10 06:22Z.

**Audit-4 (codex4) resolution — all four asks:**
1. *Shuffle evidence discrepancy* -> resolved + corrected. The flagged
   night2 artifact does show a KRvK-close-w threefold; the V5 control
   artifact's one draw was KPK-w (no threefold), so the "documented
   flake band / V5 control 10/12 too" framing did NOT match the artifacts
   (both read 11/12; "10/12" was a miscount — corrected in §12; the git
   message stands as-is, messages are immutable). Quiet-box re-runs
   Sep 10 (single suite at a time, no co-load; candidate x2, control x1):
   candidate W(39) / D(142, no 3x) + [loaded] D(150) w/ threefold;
   control D(150) w/ threefold + [loaded] W(59). **Classification:
   KRvK-close-w is a variance-prone boundary case for BOTH builds
   (~1 conversion per 2-3 attempts, load-independent). No night3-specific
   regression.** Raw evidence: results/night_evidence/
   shuffle_quietbox_repro_20260910.txt.
2. *Attach det/KBN/eg evidence to the night source* -> done. Recovered
   verbatim from the fix1 session trace into `results/night_evidence/`
   (det: 493,820 x2 identical on night2, 230,245 x2 identical on night3,
   same best move 47988 score -50; KBN battery pre/post incl. the full
   rows 875/870/864/902/897 + true-insufficient exactly 0; eg 8/8
   artifacts for item1/item2/fix + the V5 control run; perft; the 3
   shuffle artifacts). 13 files, provenance headers inside each.
3. *Package/verify the frozen source* -> done: v7 zip byte-verified
   (above); night1/2 zips remain in /tmp/night-candidates/ for reference
   only.
4. *Record waived/replaced instruments* -> **waived for v7: SF19-e2200
   real-clock bout + quality_ab corpus.** Ship decision stood on L1
   (0.604 vs night2) + L2 (night2 corpus probes; leak scores toward
   referee truth) + L3 (real-clock bout night3 vs V5 12-0, color-balanced,
   zero flags) + the correctness-fix chain. Accepted exposure: no
   whole-game leak-class instrument for v7; levers = 6/day upload slots +
   today's ladder watch; rollback target if v7 shows leak-family losses =
   v6 (null fix) while investigating.

**Hygiene pass (this commit series).**
- Removed 43 untracked `results/matches/round-NN-vs-unknown.pgn`
  duplicates written by an overnight FULL re-fetch (Sep 9 21:44):
  r48-75 differed from the committed files by exactly 2 tail bytes
  (capture junk after the result token), r76-90 were byte-identical.
  Root cause: the one-off fetch script's `-vs-unknown` fallback on a
  partial metadata parse. Fixed forward in `tools/fetch_dashboard.py`
  (add-only, junk-tail strip, fail-loud on empty metadata, SSR/RSC row
  dedupe). 3 genuine round-log gaps filled add-only (r48/r68/r90 `.log`).
  Tracked round files untouched; audit trail (git history) unaffected.
- r90 review artifacts committed (black-deep.json = codex3's cited
  evidence; sf18 depth pass; superseded intermediate black.json dropped
  as untracked).
- Dashboard snapshot refreshed through r90; all v1-v7 submission
  validation logs preserved.
- Night evidence backfilled: `results/night_evidence/` (13 files).
- `docs/research/` renumber: 07-pst-phantom -> 08 (collision with
  07-brainB); INDEX rows for 06-17; audit reports 09-17 archived verbatim.
- Agentic archive extended: +16 briefs, +9 reports, +23 raw traces
  (39 total, ~33 MB raw -> ~6.6 MB gz); sessions/README.md index updated;
  AGENTIC-PROCESS.md §2b/§3b timeline + retrospective items 10-15.

**Open/parked:** three idle herdr panes remain parked (fix1, codex3,
codex4 — idle, no work in flight); the pre-freeze instruments not yet run
for v7 (ask 4 above); freeze Sep 11 10:00 UTC; ladder rounds hourly
07:00-21:00 UTC.
