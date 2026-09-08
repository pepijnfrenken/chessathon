# Chessathon — agent context hook

<!-- AIWG:claude-md-hook:start -->
This block is managed by `aiwg regenerate`. Operator content above/below is preserved.
<!-- AIWG:claude-md-hook:end -->

## ⚠️ MANDATORY — READ FIRST (every agent, every mission)

- **`ORIGINALITY.md`** — the competition's originality/compliance rules and
  what is allowed vs forbidden in this repo. **Read it before writing ANY
  code.** The one-sentence rule: *everything shipped is code we wrote in
  this repo during this event (plus permitted data); if we didn't write it
  here, it doesn't ship.* No third-party engine code, no pretrained models,
  classical search only.
- **`BUILD.md`** — the design log / originality record. Update it as you
  build. This is what lets Pino explain the agent to a judge.
- **`PROCESS.md`** — the master project log: decisions, ladder results,
  setbacks, ideas backlog, open problems. Append to it at every milestone.
  Deep agentic record (briefs + raw traces): `docs/agentic-process/`.

## Project

AI Chessathon (London, Sep 2026). Build an original chess agent exposing
`get_move(fen, time_left_ms) -> uci` in `agent.py`. Env: 1 core, 2GB RAM,
no GPU/network, python-chess 1.11.2 + numba/numpy preinstalled, 120s+0.5s
clock, 60s init, pondering allowed, classical search is a full entry,
50MB zip. Research knowledge base lives in `docs/research/`.
