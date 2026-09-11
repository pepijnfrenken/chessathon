# AI Chessathon — Agentic Process Record

*How this engine was actually built: the full builder × auditor trail, with
briefs, raw agent traces, decisions, and evidence — so the process itself can
be audited, written up, or replayed later.*

- **Repo:** `/home/pino/projects/chessathon` (event: AI Chessathon, London, Sep 2026)
- **Build days:** 2026-09-07 → 2026-09-10. Day 1 (Sep 7): phases 1a–4 below,
  with ladder rounds r48–r61 bracketing them; the Phase-4 build was uploaded
  Sep 8. Days 2–4: the audit batteries + V5 ship, the q5 instrument/fix
  rounds, and the v6/v7 upload chain — see §2b/§3b below.
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

Later phases added a **Codex lane** (openai-codex fresh-eyes auditors,
read-only, audits only — never builders/gates/ops; from Sep 9) and
**tooling** runs that validate an instrument (quality_ab) before it is
allowed to gate anything.

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

## 2b. Timeline map — the later phases (Sep 8 → Sep 10)

| # | Window (UTC) | Role / session | Brief | Commits | Verdict (evidence) |
|---|---|---|---|---|---|
| A2 | 09-08 12:21–13:46 | Auditors 2-A/2-B/2-C (+ sound resume) | `aud2-sound`, `aud2-strength`, `aud2-prod` | — (read-only) | Reports 09/10/11. 2-A found the EP-capture key corruption (→P7); P8 found by the builder's own all-legal-moves control sweep |
| B4 | 09-08 13:20–16:00 | Builder round B4 | (in-session) | `73c7d44`, `08d4cb6` + gate logs | P7+P8 fixed with falsification probes; tree A/B null (0.479) → shipped as **V5** on correctness (upload 16:49, sha 6abb1ca1) |
| A3 | 09-08 14:31 | Auditor 3 (builder-check) | `aud3-builder` | `9162302` (gate logs) | Fix round verified on a fresh snapshot incl. probe sensitivity → report 12 |
| BA/BB | 09-08 19:17 → 09-09 07:21 | Research brainA / brainB | `brief-brainA/B` | — | Ranked probe menus → reports 06/07 |
| P4/SEE | 09-08 21:00 → 09-09 00:30 | Builder (in-session) | — | `7c08f42`, `ce5c774` + SEE gates | NULL_DEEP 0.438 → **REVERTED**; SEE 0.438 / SEEPRUNE 0.458 → stay OFF |
| T | 09-09 07:22–07:47 | Tooling + qab auditor | `q5-tooling`, `q5-tooling2`, `q5-audit-qab` | `89971a6` | `tools/quality_ab.py` built + validated |
| A2b | 09-09 10:08–12:46 | Auditor round 2 (+resume) | `audit2`, `audit2b` | `a2d7003` (stats patch) | quality_ab design verdict: replay mechanics sound, decision metrics clamp-dominated → report 13 |
| C1 | 09-09 13:31–16:20 | Builder `clamp1` | `clamp1` | `2a115cd`, `3aaaf99` | COMPCLAMP L1 0.417 → stays default-OFF |
| CX1 | 09-09 17:08–18:29 | Codex fresh-eyes (round 1) | `codex1` | — (read-only) | Wrong-sign null cutoff; inverted PST; lost root ordering → reports 14/15 |
| N1 | 09-09 18:33 → 09-10 01:19 | Builder `fix1` (night queue) | `fix1` | `aebee58` … `96d7397` (12 commits) | null 0.708; egfix 0.625; pstflip 1.000; rootorder 0.604; L3 bout night3 vs V5 **12-0**; zips staged |
| U6 | 09-09 20:39–42 | Operator | — | — | **v6 uploaded** (sha 71c172ee) — null fix live |
| CX2-4 | 09-09 20:55–23:03 | Codex rounds 2–4 | `codex2/3/4` | — (read-only) | codex2 aborted at launch; codex3 r90 review → report 16; codex4 night re-audit **SHIP-AFTER-FIX-X** → report 17 |
| U7 | 09-10 06:19–22 | Operator | — | — | **v7 uploaded** = night3 zip (sha d5d57f6a) → Active; release identity verified |
| H | 09-10 06:21→ | Orchestrator (hygiene) | — | `06782b2`… | Duplicates removed, night evidence backfilled, traces archived, records reconciled; quiet-box shuffle repro — see PROCESS.md §13 |

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

## 3b. Later phases — why each run happened (Sep 8 → Sep 10)

### Sep 8 — the audit battery and V5
The Phase-4 ship (Sep 8 morning) put a new build on the ladder, so a
three-persona audit battery (2-A soundness hawk / 2-B strength skeptic /
2-C production engineer) ran against the live engine. 2-A found the
en-passant hash corruption (P7); the builder's own all-legal-moves control
sweep then found the sibling castling-rights-vanish bug (P8) the battery
had missed — lesson: test every incremental-hash transition TO the
absent/zero state. Both were fixed with falsification probes on the unfixed
tree, and a tree-A/B gate read null (0.479) → **V5 shipped on correctness**
(upload 16:49). Auditor 3 then verified the fix round on a fresh snapshot
(the "verify-the-builder" pattern: diff hygiene + independent rerun +
probe sensitivity) → report 12. That evening brainA/brainB produced the
ranked probe menus (reports 06/07), and the builder gated P4 NULL_DEEP
(0.438 → reverted) and SEE ordering/pruning (0.438/0.458 → stays OFF).

### Sep 9 — instrument verdicts and the codex reframe
quality_ab was built and independently audited; audit round 2's verdict
(report 13): its replay mechanics are sound but the decision metrics were
mate-clamp-dominated — hence the L1-L4 stack where L4 alone can never ship
or kill. `clamp1` built COMPCLAMP behind a default-off toggle, gated to
L1 0.417 → stays OFF. Then the pivotal event: a cheap codex fresh-eyes pass
found what in-house replay tooling had missed for a day — a **wrong-sign
null-move cutoff** (a plain negamax algebra error on one score path), PST
tables consumed **vertically inverted** (home pawns credited the "advanced"
row), and root ordering that dropped the previous iteration's best move.
The codex runtime experiment (182 probes) reproduced the null defect and
also killed the time-multiplier hypothesis (2× budget repaired zero leaked
positions).

### Sep 9-10 night — the fix queue, every item gated
fix1 ran an ordered queue, one fix per commit+gate: null-sign fix → L1
0.708 (first above-null-band score in project history); insufficient-
material zeroing fix (KBN-v-K was scored 0; now +875) → 0.625; pawn-PST
flip (the measured phantom root cause) → L1 1.000 + leak-score collapse
toward referee truth; root ordering → 0.604 + −53% nodes at fixed depth
with the same best move. L3 real-clock bout: night3 vs V5 **12-0**,
color-balanced, zero flags. Zips for night1/2/3 were staged. v6 (null fix)
uploaded Sep 9 20:42; its first ladder game (r90) was reviewed by codex3 as
a single tactical miss, NOT leak-family. codex4's night re-audit returned
SHIP-AFTER-FIX-X = release identity + evidence reconciliation (no engine
defect found). v7 (night3) uploaded Sep 10 06:19, Active 06:22.

### Sep 10 — hygiene pass
A full dashboard re-fetch after midnight had written 43 `-vs-unknown.pgn`
duplicates; r90 review artifacts sat uncommitted; the night det/KBN/eg/
shuffle evidence lived only in /tmp + session traces; briefs/reports/traces
were unarchived; one PROCESS §12 line carried a garbled shuffle claim. All
resolved in the Sep 10 hygiene pass — audit-4's asks, the corrected numbers,
and the quiet-box shuffle repro (night3 wins the flagged case both colors;
the V5 control threefolded it; loaded parallel runs flake) are recorded in
PROCESS.md §13.

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
10. **Sign conventions are a first-class audit surface:** when a score-based
    verdict confuses, check negation on ALL score paths — the codex pass
    found the wrong-sign null cutoff after months of in-house tooling had
    missed it. Cheap fresh-eyes reads of independent code beat more
    in-house instruments.
11. **Evidence lands in the repo at commit time:** anything a commit message
    cites (det runs, KBN batteries, shuffle/eg outputs) must be a committed
    file — not a `/tmp` artifact or a line inside a session trace. The night
    QA numbers had to be recovered from session JSONLs during the Sep 10
    hygiene pass; don't make the next reader do that.
12. **Suites under contention flake:** a 2000 ms shuffle case threefolded
    while eg_check ran in parallel on the same box; the same case converts
    cleanly on a quiet box (night3 won it both colors, Sep 10 repro). Run
    decision-grade suites without concurrent load; re-run flaky cases quiet
    before classifying them.
13. **Reconcile numbers against artifacts before writing them into records:**
    a night-record line claimed "10/12 / V5 control 10/12" while every
    artifact showed 11/12 with *different* failed cases — a record that
    rounds off evidence framing invites the next auditor to distrust the
    whole entry.
14. **Release identity is byte-level:** dashboard sha == sha256(zip); verify
    the zip against the gated tree file-by-file AND `git diff` the shipped
    files since the gated commit. Done for v6/v7 (§13) — the uploaded
    artifact is traceable to its gate commits.
15. **Long runs can wedge silently:** real-clock bout drivers froze between
    games three times; agents error-looped on empty provider output. Poll
    file mtimes + process CPU, and prefer plain bash liveness loops over
    hub wait-chains.

---

## 5. Provenance & how to read the traces

- `briefs/*.md` — the exact mission text each agent started with (source
  session id appended at the bottom; extracted verbatim from the session's
  first message). `build-p2finish` and `audit` were reused across attempts.
- `sessions/*.jsonl.gz` — raw OMP session logs (message stream: brief,
  tool calls, reasoning, final reports). 39 files: 16 from Sep 7
  (17.1 MB raw) + 23 from Sep 8-10 (~16 MB raw) → ~6.6 MB gzipped. Read
  with `zcat file.jsonl.gz | jq -c 'select(.type=="message")'`.
  Originals live in `~/.omp/agent/sessions/-projects-chessathon/`.
- **Secret scan:** all 39 traces scanned for credential patterns before
  archiving. One regex hit, verified false positive: a public Mixpanel
  meta-tag (`meta-mixpanel-api-key`) scraped from aichessathon.com page
  content inside a research agent's web output. Two Sep 9 sessions contain
  an *elided* cloudflared token fragment from `ps aux` output
  (`eyJhIj...aSJ9` — literal ellipsis, not recoverable). No keys, tokens,
  or credentials are present.
- **Correction + amendment, Sep 11 (post-freeze release scan):** the
  "elided / not recoverable" reading above was wrong. The 11:36Z trace holds
  a **complete** cloudflared tunnel token — a 184-char base64url blob that
  decodes structurally to `{a: 32, t: 36, s: 48}` (account / tunnel / secret);
  the `eyJhIj...aSJ9` form was a tool-display truncation artifact, cosmetic
  only. The 22:57Z trace holds a 39-char truncated fragment (not usable).
  A full rescan — every tracked file (809), every blob of every commit
  (998 blobs / 213 commits), all 39 traces decompressed, plus a PII pass —
  found exactly these two traces and nothing else: no keys, cookies, bearer
  headers, or third-party personal data. Both files' token material was
  redacted to `[REDACTED-CLOUDFLARED-TOKEN]` on Sep 11. ⚠️ Pre-redaction
  copies remain in git history and in the session originals — **rotate the
  cloudflared tunnel token before this repo goes public**; rotation is the
  only fix that covers every copy.
- Evidence logs: `results/*.log` (gates, eg_check, shuffle, SPRT, repros),
  referenced by commit messages — kept in-repo so every claim in the git
  history is checkable at the same revision.
- Zip hygiene: `make_zip.sh` ships exactly `agent.py` + `engine/`; this
  directory never enters the submission artifact.
