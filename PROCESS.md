# PROCESS.md — project master log

**The one place for everything: decisions, traces, progress, setbacks,
ideas, problems.** Updated by the orchestrator (Hermes) at every milestone —
keep the TL;DR fresh, append to the right section, never delete history.

- Deep engineering detail per phase → `BUILD.md` (the judge-facing design log)
- Agentic record (briefs, raw session traces, builder×auditor narratives) →
  `docs/agentic-process/` · research KB → `docs/research/` · evidence → `results/`

---

## 0. TL;DR — current state (2026-09-08)

**Engine:** original numba-jitted alpha-beta (own board+movegen, perft-exact),
hand-tapered eval, stateful anti-threefold (game-history repetition).
`agent.zip` 30 KB — `agent.py` + `engine/` only. HEAD `49c4c0e` + process commits.

**Ladder (build r61–63, first games of the stateful build, 2026-09-08):**
r62 **WIN** vs Forking squad (checkmate — first real conversion) · r61 draw vs
CrimsonBot (material +0 even; threefold created by *their* king shuffle) ·
r63 draw vs Ultimate32 (we were −2 — repetition **held a lost game**).
**All three verified correct behaviour of the shipped build** (exact-clock
replay + eval probe, see §6 P1): r61 = dead-equal hold (raw 0.00, every
alternative ≤ −21), r62 = converts, r63 = defensive draw allowed by design.

**Open items:** ladder rounds 51–60 match records missing · check current
rating on the leaderboard · uploads freeze 11 Sep 11:00 (freeze strategy:
§5/#5, §6 P5).

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
- **P3 — ladder record r51–60 missing** — pull from the dashboard if
  still available; if not, note the gap in the write-up (honest process).
- **P4 — current ladder rating/rank unknown** (last known: 47/351 was 1a).
  Check the leaderboard after r64–66 and log it here.
- **P5 — freeze strategy:** uploads close 11 Sep 11:00. Every change after
  r61-63 carries regression risk vs the 0.750-gated stateful build. Decide
  per idea (§5) on evidence, not on time-to-freeze anxiety.
- **P6 — round-61 stderr fingerprinting impossible** (identical warmup
  lines) — see §5 #8.

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
