# CHESSATHON — PHASE 4: KPK + HORIZON STRENGTH (continuation brief)

## Read FIRST (mandatory)
1. `/home/pino/projects/chessathon/ORIGINALITY.md` — THE LAW. Acknowledge in final summary.
2. `/home/pino/projects/chessathon/BUILD.md` — design log. **Update it as you go** — the judges read it.
3. `/home/pino/projects/chessathon/CLAUDE.md` — project context.
4. Read the **Phase 3 + 3.1 entries** in BUILD.md FIRST (lines ~348-620) — they document what was tried, reverted, and shipped. Your baseline is **whatever HEAD is when you start** (either 6908a55 if the Phase 3.1 eg-fix gate held, or 05d0101 if the fixer reverted it after the negative v5 gate 0.396). **Read `git log --oneline -3` first and confirm what HEAD is.** If the Phase 3.1 endgame terms were reverted, your baseline has the documented KQvK/KRvK conversion weakness (they shuffle into 3-fold draws at short TCs) AND the Phase-3 correctness fixes. NEVER regress from the current HEAD.

## Context — where the project stands
- Phase 2: hand eval ships (Texel tuning rejected, honest negative).
- Phase 3: aspiration windows REJECTED (negative gate 0.438, reverted). LMR confirmed (gate 0.542, kept). Correctness forensics found + fixed 4 baseline bugs (PVS re-search sign, null-move beta>0, qsearch quiet-leaf, parse_fen ep default) — but the fixes exposed an endgame conversion regression.
- Phase 3.1: endgame conversion fixer (commit 6908a55 + a final restricted-config re-gate running). Manhattan-drive + edge/prox mate-net terms (≤6-piece bare-king family only), qsearch stalemate probe (sparse-gated), net-only budget boost + partial-iteration adoption, eg_check black-fen mirror fix.
- **HEAD now = the Phase 3.1 tree** (6908a55 + final gate confirmation). This is the known-good baseline. NEVER regress from it.

## The two documented weaknesses to attack (from BUILD.md Phase 3.1 risks)
1. **KPK remains the weak spot** — the mate-net terms deliberately DON'T fire at |mat|=100 (KPK is < the 300 gate), so KPK-w sometimes converts via king-centralization + passed-pawn gradient, but usually draws at 300ms. KPK is a REAL ladder case (king+pawn vs king appears constantly). This is the #1 target.
2. **KRvK-class nets at horizon boundary** — mate-in-16 nets sit exactly at the depth boundary at short TCs; conversion flakes ~70% at 300ms. At competition clock (2.5-45s/move) it's robust, but the 300ms/500ms gate regime still flips.

## Mission — pick ONE primary, in order (do not stack)
### OPTION Z (NEW, from ladder evidence — rounds 54/55 drew by 3-fold after aimless shuffling):
**Anti-shuffle / progress mechanism in quiet positions.** The engine, with time on the clock
(87-117s left!), shuffles a rook Rg1-Rf1-Re1-...-Rb1-Ra1-Rb1 for 10+ moves or Rhb8-Rh8 for 5+
moves and draws by repetition (r54 fm2, r55 Minimax Two — ladder logs). Root cause: in quiet
positions all legal moves score within noise (~equal), the search picks any, and nothing
breaks the cycle. Fix candidates (our own code):
1. **Repetition-aware move selection at the root**: if the root's best move would repeat a
   position already on the path (or a position seen in the game via TT/history), penalize it
   (e.g. -5..-20cp) so the search prefers non-repeating progress moves — unless the repetition
   is forced (only legal move / only move not losing). This is classical and ships in many
   engines; must NOT weaken defense (only apply when a non-repeating alternative exists within
   a small score band).
2. **50-move / progress term**: weight quiet moves that change the pawn structure or piece
   square (irreversible progress) slightly above pure shuffles.
3. Verify on the EXACT r54/r55 shuffle positions (reconstruct the FENs from the logs where
   possible, or synthesize similar quiet-shuffle positions): new engine must NOT shuffle 3+
   identical moves with time available.
This is the highest-value fix for the ladder right now — it directly targets the drawn-won-games
pattern. Test it FIRST before KPK if it can be made safe (gates: 24g vs HEAD ≥55%, plus the
shuffle-position regression suite).
### OPTION A (recommended first): KPK conversion via eval terms we own
KPK = K+P vs K. Winning plan: king in front of pawn, pawn to promotion square, king controls promotion. The engine needs:
- Passed-pawn bonus (check if exists in eval — many hand evals have one; if present, verify it fires in KPK)
- King-support-of-pawn term: reward the winning king for standing on/adjacent to the pawn's promotion path (in front of the pawn)
- King-opposition-ish term: reward controlling the queening square (king on the queening-square rank/file)
- KEY: these must fire ONLY in the KPK family (≤6 pieces, exactly one pawn, no other pawns, |mat| small-but-winning ~100, kings + one pawn total ≤4 pieces) so they can't erode material elsewhere (Phase 3.1 lesson: scope tightly!)
- Hand-tuned constants, NOT tuner params (keep the 813-param tuner contract intact).
### OPTION B: KRvK/KQvK horizon robustness
- The mate-net terms work at depth ≥16 but flake at the horizon boundary. Options: extend king-approach moves that reduce drive (Phase 3.1 fixer started this — check if it shipped), or a small endgame extension for checks/drive-reducing moves.
- Risk: extension can blow up node count in the net domain. Measure NPS carefully.

## Validate EACH change (in order, no skipping)
1. **Correctness**: fixed-depth parity — feature ON vs OFF, same best move + score at d6-8 on 8-10 positions (KPK-w, KPK-b, KQvK, KRvK, KRPvK, KBNvK if present, sharp mg, startpos, italian). Byte-exact on the exact core (LMR off); equal-value moves only with LMR on.
2. **Perft**: `tools/perft_check.py` ALL PASS (movegen untouched, but confirm).
3. **Endgame gate**: `tools/eg_check.py` (mirrored, both colors) — KPK-w must WIN consistently (the whole point), and KQvK/KRvK/KRPvK must NOT regress (still ≥ 6/8 at 300ms, ideally 8/8).
4. **Strength gate**: `tools/gate_match.py` — new vs HEAD, 24 games, 500ms, hand:1111 both sides. ≥ 55% to ship. Watch color asymmetry (Phase 3.1 lesson: if new-as-black collapses, the terms over-fire somewhere — scope tighter).
5. **NPS**: fixed-depth bench, startpos d10 + mg d8. Report knps — must not drop >5% from the Phase 3.1 record (~500-550 knps).
6. **Determinism**: same position × 2 runs → identical.
- Run gates as BACKGROUND processes, poll them. NEVER edit code while a gate is running. Kill leftovers (`pkill -f` with exact paths) before starting.

## Constraints
- ORIGINALITY.md: everything you write is your own code in this repo. No third-party engine code.
- Hand eval ships. Do NOT flip to tuned. Do NOT re-run Texel tuning.
- Scope every new eval term TIGHTLY (the ≤6-piece lesson). If a term helps KPK but hurts anything else, it must be gated to the exact family that needs it.
- Commit granularly (`4 (feature): what + why + gate result`). Update BUILD.md Phase 4 entry with honest verdicts.
- The competition clock is 120s+0.5s, 1 core, 2GB RAM — never ship anything that risks flagging or memory blowup. Zip must stay <50MB, init <60s.
- Always leave the tree committed + known-good. If KPK can't be fixed without regression, ship the baseline and document honestly.

## Report
Final summary: what you tried (per option), per-change gate scores + nps + eg_check table, what shipped (commit hash), what was rejected + why, risks remaining. Be honest about anything that still doesn't convert.

<!-- source session: 2026-09-07T19-43-06-446Z_01a07d65-4ece-7000-af07-25aa434b1cd7.jsonl -->
