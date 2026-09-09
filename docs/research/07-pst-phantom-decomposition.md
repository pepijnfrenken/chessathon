# q5-fix1 Mission B — static-eval term decomposition: the phantom-credit
# anatomy and the ranked PST suspects (2026-09-09)

Instrument: `tools/eval_decompose.py` — numpy mirror of `evaluate()` with
**bit-exact parity** vs the jitted eval on all 45 probe FENs (tapered
White-POV + tempo + mate-drive term == `evaluate()` mover-POV, 45/45).
The tuner's parity-verified feature derivation (`tools/texel_tune.py`)
does the heavy lifting; this tool adds per-side/per-piece PST sub-totals
and raw table-coordinate dumps. (The mate-drive term is NOT in the tuner
model — it had to be added separately; accounted for in the tool.)

Corpus: the 13 codex1-experiment positions (r83 relative plies
21/29/31/35/39/41/75/77, r70-B p24, 4 win controls) + every our-side FEN
of the loss games r64/r74/r76 from the **corrected** leak corpus
(`results/leak_suite/fens.json`, PGN-header side filter). 45 FENs total.
Raw output: `/tmp/q5b_decomp_full.json` (regenerate with the tool;
committed so the method ships).

## Headline: the phantom is ONE term — the pawn PST read vertically inverted

`engine/eval.py` indexes White PSTs directly (`s = sq64(sq)`) and Black
PSTs mirrored (`s = sq64(sq) ^ 56`), with `a1=0 .. h8=63` — so table row
1 (values 50/80) is read by **both** sides' HOME pawns (White e2 reads
row 1; Black e7 reads `60^56 = 4` = row 1). The tables were written
rank-8-first ("advanced = bigger"), so the consumer is vertically
inverted vs intent, color-symmetrically. Measured consequence (both
sides read the same rank profile):

| pawn rank | mg mean read | eg mean read |
|---|---:|---:|
| home (2nd/7th) | +50.0 | +80.0 |
| 5th/3rd | +5.0 | +11.2 |
| 6th rank | -2.5 | +5.0 |

**Advancing a pawn from its home rank to the 5th costs ~45 mg / ~69 eg.**
Counterfactuals on r83-p21 (model-exact, so arithmetic == engine):
White f2->f5: eval (Black POV) +78 -> +10; Black f7->f4: +78 -> +145.

### The r83 family, quantified

In all eight pre-leak r83 positions material was dead equal (0 or -100)
and the referee had Black at -43..-174. Our static eval said **Black
+78..+318**. Decomposition (White-minus-Black, mg/eg):

| probe | W pawn PST mg/eg | B pawn PST mg/eg | W-B pawn delta | eval (B POV) |
|---|---|---|---|---|
| p21 | +210/+335 | -300/-475 | **+510/+810** | +78 |
| p41 | +110/+195 | -300/-475 | +410/+670 | +205 |
| p77 | +75/+130 | -250/-395 | +325/+525 | +318 |

The **only** material-neutral term large enough to carry the phantom is
the pawn PST: White's advanced pawn mass (c5/d4/e5/a5/g5...) reads
0..30 while Black's home wall (a7/b7/f7/g7/h7...) reads 50/80 EACH. At
p77 the pure pawn-placement credit is +325 mg / +525 eg for White
(= Black "up" that much in placement), plus mobility -24 and
king-safety -16 White-POV — the +318 Black-POV total is fully explained:
**material -100, pawn PST +525-ish tapered, no other term contributes
material-scale credit.** Same mechanism in r70-B (mat +220 White, eval
-26 Black-POV): Black holds 4 home pawns vs White's 1 → +150 mg/+240 eg
placement credit for Black (tapered +198 at phase 11) eats the +220
material edge almost exactly.

King PST is NOT a meaningful contributor in these positions: castled/
back-rank kings read -40..-50 mg per side with the deltas ≤10-20 cp.

### Loss-game corroboration (r64/r74/r76)

r76 (first leak at Nxh6+, material already -260): pawn PST delta +49
White — small. r74 pre-leak (mat +110..+330, eval +129..+550): pawn PST
deltas -5..-47 (White slightly punished for advancing). The
**transition-phase** (r64 p129-207, r74 p98+) large positive
king-safety/passed terms appear only AFTER the eval already collapsed.
The leak family's pre-collapse "we're fine" signal is the pawn-PST
inversion; the post-collapse terms are a separate, smaller story.

## Ranked suspects for tomorrow's ablation spec

1. **Pawn PST rank orientation (MG+EG together), `engine/eval.py:200-220`
   as read through `eval.py:471`.** The phantom itself. Numbers above.
   Ablation A (first): normalize at hand-assembly (`eval.py:294,300`)
   by flipping the 8 rows of `_PAWN_MG`/`_PAWN_EG` (row 0 stays last).
   Expected immediate effect: home walls stop reading +50/+80; r83-class
   positions stop reading +100..+300 for the side whose pawns sit home.
   Risk: weights were gate-tuned around the inverted tables (Phase-2
   hand≈tuned wash) — gate at 500ms AND quality_ab before ship.
2. **King MG orientation (`eval.py:266-275`), separately.** g8 reads +30
   vs g1 -40 for White; castling short costs 70 mg cp vs doing nothing.
   BUILD.md:74-76 documents the opposite intent ("king PST is
   castle-back in middlegame"). Measured on the corpus: contribution
   small (≤20 cp deltas) because both sides' kings sat back-rank/castled
   — but the incentive direction is anti-castle and the g8-center EG
   rows (e8 EG -30 vs e4 +40) are consistent with rank-8-first authoring.
   Ablation B: flip rows of `_KING_MG` (and audit `_KING_EG`, whose
   rank-1 -50/-30 edge values look author-correct but must be checked
   after the flip). NOT bundled with A.
3. **Pawn EG home-rank magnitude specifically.** Even after the row
   flip, row 1 becomes -20..+10 mg / 0 eg — fine — but the EG table's
   row-2/3 values (30/40, 15/30) mean the corrected table rewards early
   advancement modestly; check the corrected profile against the
   documented "castle-back" prose and the selfcheck expectations
   (`eval.py:752-759` asserts passed-pawn monotonicity — keep them
   green in the ablation).
4. **Non-pawn tables: NO-OP.** Knight/bishop/queen MG tables are
   rank-mirror-symmetric in effect (row1==row7 means verified);
   rook MG's only rank asymmetry is the 7th-rank band (row idx 1,
   +5/+10) which under the flip simply swaps to "rook on 2nd" — audit
   but expect zero delta. Do NOT touch PASSED_W/SHELTER masks
   (`eval.py:151-162`, a1-based by construction).
5. **Mobility/king-safety/tropism/bishop-pair: cleared.** Per-term
   magnitudes on all 45 FENs are ≤±50 cp and sign-correct; they do not
   carry the phantom. Bishop pair = 0 everywhere in the corpus.

## Explicit answers to the brief's questions

- **Does the king PST (as read after ^56) reward a king on its own back
  rank, the enemy back rank, or neither?** It rewards the ENEMY back
  rank (White g8 +30 > g1 -40; Black e1 reads 0 > e8 -50) — vertically
  inverted, matching the pawn tables' authoring convention, NOT the
  BUILD.md castle-back prose. In-corpus magnitude small; still a real
  anti-castle incentive.
- **Does the pawn table punish advancement consistently?** YES — every
  step from home toward the 8th loses credit for BOTH colors (home
  50/80 → 5th rank 5/11 means → 6th rank -2.5/5). Advancement is
  monotonic-punished; the only non-monotonic wrinkle is the EG 7th-rank
  row (+13.8 mean) which after inversion rewards sitting on the 2nd.

## Method note for the ablation

The flip is a one-line change at hand-table assembly (rows reversed
once), NOT per-square logic; `tools/eval_decompose.py` re-run must show
the r83 pawn-PST delta collapsing from +510/+810 to ≈±100, and the
existing eval selfcheck must stay green. Gate plan stands per §8: L1
24@500ms, quality_ab corpus, and — per the operator's Sep-9 direction —
the real-clock SF bout as primary instrument for eval-surface changes.
