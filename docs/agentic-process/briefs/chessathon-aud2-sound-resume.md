# CHESSATHON AUDIT 2-A — SOUNDNESS HAWK — RESUME (read-only)

## Context
A previous run of this audit (deepseek-v4-flash, session 12:21) died mid-
probe when the provider returned empty responses. It left a DRAFT report at
**`/tmp/chess-aud2-sound-report.md`** with findings F1–F9. Your job: finish
it, validate the key finding, and deliver the verdict.

The engine: `/home/pino/projects/chessathon` (tree HEAD `b320e3a`, engine
byte-identical to the shipped `49c4c0e`; LIVE on the competition ladder,
upload freeze 11 Sep). Read `ORIGINALITY.md` first (repo law).

## NEW INFORMATION — F1 CONFIRMED by the orchestrator (direct code
inspection, engine/board.py `make_move_apply`, ~lines 236–256):
For EP captures (F_EP), the captured pawn is removed from the key at its
real square (`to -/+ 16`, line 239) — but `captured != EMPTY` is then true,
so line 255–256 XORs a **phantom removal from `to`** (`ZPIECE[to,
captured+5]`), a square where nothing was captured. Result: the zobrist key
is corrupted by one spurious XOR on every en-passant capture. `unmake`
restores via `prev_key` (save/restore), so make/unmake are self-consistent
within a search line, but the key diverges from the parse_fen truth after an
EP capture — which corrupts (a) the game-history pre-seed used by the
stateful anti-threefold repetition detection (real-game repetitions AFTER
an EP capture can be MISSED → threefold shuffle risk returns), and (b) TT
keying on post-EP subtrees. Determinism is unaffected.

## Your tasks (in order)
1. **Validate the F1 fix in YOUR SNAPSHOT copy** (`/tmp/chess-aud2-sound`):
   change line 255–256 to skip the removal for EP —
   `if captured != EMPTY and fl != F_EP: key ^= ZPIECE[to, captured + 5]` —
   then PROVE key parity: build positions containing an EP capture (e.g.
   `1. e4 d5 2. e5 d4 3. exd6 e.p.` — construct via python-chess and push
   moves so the FEN is exact), and verify
   `B.parse_fen(post_ep_fen)['key'] == key-after-make-and-back` (roundtrip)
   AND that a search making the EP capture produces keys matching
   parse_fen of the resulting FEN. Run determinism (two identical
   fixed-depth searches, byte-identical) and a perft spot-check (2–3 FENs)
   with the fix applied in the snapshot. Report before/after numbers.
   (Sanity: confirm the UNFIXED snapshot reproduces the mismatch — that
   proves the probe is sensitive.)
2. **Finish F7**: the perft-vs-oracle probe that was cut off — run
   `tools/perft_check.py` in your snapshot (plus 2–3 tricky FENs of your
   own: EP pins, castling through check, promotions).
3. **Verify or refute F2** ("empty-history byte-identical to no fix claim
   is false") with a concrete probe: run `search_root` with gcnt=0 on the
   shipped tree vs the pre-Phase-4 logic expectation — state precisely what
   differs and whether it matters.
4. **Finalize the report** at `/tmp/chess-aud2-sound-report.md`: fill in
   F1 (now CONFIRMED with the code-level evidence above + your probe
   numbers), F7, F2; assign severities; end with the verdict:
   **"fix before freeze: F1 (one-line EP-hash fix, parity-proven)"** or
   your reasoned alternative. Note the fix's regression risk honestly
   (one line, but it changes every EP-capture key — the parity probe +
   determinism + perft are the evidence it is safe; a full 24-game gate is
   the orchestrator's call, not yours).
5. Final summary in-session; keep the report file updated as you go.

## Rules
- HARD read-only on `/home/pino/projects/chessathon` — no writes, no
  commits. All work in `/tmp/chess-aud2-sound` (git archive HEAD copy).
- `PY=/tmp/chessbench/bin/python` (python-chess + numba; ~40s JIT warmup
  per fresh process — batch).
- Provider hiccups (429/empty content): wait 20–60s, retry. If the model
  returns empty responses 3× in a row, STOP and say so in the report —
  do not loop.
- Time budget ~1.5h; if you cannot finish, leave the report in a clear
  state with what remains.

<!-- source session: 2026-09-08T13-14-46-470Z_01a08128 -->
