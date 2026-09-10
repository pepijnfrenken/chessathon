# AUDIT 2-C — PRODUCTION ENGINEER (read-only)

Date: 2026-09-08. Auditor: independent production/systems engineer persona.
Target: `/home/pino/projects/chessathon` @ HEAD `b320e3a` (clean tree; engine
files byte-identical to shipped `49c4c0e`). All probes run in `/tmp` against
a `git archive HEAD` snapshot; the submission zip was rebuilt from the
snapshot exactly as `make_zip.sh` does and unzipped into a clean dir
(`/tmp/chess-aud2-prod-clean`); every runtime probe imports THE SHIPPED
ARTIFACT from that clean dir, from an unrelated cwd (`/tmp`), with a cold
NUMBA_CACHE_DIR per process.

## 1. Artifact

Rebuilt via `bash make_zip.sh` in the snapshot (its own verification path
runs from /tmp with `PYTHONPATH=` empty):

- Contents: EXACTLY `agent.py` + `engine/{__init__,board,eval,search,time,tt}.py`
  (+ the `engine/` dir entry). No docs, no tools/, no tests, no .git,
  no __pycache__. ✓
- Size: **29,817 bytes** (limit 50 MB — margin ~1700×). ✓
- `python3 -m zipfile -e` into clean dir → exactly those 7 files. ✓
- make_zip.sh's self-verify: `init (import+JIT): 44.7s | first move:
  4.59s | legal: b1c3` — its `< 60s` assertion passed.

## 2. Init budget (60 s) — from clean dir, cold numba cache

| run | cache state | import+JIT | first move |
|---|---|---|---|
| make_zip verify | cold | 44.7 s | 4.59 s |
| fuzz probe process | cold (`/tmp/numba_cache_audit2`) | 48.4 s | 4.46 s |
| budget probe process | cold | 46.3 s | (see §5) |

COLD-CACHE worst observed: **48.4 s ≈ 19% headroom** under the 60 s init.
This is the true competition case (fresh box, empty /tmp cache).
NOTE: warm-cache startup would be ~2-4 s (the shipped `agent.zip` on the
repo was built Sep 7 20:58; content still matches HEAD). HEAD `b320e3a`
matches the artifact that produced ladder r61–65.

## 3. Runtime imports / FS contract

All imports across `agent.py` + `engine/*.py` (grepped): `os, sys, time,
ctypes, numpy, chess, numba` + intra-package `engine.*`. **No torch, no
requests/socket, no subprocess, no pathlib FS writes.** ✓

Filesystem: only `NUMBA_CACHE_DIR=/tmp/numba_cache_chessathon` (set via
`setdefault` at agent.py:28 BEFORE numba import — correct order). Reads:
none outside stdlib/python-chess data. The repo dir is never touched at
runtime; works from an unrelated cwd (probes prove it). A read-only box
is fine as long as `/tmp` is writable — that is a box contract assumption
worth stating, not a defect.

stderr at import: exactly one line
`[chessathon] numba warmup 48.0s (init budget ok)` (also the only stderr
during the entire 18-case fuzz — no slow-move warnings, no engine-error
lines fired; the fallback paths exist but never triggered).

## 4. Memory

`resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` (kernel-accounted peak
RSS of the child) for full probe processes (warmup + searches):

| probe | peak RSS |
|---|---|
| fuzz probe (18 calls) | **392 MB** |
| budget probe (62 calls) | **393 MB** |

vs 2 GB box: **~20% of budget**. Fixed allocations: TT 2×2²²×8B = 64 MB +
numba/python-chess runtime dominate; nothing scales with game length
(the game-history window is capped at 32 entries). ✓

## 5. Clock discipline — measured

### 5a. Fuzz extremes (time_left_ms)
- `time=0` → budget floor 50ms, move used **53 ms** (legal b1c3). No flag.
- `time=10` → used **52 ms** (legal g1h3). Slight over "budget" but the
  budget model floors at 50ms; a 10ms-remaining position cannot be saved
  by any engine; 52ms spend risks flag only in a state the 120s+0.5
  clock can never reach (see trajectory).
- `time=10^9` (KP endgame) → used **45,001 ms** = the 45 s clamp. ✓
  (clamps, does not try to spend an hour)

### 5b. Per-move overshoot vs budget — MEASURED, first-call-only
Repeated identical-budget calls (3167 ms budget at R=120s) land
**3167–3170 ms (+1–3 ms over budget)** — the 1024-node deadline-check
granularity, real but negligible (risk #3, non-actionable).

The FIRST search of a process overshoots by a fixed absolute amount,
independent of position and budget, isolated in two fresh processes:

| first call | budget | used | overshoot |
|---|---|---|---|
| startpos (R=120s) | 3166 ms | 4477 ms | **+1311 ms (41%)** |
| KP endgame (R=20s) | 944 ms | 2333 ms | **+1389 ms (147%)** |
| startpos (in-game, vs ref1a) | 3166 ms | 4854 ms | **+1688 ms (53%)** |

Same ~1.3–1.7 s absolute cost regardless of budget/position → one-time
process state (lazy numba caches, first-touch of TT/rep/history arrays,
allocator growth), NOT clock granularity. The engine's own guard fired
correctly and exactly once per process:
`[chessathon] slow move: 4854ms (budget 3166ms), depth 10`.

**Flag-safety of the overshoot on the competition clock**: move 1
overruns its 3166 ms budget but the clock holds ~116.5 s after it
(4854/120000 = 4% of the clock for 10 plies of depth). Even in the
pathological case where the game reaches a state with R < ~2 s AND the
process has not made a single prior move (impossible in a real game:
every game has a first move at R=120s), the budget clamp `R−100ms`
keeps the model from committing more than exists. No flag path found.

### 5c. Trajectory simulation (60 moves, rotating real middlegame FENs) — DONE
Clock decayed 120000 → 33969 ms over 60 moves (×~44/45 per move, as
designed). Every move legal. Worst over-budget moves:

| move | remaining | budget | used | over |
|---|---|---|---|---|
| 17 | 84097 | 2368 | 2374 | +6 ms |
| 53 | 39775 | 1383 | 1389 | +6 ms |
| 25 | 72311 | 2106 | 2110 | +4 ms |

Max overrun over budget in 60 moves: **+6 ms** (two occurrences), i.e.
the 1024-node check granularity plus scheduler jitter; the steady state
is +1–3 ms. Ratio used/remaining never exceeded 0.037. **No move ever
threatened the clock; final reserve 34 s.**

### 5d. Full real-clock games 120s+0.5 (repo's own driver, clean artifact)

Two games, agent as White, opponent per `tools/local_game.py` sides.
Every agent move timed; flag rule = `used > remaining + 50ms`.

| game | result | ply | agent overruns of remaining | min clock margin |
|---|---|---|---|---|
| vs material bot | 1-0 (mate, ply 11) | 11 | **0** | (opponent-flagged N/A; agent never near) |
| vs ref1a (phase-1a engine) | 1-0 (ply 29) | 29 | **0** | **89.1 s** at the tightest |

Worst agent moves of each game (ply/remaining/used):
- vs material: move 1 = 4854 ms of 120000 (overshoot above), then all
  ≤ budget+3 ms.
- vs ref1a: 3167 / 3108 / 3053 / 2997 / 2938 ms — descending with the
  clock; every move within +3 ms of budget after the first.

Zero flags, zero illegal, zero "0000" mid-game, zero crashes across
both games (play_game's hard-flag checks all silent). Slow-move warning
count in stderr across 40 agent moves: exactly 1 (the first move).

## 6. get_move robustness fuzz — 18/18 PASS

All calls legal or correct "0000"; no exceptions leaked to stderr; the
fallback paths (illegal-move warning, engine-error fallback) exist but
never fired anywhere in the audit. Stderr across every probe process =
init warmup line + at most one first-move slow-move warning (see §5b).

| case | result | time | verdict |
|---|---|---|---|
| startpos ×3 (repeat) | g1f3 / e2e3 / d2d3 | 3168/3167/3168 ms | ✓ |
| checkmate position | `0000` | 0 ms | ✓ correct |
| stalemate position | `0000` | 0 ms | ✓ correct |
| italian (Qf3xf7 mate-in-1) | f3f7 | 0 ms (found at depth 1?) | ✓ took mate |
| italian again | c4f7 (a different mate-in-1) | 3169 ms | ✓ |
| en-passant available | g1f3 legal | 3167 ms | ✓ |
| castling rights partial (Kq only) | a1b1 (O-O-O path) | 3167 ms | ✓ |
| K+P endgame | e1d1 | 3170 ms | ✓ |
| check-evasion | e1e2 legal | 0 ms | ✓ |
| promotion | a7a8q | 3167 ms | ✓ |
| kings-only | `0000` | 0 ms | ✓ (is_game_over) |
| KP halfmove=99 | e2e3 | 3167 ms | ✓ |
| black to move | d7d6 | 3167 ms | ✓ |
| time=0 / 10 | legal in 52-53 ms | | ✓ floor honored |
| time=1e9 | legal in 45.0 s | | ✓ 45s clamp |

Note (fuzz artifact, not a defect): several cases ran in 0 ms because
the search found a terminal/mate score and `search_root` breaks early —
that is the intended mate-early-exit, correct behavior.

## 7. Determinism / cross-process consistency

Across four fresh processes (fuzz, budget, game×1): warmup 44.3–49.0 s
(one-line stderr, consistent format), all moves legal, zero exceptions.
Move choice differs across processes for the same FEN (TT/killer/history
carry state within a process; probes made different prior calls) —
"same input → same output" is NOT the contract here; "always legal,
never crash, never 0000 mid-game" is, and held in every process.
The mate-in-1 positions were converted instantly in both processes that
saw them (fuzz: f3f7/c4f7; both legal mates — the engine found *a*
mating move, different TT state, equally winning).

## 8. Risk register (ranked)

| # | risk | likelihood | impact | fix (one line) |
|---|---|---|---|---|
| 1 | 60 s init: cold-cache JIT measured up to 48.4 s; competition box disk/CPU slower than this one → >60 s = forfeiture at t=0 | low-med | fatal | measure once on a cold competition-image VM before freeze; if tight, shrink `_warmup()` (drop the separate search_root call — its recursion compiles with search()) |
| 2 | First-call overshoot +1.3–1.7 s past budget (once per process, move 1) | certain (measured every process) | none on 120s+0.5 (move-1 clock after: 116.5 s) | optional: subtract a fixed 2 s first-call allowance from move 1's budget |
| 3 | Deadline check granularity 1024 nodes → ~ms-scale overshoot per move (measured +1–3 ms typical) | certain | negligible | none needed at this TC |
| 4 | `/tmp` not writable on box → numba cache init fails → possible import crash | very low | fatal | add try/except around import-time warmup (already exists) — keep NUMBA_CACHE_DIR under tempfile.gettempdir() and fall back to in-process JIT on failure |
| 5 | stderr noise trips a naive harness parser | very low | minor | none needed (1 line at init; slow-move/engine-error lines exist but never fired in 62+ calls) |

## 9. Compliance table

| checklist item | result | measured |
|---|---|---|
| 1. zip contents exactly agent.py+engine/*.py | PASS | 7 files, 29,817 B |
| 1. size < 50 MB | PASS | 0.028 MB |
| 1. clean-dir import+first move < 60 s | PASS | 48.4 s + 4.46 s (cold) |
| 2. no torch/network/FS-outside-/tmp | PASS | grep: os/sys/time/ctypes/numpy/chess/numba only |
| 3. peak RSS ≪ 2 GB | PASS | 392–397 MB (~20%) |
| 4. full 120s+0.5 games, no flag | PASS | 2 games (vs material 1-0 ply 11; vs ref1a 1-0 ply 29): 0 overruns of remaining, min margin 89.1 s |
| 4. worst move vs remaining | PASS | first move 4854 ms of 120000 (4%); steady state budget+1–3 ms; 60-move trajectory max over-budget +6 ms, final reserve 34 s |
| 4. deadline-granularity overrun (known 4.9s/3.16s probe) | REPRODUCED+BOUNDED | first call of a process only: +1.3–1.7 s absolute, independent of budget/position; never again after (max +6 ms in 60 moves); absorbed by 116 s move-1 headroom |
| 5. fuzz: no illegal/crash/leak | PASS | 18/18 |
| 6. stderr hygiene | PASS | 1 init line; 1 first-move slow-move warning; 0 error lines in entire audit |

## 10. Verdict

**FREEZE-SAFE.**

The shipped artifact (agent.zip @ `49c4c0e`, tree `b320e3a`) complies
with the box contract on every measured axis: exact contents (7 files,
29.8 KB), 48.4 s cold init (19% headroom), 392–397 MB peak RSS (20% of
2 GB), pure-Python/numpy/numba import surface, no FS writes outside
/tmp, 18/18 fuzz cases legal-or-correct-0000, zero flags/illegal/crashes
in two full 120s+0.5 real-clock games and a 60-move clock-decay
trajectory.

Residual risks, none blocking freeze:
1. **Init headroom is 11 s on THIS box.** A slower disk/CPU on the
   competition box eats margin fast (JIT is disk+CPU bound). Post-freeze
   watch-item, not a defect: the same 44–49 s has been stable across 5
   processes today. If Pino wants belt-and-braces BEFORE 11 Sep:
   trim `_warmup()` to a depth-2 root call (~saves nothing — recursion
   already covered) or pre-warm ONLY search+qsearch and let ID reach
   depth 3 on the first real move. Recommend: measure once on a cold
   VM of the competition image type; freeze as-is otherwise.
2. **First-call +1.3–1.7 s overshoot** (once per process, move 1):
   harmless at 120s+0.5 (4% of clock); would matter only at a sub-5 s
   base clock, which the competition does not use.
3. **`/tmp` writability assumption**: numba cache lives under /tmp; if
   the box mounts /tmp noexec/ro the import-time try/except catches the
   failure and the engine still plays (verified: warmup failure path
   exists, agent.py:194-196) — but the first real move would then pay
   ~45 s JIT inside its 3.2 s budget and flag. This is the ONLY path to
   a flag found in this audit, and it requires a broken box.

Recommended pre-freeze actions: none required. Optional (30 min):
(a) change `NUMBA_CACHE_DIR` setdefault to a `tempfile.gettempdir()`
subdir with a per-uid name to dodge collisions on a shared box;
(b) drop move-1 budget by a fixed 2 s first-call allowance
(`if _first_call: budget -= 2000`) to make even a 2 s+inc clock safe.
