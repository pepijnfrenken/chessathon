# CHESSATHON — ENDGAME CONVERSION FIXER (Phase 3 follow-up)

## Your mission
HEAD (05d0101) ships a correctness-fixed search + MATE_DRIVE_K=50 mate-drive,
but **endgame conversion is BROKEN at HEAD**: an independent audit plus a
fresh run of `tools/eg_check.py` on the actual tree shows won endgames do NOT
convert:

```
KQvK   strong-as-white DRAW   KRvK  strong-as-white DRAW
KQvK   strong-as-black DRAW   KRvK  strong-as-black DRAW
KPK    strong-as-white DRAW   KPK   strong-as-black DRAW
KRPvK  strong-as-white WIN    KRPvK strong-as-black LOSS
```

The strong side shuffles legal quiet moves into 3-fold draws (verified at
300ms AND 2000ms). The builder's BUILD.md/summary claims "eg_check: KQvK W,
KRvK W, KRPvK W — 3/4 matches the Phase-2 record" — that does NOT reproduce
on the shipped tree. Phase 2's record (prior shipped state) showed KQvK/KRvK
white wins (HEAD 5/8 per the audit).

## Reproduce first
```
cd /home/pino/projects/chessathon
/tmp/chessbench/bin/python tools/eg_check.py          # shipped eval default
/tmp/chessbench/bin/python tools/eg_check.py --strong hand:1111 --weak hand:0000
```
(tools/eg_check.py default strong=tuned:1111 — use hand:1111 for the shipped
eval. Requires the /tmp/chessbench venv; python3 without chess fails.)
Record the exact results before touching anything.

## Diagnose (root cause candidates, in order)
1. **Trace one KRvK-white game** (strong K+R vs bare K): does the strong side
   drive the king to the edge and then fail to mate (Rg1-style shuffling), or
   does it never approach? Watch whether the king actually chases (mate-drive
   term active? kdist decreasing?).
2. **Is MATE_DRIVE_K=50 enough?** The eval comment says 30 was too weak. Check
   whether the search's chosen moves actually reduce kdist / push the enemy
   king to the edge. The drive term (7-kdist) is added to the eval — verify it
   survives the search horizon (it's a leaf eval term, should).
3. **Mate-in-N horizon**: at 300ms the search reaches ~d8. KQvK/KRvK mate nets
   are ~10-15 moves — the engine can't see mate, it must convert via eval
   gradient (drive king to edge + deliver). If the eval gradient is flat
   (shuffling) the drive term isn't dominating PST/rook noise.
4. **Compare to Phase-2 HEAD** (6dc3dcb, the pre-Phase-3 ship): the audit says
   it converted KQvK-w/KRvK-w. Diff the eval/search between 6dc3dcb and HEAD —
   what did the "correctness fixes" change that could hurt endgame play?
   (qsearch quiet-leaf eval? null-move beta>0? draw scoring?) The fixes are
   value-sound per brute force, but play-quality can still regress if e.g. the
   old code's *bugs* accidentally caused progress (e.g. null-move at negative
   beta effectively pushed the king).
5. **Search horizon trick**: consider a small endgame-specific extension or a
   stronger mate-drive (king-centralization + rook/queen proximity bonus), or
   restoring whatever Phase-2 behavior drove conversion — but ONLY via
   eval/search terms we write ourselves (ORIGINALITY.md: no third-party code).

## Constraints
- **ORIGINALITY.md applies**: everything you write must be your own code in
  this repo. Read it first.
- Goal: KQvK + KRvK + KRPvK convert as strong-as-white AND strong-as-black
  (both colors) at 300ms in eg_check, without regressing: perft, determinism,
  parity, NPS, or the 24g LMR gate (8W-6L-10D 0.542) evidence.
- **Gate after fixing**: run eg_check (all 4 cases × 2 colors = 8 games) +
  perft_check + a 24g A/B gate (new vs HEAD 05d0101) at 500ms to prove no
  overall regression. SPRT if time permits.
- The shipped config is hand:1111 (CHESSATHON_EVAL_CONFIG default hand).
- Commit with a clear message. Update BUILD.md Phase-3 entry honestly
  (correct the false eg_check claim if it's wrong).
- Do NOT touch agent.py, engine/tt.py unless necessary. Keep the diff minimal.
- Box has 6 cores; run gates as background processes and poll (no blocking).

## Report
Print a final summary: reproduce results → root cause → fix (exact diff) →
gate results (eg_check 8/8, perft, A/B score) → commit hash. Be honest about
any case that still doesn't convert and why.

<!-- source session: 2026-09-07T16-22-30-035Z_01a07cad-a593-7000-8208-374bb3572689.jsonl -->
