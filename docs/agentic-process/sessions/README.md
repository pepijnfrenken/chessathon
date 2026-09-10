# Raw agent session traces (gzipped)

Raw OMP session logs for every builder, auditor, tooling, and research agent
that worked on this repo (2026-09-07 → 2026-09-10). Each `.jsonl.gz` is the
full message stream of one agent run: the mission brief it received, every
tool call, its reasoning, and its final report.

**Read:** `zcat <file>.jsonl.gz | jq -c 'select(.type=="message")'`

**Index** (map in ../AGENTIC-PROCESS.md §2):

### Sep 7 — build day

| File (prefix) | Role | Phase |
|---|---|---|
| `…T06-32-38…` | Research WS1 | engine architecture KB |
| `…T06-32-41…` | Research WS2 | eval/testing KB |
| `…T06-32-44…` | Research WS3 | landscape/rules KB |
| `…T06-38-20…` | Research WS4 | models methodology KB |
| `…T07-02-21…` | Builder | Phase 1a (minimal agent) |
| `…T08-39-20…` | Builder | Phase 1b (numba core) |
| `…T10-28-15…` | Builder `phase2` | Phase 2 (eval parameterization) — died mid-run |
| `…T10-49-39…` | Builder `p2cont` | Phase 2 cont (tuner/SPRT) — died mid-run |
| `…T12-01-00…` | Builder `p2finish` #1 | Phase 2 finish — died (model cold-start) |
| `…T12-03-13…` | Builder `p2finish` #2 | Phase 2 finish — died (timeout hunt) |
| `…T12-12-42…` | Builder `p2finish` #3 | Phase 2 finish — COMPLETED |
| `…T13-20-29…` | Builder | Phase 3 (aspiration + LMR) |
| `…T14-46-22…` | Auditor | Phase 3 audit (parallel, read-only) |
| `…T16-22-30…` | Builder `egfix` | Phase 3.1 (endgame conversion fixer) |
| `…T19-43-06…` | Builder | Phase 4 (stateful agent) |
| `…T19-44-01…` | Auditor | Phase 4 audit (parallel, read-only) |

### Sep 8 — audit-2 battery, V5 ship, brainA/B, evening gates

| File (prefix) | Role | Phase |
|---|---|---|
| `…T12-21-05…` | Auditor 2-A (soundness hawk) | audit-2 — died mid-probe (provider empty-output); resumed below |
| `…T12-21-20…` | Auditor 2-B (strength skeptic) | audit-2 attempt 1 — boot-death |
| `…T12-21-24…` | Auditor 2-C (production) | audit-2 attempt 1 — boot-death |
| `…T12-26-40…` | Auditor 2-C (production) | audit-2 relaunch — completed → report 11 |
| `…T12-37-57…` | Auditor 2-B (strength) | audit-2 relaunch — completed → report 10 |
| `…T13-14-46…` | Auditor 2-A (soundness) resume | audit-2 — completed → report 09 |
| `…T14-31-26…` | Auditor 3 (builder-check) | P7+P8 key-fix verification — completed → report 12 |
| `…T19-17-25…` (631Z) | Research brainB | radical probes B — completed → report 07 (ran into Sep 9 07:21) |
| `…T19-17-25…` (793Z) | Research brainA (attempt 1) | died; relaunched |
| `…T19-37-57…` | Research brainA | radical probes A — completed → report 06 (ran into Sep 9 07:21) |

### Sep 9-10 — quality_ab, audit round 2, COMPCLAMP, codex 1-4, the night build

| File (prefix) | Role | Phase |
|---|---|---|
| `…T07-22-50…` | Tooling | quality_ab instrument validation (brief reused below) |
| `…T07-22-55…` | Auditor (qab) | quality_ab correctness audit |
| `…T07-47-15…` | Tooling 2 (resume) | quality_ab validation — completed |
| `…T10-08-34…` | Auditor round 2 | ship-gate audit — killed by operator (provider slot fight) |
| `…T11-36-20…` | Auditor round 2b (resume #1) | died; relaunched |
| `…T12-03-49…` | Auditor round 2b (resume #2) | completed → report 13 |
| `…T13-31-42…` | Builder `clamp1` | COMPCLAMP + L1-L4 gate stack — completed (BUILD P8) |
| `…T17-08-03…` | Codex 1 (initial) | fresh-eyes audit — short session, superseded |
| `…T17-11-11…` | Codex 1 (main) | fresh-eyes audit + runtime experiment → reports 14/15 |
| `…T18-33-00…` | Builder `fix1` | night queue: null-sign fix, egfix/pstflip/rootorder, L3 bout — final commit 01:19 Sep 10 |
| `…T20-55-29…` | Codex 2 | night re-audit attempt — aborted at launch |
| `…T21-53-00…` | Codex 3 | r90 loss review → report 16 |
| `…T22-57-35…` | Codex 4 | night2 re-audit — SHIP-AFTER-FIX-X → report 17 |

Originals: `~/.omp/agent/sessions/-projects-chessathon/` (same filenames,
uncompressed). 39 files total: 16 from Sep 7 (17.1 MB raw) + 23 from Sep
8-10 (~16 MB raw) → ~6.6 MB gzipped.

**Credential scan** (all 39, before archiving): clean. Two Sep 9 sessions
contain an *elided* cloudflared token fragment captured from `ps aux` output
(`eyJhIj...aSJ9` — literal ellipsis, not recoverable); one false positive as
before (public Mixpanel meta-tag in scraped page content).

**Notes:** briefs are reused across attempts of the same mission (audit-2
sound/strength/prod, audit-2b, codex-1) — one brief file covers all its
attempts. Several runs died on provider empty-output/mid-run wedges
described in PROCESS.md §13; their partial work survives in the traces.
