# AI Chessathon — Agentic Process Record

*How this engine was actually built: the full builder × auditor trail, with
briefs, raw agent traces, decisions, and evidence — so the process itself can
be audited, written up, or replayed later.*

- **Repo:** `/home/pino/projects/chessathon` (event: AI Chessathon, London, Sep 2026)
- **Build day:** 2026-09-07 (all phases below ran that day; ladder rounds r48–r61
  bracketed them). Upload of the final Phase-4 build: 2026-09-08.
- **Companion docs:** `BUILD.md` (engineering design log — verdicts, gates,
  risks) · `ORIGINALITY.md` (submission law every agent acknowledged) ·
  `docs/research/` (the knowledge base the research workstreams produced).

---

## 1. The agentic setup

One human (Pino) plus an orchestrator (Hermes, this session channel) drove a
fleet of autonomous agents:

| Role | What they did | Evidence in this directory |
|---|---|---|
| **Orchestrator** | Wrote every mission brief, launched agents in herdr panes, watched gates, took ship/revert calls on evidence, ran the retrospective | `briefs/*.md` |
| **Builder** | One phase per run: read `ORIGINALITY.md` + `BUILD.md`, implemented, ran gates, committed granularly with decision-carrying messages | `sessions/*.jsonl.gz` |
| **Auditor** | Read-only parallel agent: md5-snapshot the builder's working tree, re-verify in a `/tmp` copy, never touch the repo; findings → report file → orchestrator decides | `sessions/*…jsonl.gz` (audit briefs), git commits that fix their findings |
| **Research WS 1–4** | Parallel knowledge-base agents (architecture / eval-testing / landscape / models) that produced `docs/research/` before any build | `sessions/*…jsonl.gz` |

Agents ran as OMP sessions (model via FreeInference/featherless; deepseek
preferred, qwen fallback) in herdr panes with cwd = repo. Every final report
acknowledges `ORIGINALITY.md` — the traces show it, per-run.

**Gate tooling (all in `tools/`):** `perft_check.py` (movegen parity vs
python-chess), `eg_check.py` (won-endgame conversion suite),
`shuffle_check.py` (threefold-shuffle resistance), `trace_endgame.py`
(endgame trace probes), `gate_match.py` (+`_tree`) — 24-game 500 ms A/B gates,
`gate_match_tree.py` for tree-commit vs HEAD, `sprt.py` (trinomial SPRT),
`bench_nps.py`, `local_game.py`, `repro_case.py`, `engine_side*.py`
(subprocess sides with import-time config via `CHESSATHON_EVAL_CONFIG` /
`CHESSATHON_EVAL_GATE` env), `make_zip.sh` (submission builder: exactly
`agent.py` + `engine/`, import+JIT < 60 s check).

---

## 2. Timeline map — who did what, when, and what shipped

| # | Window (UTC) | Role / session | Brief | Commits | Verdict (evidence) |
|---|---|---|---|---|---|
| R0 | 06:32–06:51 | Research WS 1–4 (4 parallel) | `ws1-arch`, `ws2-eval`, `ws3-landscape`, `ws4-models` | `d00026b`…`8aa7ea9` | KB foundation: architecture plan, eval/testing infra, field strength (CCRL bar), models methodology |
| 1a | 07:02–~08:20 | Builder | `build-1a` | `338144f`…`7490d14` | Minimal pure-Python agent shipped; harness gate 17-7-0 zero flags; upload → ladder **47/351** |
| 1b | 08:39–~10:20 | Builder | `build-1b` | `92aa2b5`…`8ad206f` | Own numba board+movegen+search (perft-exact d1–5, ~865 knps); gate **22-0-0 vs 1a**, zip 35.5 s init |
| 2 | 10:28–13:17 | Builder ×5 runs (`phase2`, `p2cont`, `p2finish` ×3 attempts — two died) | `build-phase2`, `build-p2cont`, `build-p2finish` | `f4e13e4`…`6dc3dcb` | **Negative result, well executed:** hand eval ships — vs flat 0.479 (wash); Texel-tuned weights rejected 0.104 (0W-19L-5D); SPRT aborts 0-41-9 / 0-10-10; 735-game/60k-position provenance |
| 3 | 13:20–16:19 | Builder + **Auditor** (14:46, parallel, read-only) | `build-phase3`, `audit` | `3817bde`…`05d0101` | Aspiration REJECTED (gate 0.438, reverted `f621ba1`); LMR KEPT (0.542); 4 search-correctness fixes; auditor report → forensics fixes |
| 3.1 | 16:22–19:47 | Builder (egfix) | `egfix` | `6908a55`, `fc0098e` REVERT, `bcc1efa` | Endgame conversion fixer **REVERTED**: gates regress 0.417/0.396; regression pinned to qsearch stalemate probes, invariant to net scope (v3–v6 gates all ~0.417) |
| 4 | 19:43–21:00 | Builder + **Auditor** (19:44, parallel, read-only) | `build-phase4`, `audit` | `caede75`, `496b86a`, `49c4c0e` | **SHIPPED — first decisive gate win:** stateful anti-threefold agent + auditor-found qsearch knight-capture fix; **0.750 vs HEAD**, eg_check 8/8, shuffle suite zero threefolds |
| — | 2026-09-08 | Post-ship investigation | (this conversation) | `tools/replay_pgn.py` | Ladder r61 drawn by threefold (queen shuffle) — classification pending PGN replay: old-build lag vs legitimate defensive draw vs real bug |

---

## 3. Why the auditor and builder did what they did

The short version of a long day: **every phase was triggered by evidence —
ladder losses or audit findings — and every decision was made on gate
numbers, including the decisions to ship negative results and revert
promising-sounding features.**

### Phase 1a — get on the board, correctness first
Trigger: the ladder was live; data beats theory. Deliberately weak engine
(depth 3–4), harness gate 17-7-0, upload same day → 47/351 (top 13%).
En-passant crash found by the harness, fixed (`2b4cc14`). Lesson encoded in
the 1b brief: *correctness gates before strength.*

### Phase 1b — the real engine
Trigger: 47/351 with a pure-Python search = ceiling. Built own 0x88 mailbox
board + movegen + make/unmake + zobrist, perft-parity vs python-chess as the
non-negotiable gate #1, then ID/PVS/TT/qsearch/null/LMR/check-ext.
22-0-0 vs 1a. First ladder games with it: r48–r50 losses recorded as
`[results]` commits — the beginning of the loss-pattern corpus that drove
Phases 3/3.1/4.

### Phase 2 — the honest negative (and the pipeline that made it cheap)
Trigger: eval was material+PST-only; hypothesis: richer eval wins.
Builder parameterized eval into gateable term groups and built an A/B
harness + trinomial SPRT + numpy Texel tuner (IRWLS, bit-parity-checked
against the jitted evaluate). Two builder runs died mid-mission (cold-start
model stall; stale-SPRT conflict killed a live SPRT — see §4). A
**garbage-tuned-weights** commit briefly landed (`516ef8c`, qwen finisher
wired a degenerate fit) and was reverted same-day (`b1df520`, material
anchoring fix + real 60k-position self-play fit).
Result: rich hand eval ≈ flat eval (3W-4L-17D, 0.479 — a wash); tuned
weights catastrophically worse (0W-19L-5D, 0.104; SPRT aborts 0-41-9 /
0-10-10). **Decision: ship hand eval, document the negative.** Why not keep
tuning: with a 0-wins-in-50 signal and the eval not being the ladder loss
pattern, the next lever had to be search. This is the run that made
"gate evidence > optimism" the house rule.

### Phase 3 — search strength: one accept, one reject
Trigger: r49/r50 losses were tactics misses (hung pieces) = shallow search.
Builder added aspiration windows (Phase-3 first candidate) — **gate 0.438
(5W-8L-11D): rejected and reverted** (`f621ba1`), with the honest note that
short-TC gates punish re-search windows. LMR: **gate 0.542 — kept**. Four
search-correctness fixes shipped alongside (found via the auditor + builder
forensics). The parallel **auditor** (14:46, read-only, md5-snapshotted
tree, ran everything in a `/tmp` copy) verified the working tree before
ship — its report is the reason the Phase-3 ship was trusted. The
"aspiration rejected" lesson was written into the code as a comment in
`search_root` so future agents don't retry it blindly.

### Phase 3.1 — the endgame fixer that didn't survive contact with gates
Trigger: independent audit + fresh `eg_check` on HEAD showed won endgames
NOT converting (KQvK strong-as-white draw, etc.) — plus r54/55 would later
show shuffle-draws. Builder (egfix) added Manhattan drive + edge/prox
mate-net terms, a qsearch stalemate probe, and an endgame budget boost
(`6908a55`). **Gates: 0.417 / 0.396 — colour-symmetric regressions.
Reverted** (`fc0098e`) with the experiment preserved in BUILD.md Phase 3.1 +
`results/phase31/`. The builder then ran the diagnostic series (v3→v6
bare-king gates, all ~0.417): **regression pinned to the qsearch stalemate
probes, invariant to net scope** (`bcc1efa`). This pinning is what sent
Phase 4 in the right direction — the failure mode was repetition/conversion
mechanics, not eval terms.

### Phase 4 — the stateful agent (the decisive one)
Trigger: ladder r54/r55 — **won endgames shuffling into threefold draws**
with time on the clock; reproduced locally (KQvK/KRvK-w threefold at 2 s).
Root cause: the agent was stateless — `get_move(fen, …)` parsed each FEN
fresh, so the search could never see that a move repeated a REAL-game
position. Fix: rolling 32-key game-history window (both parities), rep[]
pre-seed in `search_root`, root refuses 3rd occurrences (eff 0) and
penalizes 2nd ones (−20 cp when not losing; a losing side may still repeat
= correct defense).
The parallel **auditor** (19:44) found, independently: **qsearch
knight-capture blindness** — `gen_moves` cap_only skipped ALL knight moves,
silently dropping captures worth up to 190 cp (`496b86a`). Builder +
auditor verified: empty-history fixed-depth byte-identical to HEAD
(provably inert when no history exists), perft ALL PASS, eg_check 8/8,
shuffle suite 12/12 @300 ms + 11/12 @2 s with **zero threefolds**.
Gate: **15W-3L-6D (0.750), zero flags — first decisive pass in the project
history.** Shipped, uploaded 2026-09-08.

### Round 61 (2026-09-08) — the open item
First rated game of the new build: drawn by threefold after a Qd6↔Qe7 queen
shuffle. The root logic says the new build *cannot* shuffle into a draw
when winning (3rd occurrence = eff 0; 2nd = penalty when not losing) — so
the draw is either a correct defensive hold (we were worse), an old-build
round, or a real bug. `tools/replay_pgn.py` replays the real FEN stream
through the shipped agent to classify it. *(Status as of this commit:
awaiting match PGN.)*

---

## 4. The retrospective — "it broke too many times" (Pino, after Phase 2)

Written into the Phase-3 brief as operational law after Phase 2's
breakages. Every item below cost real hours:

1. **Sprint discipline:** one search feature per agent run; commit +
   validate before the next. Never queue untested features.
2. **No long SPRT in the same run as code edits** — a stale-SPRT conflict
   killed a live run and confused results for hours.
3. **Kill leftovers before starting:** stale `sprt.py` / `engine_side.py` /
   `gate_match.py` processes from a dead agent silently corrupt the next
   run's evidence.
4. **Verify empty before each gate** (`ps aux | grep …`), and check for
   stale log files that a new run would append to.
5. **Model cold-starts kill agents:** the Phase-2 finisher died three times
   (12:01, 12:03, 12:12 runs — see traces) — once on the provider's
   "model is starting up" placeholder. Re-probe first; never burn a run on
   a dead endpoint. (Orchestrator memory: 401s are transient; deepseek
   preferred, qwen fallback.)
6. **Tuning is not the default lever** after Phase 2's negative — do not
   re-run the tuner without new evidence.
7. **Commit granularly, message = what + why + evidence** — the git log is
   the originality record judges read.
8. **Honesty is a gate:** negative SPRT → revert and say so. A rejected
   feature with a clean revert commit is a *good* outcome (aspiration,
   egfix). The BUILD.md reads like a lab notebook for this reason.
9. **Auditors are read-only and parallel:** md5 snapshot → `/tmp` copy →
   independent re-verification — they never write the tree, so their
   findings are trustworthy and their runs can't corrupt the builder's.

---

## 5. Provenance & how to read the traces

- `briefs/*.md` — the exact mission text each agent started with (source
  session id appended at the bottom; extracted verbatim from the session's
  first message). `build-p2finish` and `audit` were reused across attempts.
- `sessions/*.jsonl.gz` — raw OMP session logs (message stream: brief,
  tool calls, reasoning, final reports). 16 files, 17.1 MB → 3.6 MB
  gzipped. Read with `zcat file.jsonl.gz | jq -c 'select(.type=="message")'`.
  Originals live in `~/.omp/agent/sessions/-projects-chessathon/`.
- **Secret scan:** all 16 traces scanned for credential patterns before
  archiving. One regex hit, verified false positive: a public Mixpanel
  meta-tag (`meta-mixpanel-api-key`) scraped from aichessathon.com page
  content inside a research agent's web output. No keys, tokens, or
  credentials are present.
- Evidence logs: `results/*.log` (gates, eg_check, shuffle, SPRT, repros),
  referenced by commit messages — kept in-repo so every claim in the git
  history is checkable at the same revision.
- Zip hygiene: `make_zip.sh` ships exactly `agent.py` + `engine/`; this
  directory never enters the submission artifact.
