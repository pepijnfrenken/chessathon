# Raw agent session traces (gzipped)

Raw OMP session logs for every builder, auditor, and research agent that
worked on this repo on 2026-09-07. Each `.jsonl.gz` is the full message
stream of one agent run: the mission brief it received, every tool call,
its reasoning, and its final report.

**Read:** `zcat <file>.jsonl.gz | jq -c 'select(.type=="message")'`

**Index** (map in ../AGENTIC-PROCESS.md §2):

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

Originals: `~/.omp/agent/sessions/-projects-chessathon/` (same filenames,
uncompressed). Scanned for credentials pre-archive — clean (one false
positive: public Mixpanel meta-tag in scraped page content).
