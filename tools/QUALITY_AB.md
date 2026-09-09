# QUALITY_AB — local pre-upload quality A/B

`tools/quality_ab.py` answers one question before every upload: **is the
candidate build locally better than the shipped V5 on real ladder games?**
It replays the candidate against the actual ladder opponents (the opponent
follows the recorded PGN moves) with the exact `%clk` clocks the ladder
gave us, then scores both the real game (V5's moves) and the replay (the
candidate's moves) with an independent referee — Stockfish 19 at a fixed
depth — and classifies what happened to V5's mistakes.

SF lives outside the repo (`~/.local/bin/stockfish`); it is a *referee*,
never shipped code (see ORIGINALITY.md §allowed-5).

For `--candidate HEAD` the aggregate verdict is WEAK/FAIL **by
construction**: the candidate cannot beat itself, so pre-divergence V5
leaks come out `retained` and `leaks_avoided>=1` cannot pass. The
self-test pass signal is instead: (a) fidelity ≥ 90%, or (b) every
divergence traced to the LIMITS-#3 machine-artifact class, plus
`replaced-worse == 0` throughout.

## Usage

Run from repo root, sequential only (SF reviews use Threads=6; replays are
real-clock and load-sensitive — never alongside a 500 ms gate):

```
PY=/tmp/chessbench/bin/python
$PY tools/quality_ab.py --candidate HEAD \
    --game round-74-vs-rohan.pgn:white --game round-70-vs-kingsguard.pgn:black \
    [--env CHESSATHON_SEE=1] [--sf-depth 16] \
    --out results/quality_ab/<label>
```

- `--candidate HEAD` replays the live tree; a commit sha replays an
  archived snapshot (`git archive` into `<out>/candidate_tree/`).
- `--game <name>.pgn:<white|black>`, repeatable. The `.pgn` suffix is
  optional. Standard corpus = the 7 leak-reviewed games r64/r68/r70/r71/
  r72/r73/r74 (reviews cached in `results/leak_reviews/<name>.sf16.json`).
- `--env K=V` passes engine toggles to the replay worker (each worker is
  its own process because numba bakes toggle globals at compile time).

Per game the out dir gets `<name>.replay.{json,pgn}`,
`<name>.replay.sf16.json` (the referee's review of the replay), plus
aggregate `REPORT.md` + `report.json`.

## Self-test semantics

`--candidate HEAD` on a game the ladder played with V5 is the instrument's
self-test: the printed `SELF-TEST` line demands fidelity
(matched/our_moves) ≥ 90%. Mismatches at k=2/3 with a match at k=1 (or
vice versa) prove position passing, clock extraction, review caching and
k-index alignment all work — the pipeline is exercised end-to-end.

Fidelity below 90% is a **sanity alarm, not automatically a tool bug**.
Debug order (see LIMITS #3):
1. Retry once on a quiet box (replays are real-clock).
2. Check the replay JSON: which k diverged first, `took_ms` vs `tl_ms`
   (did the move overrun its own budget?), `stop_reason`.
3. Compare with the venue's `%clk` for the same move (did the venue also
   overran its budget there?).
4. Only then suspect the tool: exact-clock alignment (off-by-one, book-FEN
   games where black moves first), replay PGN construction (SetUp/FEN
   headers), review-cache path, leak-classification k index.

## Interpretation

The referee classifies every our-move by cp_loss at fixed depth
(`tools/review_sf.py`: ≤10 best, ≤40 excellent, ≤90 good, ≤160
inaccuracy, ≤300 mistake, >300 blunder; "brilliant" = sacrifice ≥3 pt
that still scores ≤20 loss). cp_loss is from the mover's POV,
E_i + E_{i+1} over consecutive SF evals.

V5's blunder/mistake plies ("leaks") are classified against the
candidate's move at the same our-move index k:
- **retained** — candidate plays the same bad move;
- **replaced_worse** — candidate avoids it but its own move is also
  blunder/mistake;
- **avoided** — candidate avoids it with a ≤-inaccuracy move (pre-divergence
  plies only; after a divergence the candidate never faces that position
  and the leak is counted **unreached** — conservative by design).

Aggregate verdict `PASS (locally better)` requires ALL of:
`leaks_avoided>=1`, `no_replaced_worse`, `no_more_blunders` (b+m count),
`mean_not_worse` (mean cp_loss within +10 cp noise). 2/4 checks =
`WEAK`, less = `FAIL`. The 7-game corpus is small: read the numbers and
the leak entries, not just the label.

## LIMITS

1. **Proxy opponent follows the PGN.** After the candidate's first
   deviation the recorded opponent moves may become illegal in the new
   position — the replay stops there
   (`stop_reason: opponent PGN move illegal after deviation (ply N)`).
   Post-deviation candidate moves are still refereed standalone, but the
   game is no longer "the ladder game".
2. **Per-move scoring at fixed depth.** d16 cp_loss is SF19's opinion at
   that depth, not full-strength analysis; bucket boundaries near a
   threshold are noise-prone. Both sides are scored identically, so A/B
   deltas remain meaningful.
3. **Replay divergence is a machine artifact class.** Move choice depends
   on which iterative-deepening iteration completes inside the time budget
   (`engine/time.py`: remaining/45 + 500 ms). The venue box and this box
   land on different completed depths — measured, r74 move 1: venue
   played Nf3 in 4.2 s (its log's "Slowest 4.2 s"), the identical
   `agent.zip` build replayed here answers Bd2 in 4.5–5.1 s (JIT/TT-cold
   first move; budget 3166 ms — the venue overran its budget there too).
   Consequences: fidelity is a *sanity* check, NOT a build-identity
   check; a first-our-move divergence after a budget overrun is expected
   and deterministic per machine; and an A/B stays **valid** despite it,
   because candidate and V5 reviews both referee the moves each side
   actually chose under identical local conditions.
4. **Review caching.** `results/leak_reviews/<name>.sf<depth>.json` is
   reused for the real game when `--sf-depth` matches (default 16).
   Other depths regenerate reviews for all 7 games — heavy, sequential,
   plan ~10 min/game. Do not delete or regenerate the cached reviews.
5. **Small corpus.** 7 games, one side per game. A single swingy leak
   flips the verdict; treat PASS as "no red flag", FAIL+numbers as the
   real evidence.
