# 03 — Openings, Endgames, Adjudication (Workstream 2 KB)

Scope: opening-book strategy under curated start positions, tablebase budget math, draw-rule
handling (threefold / fifty-move / 300-ply adjudication), and endgame conversion reliability.

## 0. Originality & data note (ORIGINALITY.md first)

Books and tablebases are permitted as **shipped data**; probing code stays ours
(`chess.syzygy`/`chess.polyglot` in the base image are libraries, not engines). No copied engine
code anywhere; numbers below are published data with sources. All TB/book work is data-in, our
code-out.

## 1. Opening book strategy with curated starts

- Games start from **curated "level" positions**, not the standard start ⇒ classical opening
  theory is nearly worthless: book value is low ROI. The book only helps in the first 1–3 plies,
  and only if the set is known and small.
- What "level" probably means (verify with organizers in the research-answer doc): positions
  where a strong engine eval is near 0, **possibly with side-to-move compensation** (e.g.
  −0.3 for White to move counts as level). Test our engine from the *actual* set early; also
  check whether the set leans midgame or endgame (a set full of Q-less endgames changes tuning
  priorities — see doc 02 §5).
- If the exact set is published: **home-prep is legal and the only book that pays.** Pre-analyze
  each start with our engine + Stockfish (dev-only), and hardcode short (3–6 ply) PVs. A polyglot
  book is a fine carrier: `chess.polyglot.open_reader`/`MemoryMappedReader` reads it (python-chess
  1.11 polyglot is read-only [1]); writing a book is ~16-byte records (zobrist hash, move, weight,
  learn) that we can emit with our own script using `chess.polyglot.zobrist_hash` — or use the
  `polyglot` CLI tool outside the repo. Weights = our own analyzed scores, so it stays our data.
- Recommendation for the 50 MB budget: **skip the book by default**; spend the bytes on
  tablebases (§2) unless the curated set is published. A book without a known set is dead weight.
- **Baseline strength from CCRL-public house bot**: treat its CCRL rating as the bar, calibrated
  locally by Stockfish at `UCI_LimitStrength`/`UCI_Elo` (doc 02 §7). Design target: win a SPRT
  match (elo0=0, elo1=10) **at the event clock 120+0.5** against SF tuned to the house-bot band.
  CCRL lists: https://ccrl.chessdom.com/ccrl/404/ (40/15; verify link locally).

## 2. Tablebases — exact budget math

Sizes (verified 2026-09-07 from syzygy mirror listing tablebase.sesse.net/syzygy/3-4-5/; matches
CPW [2]):

| Men | WDL+DTZ total |
|---|---|
| 3 | 0.02 MiB |
| 4 | **4.12 MiB** |
| 5 | 936 MiB (whole set does not fit) |
| 3–5 | 940.4 MiB ([2] says 939 MiB) |
| 6 | 149.2 GiB |
| 7 | 16.7 TiB |

- **3–4 piece = ~4.2 MB** ⇒ fits trivially; ~45 MB left. Covers every *classic* endgame:
  KQvK, KRvK, KBNvK, KBBvK, KPvK, KQvKR, KRvKB/KN, KPvKR, KPvKP, KQvKQ, KRvKR… Individual
  samples: KBNvK 7.5K+451K, KQvKR 20K+302K (rtbw+rtbz).
- **5-piece cherry-pick**: each pair is ~0.5–10 MB (e.g. KBBBvK 2.5 MB, KBBNvK 9.1 MB). If budget
  remains, add the highest-usage 5-piece tables; usage statistics consistently rank
  KPP-vs-KP-type and common pawn tables first (CPW's 7-man top-20 list [2] shows the pattern:
  KRPPvKRP, KBPPvKBP, KPPPvKPP…). Verify per-file sizes against a mirror before committing.
- **Probe wiring (our engine, python-chess)**: `chess.syzygy.open_tables(dir)` +
  `probe_wdl` / `probe_dtz` [1]. WDL is fifty-move aware (cursed win = +1, not +2 [2][3]);
  DTZ is single-sided and drives toward the next capture/pawn move. Plan (build-phase decision):
  probe **WDL at/near leaves** and **DTZ at root** once winning and men ≤ our count; skip
  qsearch probing [2]; mmap via OS page cache (tables are ~4 MB — fine in 2 GB RAM).
- **Is it worth it?** Stockfish classical eval gained −7 Elo (4-man), +2 (5-man), +13 (6-man) at
  10+0.1 with tables in RAM [2] — small at SF depth, but for a shallow Python search the value is
  larger: exact WDL replaces heuristics exactly where shallow search is blind (KBNvK, KQvKR,
  KPKR — longest 4-piece mates: 33, 35, 43 moves [4]). Note the Elo-gain numbers are *ceteris
  paribus* vs. a strong classical engine; our gap-to-perfect in those endgames is much bigger.

## 3. Draw rules — repetition & fifty-move with a referee

- **Referee claims threefold + fifty-move automatically** (per event rules): the engine cannot
  reject, so:
  - When winning/decisive: **avoid two-fold repeats** — at root, filter out moves leading to a
    position already seen (python-chess `board.is_repetition(2)`; position identity includes
    side-to-move, castling rights, ep square). This is the highest-value repetition code.
  - When equal/losing: **seek repetition** deliberately (a repeat is an automatic draw score) —
    prefer moves that transpose into a twice-seen position when the search score is ≤ 0 and
    material is even.
  - Non-root handling: treat repeat moves in search as draw (they are, once the referee claims)
    — nodes eventually draw, so don't give them huge scores.
- **Fifty-move**: 100 plies of no capture/pawn move ⇒ claim. All 4-piece wins convert within the
  window (longest 4-piece mates ≤ 43 moves [4]), but **5-piece wins can exceed it** (KPPvKP
  longest mate = 127 moves ignoring the rule [4]) — those are "cursed wins" under WDL [3] and are
  draws if the referee claims. Consequences:
  - With 3–4 piece TB only, prefer DTZ-progress moves in winning tablebase positions (zero in the
    clock: capture or push a pawn every ≤ 50 moves).
  - When we ship a 5-piece table, the engine must respect WDL cursed-win = draw and never treat
    +1 as a clean win.

## 4. The 300-ply adjudication — "material decides if no result"

Read the exact rule when available; design for the stated semantics:

- **Winning by material ⇒ win even without mate technique**. Converting KQvK/KRvK has zero
  urgency — what matters is not losing the material edge or the game before 300 plies. Mate
  technique is insurance, not a win condition. (KBNvK shuffled to ply 280 while keeping B+N =
  win by adjudication.)
- **Losing on material ⇒ loss, even into a fortress** (e.g. opposite-colour bishops, R-vs-R+
  blockade). Do not trust "drawish" endgame heuristics when behind; the eval should treat a
  material deficit late as terminal. This is why trade *selection* matters: when winning, trade
  into **mating material** — KQvK, KRvK, K+2 minors vs K — and never down to a bare minor
  (K+N vs K is draw-by-insufficient-material under both interpretations; K+B vs K unclear under
  "material decides" — don't rely on it).
- **Terminal draws still count before 300 plies**: stalemate, threefold, fifty-move, insufficient
  material. So avoid stalemate traps while "winning" (drive the lone king with legal moves —
  standard Q-vs-K technique), respect the fifty-move window (§3), and don't count on
  adjudication to rescue a 50-move-overdue win.
- Net strategy: **play to maintain a material edge with zeroing progress**, not to find pretty
  mates; contempt toward draw-ish lines when any material edge exists; the opposite when
  material is down (grab any repetition).

## 5. Endgame skill without TB — heuristics, and the verdict

**Verdict: 3–4 piece TB is the only *reliable* way for the full classic set, and it costs 4 MB —
take it.** Heuristics below are what make ≥5-piece (or no-TB) play not embarrass us and are still
worth implementing because search + these convert most wins while the referee's material rule
covers the rest.

ROI-ordered heuristics `[standard concepts, implement fresh]`:
1. **Passed pawn eval** (rank bonus, protected/connected boost, rook-behind bonus) — converts
   K+P endgames and pawn races (see doc 02 §4; CPW [5]). Bounded by adjudication: pushing the
   pawn also zeroes the 50-move clock.
2. **King activity/centralization** — eg bonus for central king, distance-to-enemy-king
   (tropism) when winning: drives mating nets without explicit mate "plans".
3. **Search extensions in the endgame** — extend/deepen when piece count is low (≤ ~8 men) and
   when a lone king faces mating material; shallow engines otherwise shuffle (this is what costs
   KQvK/KBvK games at ~1800 CCRL). Typically worth more Elo than any single eval term here.
4. **Stalemate guard at root** — in winning positions, when the only non-losing-looking moves
   allow stalemate, prefer a check/pawn-move alternative; `board.is_stalemate()` is one legality
   check at root, not per-node.
5. **Promotion policy** — promote to Q (R only under immediate stalemate-mate considerations);
   avoid underpromotion surprises in qsearch.
6. **Opposition**: skip explicit code — king-activity PST + depth handles K+P v K opposition
   correctly once depth ≥ ~10; explicit opposition is the classic over-engineering trap.
- **KBNvK without TB is the one classic failure**: max mate 33 [4], requires a specific
  algorithm a shallow search won't find; 4-piece TB makes it a non-issue. Similarly KQvKR (35)
  and KPKR (43) punish heuristics. This is the honest answer to "TB the only reliable way":
  for normal wins, no (search + heuristics + adjudication are enough); for the long-tail mating
  endgames and 50-move-critical lines, **yes**.

## 6. Ship list & verification (bottom line)

- Ship: **3–4 piece syzygy WDL+DTZ (~4.2 MB)** — always. Add selected 5-piece pairs if budget
  (≤ ~45 MB) remains. No opening book unless the curated set is published; then a small
  self-analyzed polyglot book.
- Verification (dev-time, outside repo): unit-test `get_move` on a FEN suite of our own:
  KQvK, KRvK, KBNvK (fastest conversion), KQvKR, KPKR, KPvKP opposition, stalemate traps,
  repetition-avoidance when winning, repetition-seeking when losing. Compare against
  Stockfish-limited at 120+0.5 for the final margin (doc 02 §7).
- Adjudication-aware acceptance: endgame tests must pass **with the 300-ply/material rule
  simulated** (assert material preserved + zeroing progress), not just "won the game".

## Sources
[1] python-chess 1.11.2 docs (syzygy, polyglot, engine) — https://python-chess.readthedocs.io/en/v1.11.2/
[2] CPW: Syzygy Bases (sizes, WDL/DTZ, probe guidance, SF Elo gains, 7-man usage list) — https://chessprogramming.org/Syzygy_Bases
[3] cpw: Endgame Tablebases / fifty-move (WDL 5-valued scale, cursed wins) — https://chessprogramming.org/Endgame_Tablebases
[4] Kirill Kryukov: Longest checkmates (DTM by material config; KQvKR 35, KBNvK 33, KPKR 43, KPPvKP 127) — http://kirill-kryukov.com/chess/longest-checkmates/
[5] CPW: Passed Pawn (rank bonuses, rook behind) — https://chessprogramming.org/Passed_Pawn
[6] Syzygy mirror for exact per-table sizes — https://tablebase.sesse.net/syzygy/3-4-5/
[7] CCRL rating lists — https://ccrl.chessdom.com/ccrl/404/