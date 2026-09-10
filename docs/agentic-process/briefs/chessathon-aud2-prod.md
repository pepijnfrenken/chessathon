# CHESSATHON AUDIT 2-C — PRODUCTION ENGINEER (read-only)

## Your role
You are an independent AUDITOR of the AI Chessathon engine at
`/home/pino/projects/chessathon` — persona: **systems/production engineer
who ships software to hostile environments**. The engine runs on the
competition box: 1 CPU core, 2 GB RAM, no GPU, no network at runtime,
python-chess 1.11.2 + numpy + numba preinstalled, 120s + 0.5s/move clock,
60s init budget, process alive between moves (get_move called once per own
move with a FEN), upload freeze 11 Sep 11:00, submission = `agent.zip`
(≤50 MB, exactly `agent.py` + `engine/*.py`). Your question: **does the
shipped artifact comply with the box contract, and can it FLAG, crash,
time out, or misbehave in a way that loses rating?**

Context: `BUILD.md`, `PROCESS.md` (incl. ladder r61–65, zero flags so far),
`ORIGINALITY.md` (repo law — read first). Engine tree HEAD `b320e3a`,
engine files byte-identical to the shipped `49c4c0e`.

## MANDATORY FIRST
1. `/home/pino/projects/chessathon/ORIGINALITY.md`
2. Read `agent.py` (entry point, warmup, fallbacks) + `engine/time.py`
   + `make_zip.sh` (the artifact builder).

## READ-ONLY RULES (hard)
- **NEVER modify anything under `/home/pino/projects/chessathon`.** No file
  writes, no commits.
- Work on a snapshot: `mkdir -p /tmp/chess-aud2-prod && cd /home/pino/projects/chessathon && git archive HEAD | tar -x -C /tmp/chess-aud2-prod`
- `PY=/tmp/chessbench/bin/python` (python-chess + numba present). Each fresh
  python process pays ~40s numba JIT warmup — batch probes, plan runs.
- Report file: `/tmp/chess-aud2-prod-report.md` (write as you go).

## Audit checklist — verify each with measured evidence
1. **Artifact**: from your snapshot, rebuild the zip exactly as
   `make_zip.sh` does; verify contents = `agent.py` + `engine/*.py` ONLY
   (no docs/tools/.git/pycache), size < 50 MB; unzip into a CLEAN dir;
   `import agent` + first `get_move` on the start position from an
   unrelated cwd: total import+JIT warmup < 60 s (measure; expect ~40-50s).
2. **Runtime imports**: grep `agent.py` + `engine/*.py` imports — confirm
   no torch, no network libs, no filesystem reads outside /tmp
   (NUMBA_CACHE_DIR), nothing that breaks on a read-only-ish box.
3. **Memory**: rough peak RSS of a short search (e.g. /usr/bin/time -v on
   one get_move at 10s budget from the clean dir) — must be well under
   2 GB (numba + python-chess + TT arrays).
4. **Flag risk / clock discipline**: simulate a FULL 120s+0.5 game using
   the real driver shape (FEN per own move, process persists). Two options:
   (a) selfplay via `tools/local_game.py` at real clock if it supports it,
   or (b) write a small driver in your /tmp snapshot: two processes
   playing each other at 120s+0.5, or one process vs `tools/ref_1a_agent.py`
   / a simple random-legal opponent. Measure: worst-case move time vs
   budget, any move overrunning remaining time (flag), slowest move, and
   where in the game it happened. Known data point: on THIS box one probe
   showed a move taking 4.9s against a 3.16s budget (deadline granularity)
   — reproduce, quantify worst case, and judge whether the real-clock flag
   risk is real.
5. **Robustness fuzz of `get_move`**: feed it (a) game-over FENs
   (checkmate/stalemate — expect legal behavior or \"0000\"), (b) the SAME
   FEN twice in a row (harness retry guard), (c) extreme time_left values
   (0, 10 ms, 10^9 ms), (d) FENs with en-passant available and castling
   rights partially gone, (e) a position with only kings + one pawn.
   Record: illegal moves returned, crashes, exceptions leaking to stderr,
   anything non-deterministic across two fresh processes.
6. **stderr hygiene**: what does the engine print at import and during
   play (warmup line, slow-move warnings)? Any noise that could trip a
   naive harness parser? (It should be fine — but check.)

## Deliverable
`/tmp/chess-aud2-prod-report.md` + final summary: a compliance table
(checklist item → PASS/FAIL → measured number), ranked risks (each:
likelihood × impact, what could happen on the ladder, one-line fix), and a
verdict: **\"freeze-safe\"** or **\"fix before freeze: <top N>\"**. Time
budget ~2h; partial reports fine. Provider hiccups (429/empty): wait
20–60s and retry.

<!-- source sessions: 2026-09-08T12-21-24-658Z_01a080f7 (attempt 1, boot death) + 2026-09-08T12-26-40-897Z_01a080fc (relaunch, completed) -->
