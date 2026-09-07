# 01 — Engine Architecture Playbook

**Goal.** A classical (no NN), numba-jitted alpha-beta chess engine in ONE Python process, 1 core, 2 GB RAM, no GPU/network. 120 s + 0.5 s/move, 60 s init budget, pondering allowed. python-chess 1.11.2 as I/O + reference library only.

**Originality (read ORIGINALITY.md).** Everything below is standard, published chess-engine *knowledge* (CPW-citable) that we implement **fresh, in our own code**, in-repo during the event. We never copy engine source (sunfish, python-chess example engines, Stockfish derivatives are all off-limits). Published data values (e.g. PeSTO PST numbers) are usable **with attribution**, but preferred is tuning our own tables. No pretrained models, ever. This doc contains no implementation code — only decisions, numbers, and sources.

---

## 1. Search framework

Core: **iterative-deepening (ID) negamax with alpha-beta**, principal-variation search, aspiration windows, transposition table. All standard algorithms — CPW: [Alpha-Beta](https://www.chessprogramming.org/Alpha-Beta), [Iterative Deepening](https://www.chessprogramming.org/Iterative_Deepening), [Principal Variation Search](https://www.chessprogramming.org/Principal_Variation_Search), [Aspiration Windows](https://www.chessprogramming.org/Aspiration_Windows), [Transposition Table](https://www.chessprogramming.org/Transposition_Table).

- **ID + PVS:** full-window search at the root/PV node; zero-window (fail-soft) searches on sibling moves using the PV move as the initial guess. Standard, big node reduction vs plain alpha-beta (~2×), cheap to implement.
- **Aspiration windows:** start next iteration at `prev_score ± 25–50 cp`; on fail-high/low re-search with full window. At our depths (8–10) this mostly saves nodes on quiet, stable positions. Fail-soft scoring is worth it.
- **Move ordering (in order):** TT move → winning captures (MVV-LVA or SEE-filtered) → killers (2/ply) → quiet history → losing captures. Ordering quality *is* the strength of alpha-beta: with perfect ordering the tree is ~O(b^(d/2)) [CPW [Move Ordering](https://www.chessprogramming.org/Move_Ordering), [Killer Move](https://www.chessprogramming.org/Killer_Move), [History Heuristic](https://www.chessprogramming.org/History_Heuristic), [MVV-LVA](https://www.chessprogramming.org/MVV-LVA)]. Generate all moves once per node, score, sort (measured fine in numba; see §3).
- **Quiescence:** stand-pat + capture search; when in check, search all evasions ([Quiescence Search](https://www.chessprogramming.org/Quiescence_Search)). Skip check-generating moves in q-search (they blow the tree up for little at our depth); cap q-depth (~10 plies) against horizon explosion. MVV-LVA ordering in q-search; no killers/TT in q-search.
- **Transposition table:** see §3 for sizing. Store `key(32b) | depth(8b) | bound(2b) | score(16b) | bestmove(16b) | gen(8b)` packed ≈ 12–16 B/entry. Always use TT move for ordering; TT score only if `depth >= node depth` (and bound allows). Use **depth-preferred replacement** within 2–4-way buckets. Mate scores: store as `MATE - ply` internally, restore with ply on read; don't store draw scores from TT hits into the repetition-prone paths without care (standard pitfall).
- **Repetition / 50-move:** draw (return 0) if the position occurs a 3rd time (track zobrist keys of the last ~8 plies incl. game history — a small ring buffer, not python-chess `is_repetition()`, which is O(history) and slow in a hot loop). Return 0 when `halfmove_clock >= 100`. python-chess exposes `board.is_repetition()` / `board.is_fifty_moves()` only for outer-loop/root use.
- **Extensions:** **check extension** (+1 ply at in-check nodes) is worth it — wins shown in classical engines and cheap. **Singular extensions: skip** (little gain at these depths, high complexity/bug risk in Python). LMR below.
- **LMR ([Late Move Reductions](https://www.chessprogramming.org/Late_Move_Reductions)): yes.** Apply only to *quiet* non-first moves (skip TT move/captures/checks/promotions), only at `depth >= 3`, never at PV nodes. Reduction grows with move index, capped at 2 plies. LMR ~+30–60 Elo in C engines; in Python the per-node cost (eval + movegen) is dominated by the *eval call*, which LMR saves — worth it.
- **Null-move pruning ([Null Move Pruning](https://www.chessprogramming.org/Null_Move_Pruning)): yes.** Classic R=2 (or R=3 at higher depth), skip in check, skip in endgame with few pieces (zugzwang). Typical +100 Elo for ~10 lines. Cheapest pruning per Elo.
- **Mate-distance pruning**, **probcut**: skip (complexity not amortized at our nps).
- **Decision:** ID + PVS + aspiration + TT + MVV-LVA/killer/history ordering + q-search (captures + full evasions in check) + check extension + null move + LMR. Order of implementation matters: get alpha-beta + ordering right before any pruning.

## 2. Evaluation

Hand-crafted, **tapered** (interpolate midgame ↔ endgame by game phase) ([Tapered Eval](https://www.chessprogramming.org/Tapered_Eval), [PeSTO](https://www.chessprogramming.org/PeSTO)). PeSTO proves PST-only + taper is strong enough for TCEC CPU League 1 ([CPW](https://www.chessprogramming.org/PeSTO)) — the base we build on.

- **Material + PST tables (dominant term).** PeSTO's Texel-tuned base values (published data, attribute if reused — [PeSTO's Evaluation Function](https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function)): mg P82/N337/B365/R477/Q1025, eg P94/N281/B297/R512/Q936, phase weights N/B=1, R=2, Q=4 (max 24). **Prefer tuning our own** PSTs (self-play + Texel-style fitting later); start from PeSTO-level shapes. Taper formula: `(mg*phase + eg*(24-phase))/24`.
- **Pawn structure:** doubled, isolated, backward, **passed** (biggest single term after PST; bonus by rank, blockable, +rook-behind-passer), candidate passed. [CPW Pawn Structure](https://www.chessprogramming.org/Pawn_Structure) for the standard term list.
- **King safety:** pawn shield in front of castled king + king-tropism penalties when enemy pieces attack near the king; scale by game phase (important only in middlegame). Keep it bitboard-cheap (attack counts per square via precomputed attack tables).
- **Mobility:** count legal/attacked squares per piece, small per-bin bonus. Moderate value; cheap in numba with precomputed tables.
- **Bishop pair** (~+30–50 cp scale), **rook on open/semi-open file**, rook on 7th, **tempo** (+~10–20 cp for side to move — with tapered PST, tempo matters less; keep small).
- **What actually matters at depth 6–9:** (1) material+PST correctness, (2) passed pawns + king safety, (3) everything else is detail. Avoid eval terms that cost more than they win at these depths: no SEE in eval, no complex king-attack tables, no space/center complex nets. **Eval budget: ≤ ~2–4 µs/node in numba** (should be ~10–25% of node cost).
- **Decision:** tapered eval = material + PST + bishop pair + tempo, then pawn structure (doubled/isolated/backward/passed), then mobility + king safety. All bitboard/mailbox-cheap, all numba-jitted. Tune later (Texel) — do not spend phase-2 time on tuning.

## 3. Python performance reality (measured on this machine, 1 core, 2026-09-07)

We benchmarked the exact stack locally (python-chess 1.11.2, numba 0.67.0, CPython 3.14):

| Measurement | Result | Implication |
|---|---|---|
| python-chess movegen (perft) | **~100 knps** (perft4 197,281 in 2.0 s; perft5 4.87 M in 47.6 s) | Movegen alone caps a python-chess-inner-loop search at ~10⁵ nodes/s |
| Pure-Python search (python-chess board, material eval, q-search, capture-first) | **18–34 knps**; d6 = 4.8 s (107 k nodes) | Pure-Python ceiling ≈ depth 6–7 per move → sunfish-class |
| numba mini-engine (own mailbox board + movegen, material-only eval, no TT) | **0.7–1.2 Mnps** (d6 71 k nodes in 0.10 s; d9 23.1 M in 19.2 s) | numba search core is ~25–40× faster than pure Python |
| numba first-call JIT compile | **~5.8 s** (one function, this machine) | MUST warm up during the 60 s init budget; set `NUMBA_CACHE_DIR` to /tmp scratch (repo files read-only) |
| Imports RSS (python-chess+numpy+numba) | **~430 MB** | Never import torch (adds ~1 s+ and hundreds of MB); budget RAM below |

**Decisions that follow:**
- **Write our own board + movegen, numba-jitted** (mailbox or bitboards — our own design). python-chess is the I/O + validation layer only: parse the incoming FEN once per `get_move`, convert our move → UCI at the root, and run perft cross-checks against `chess.Board` during development (python-chess as a legal-move *oracle* is using the permitted preinstalled library, not copying an engine).
- Never call `board.fen()` in a loop; never re-parse FEN per move. In pure-Python contexts, `push_uci/pop` + our own zobrist key (python-chess exposes `board._transposition_key()` for reference).
- **What to jit:** movegen, make/unmake, eval, q-search, negamax inner loop, TT access. **Leave pure Python:** harness/UCI glue, book/TB lookups, time management decisions, pondering orchestration (cold paths, no speed value).
- **TT sizing for 2 GB:** a plain Python dict costs ~100–200 MB per 1 M entries and 0.15 s to build — **use packed numpy/numba arrays** (12–16 B/entry): 2²¹–2²³ entries = 32–192 MB of our budget. Recommend ~128–256 MB TT (2²³ entries). Never store Python objects in the hot loop.
- **Depth feasibility (planning numbers):** per-move budget ≈ 3.5–5 s (see §4) → pure-Python depth ~6; numba engine at an estimated 150–500 knps (slower per node than our 1.2 Mnps stripped mini — richer eval/TT/LMR — but far fewer nodes) → **depth 8–10** typical middlegame, deeper in endgames (fewer pieces). This is the honest envelope; §7 gives the strength implication.

## 4. Time management

Constraint: 120 s base + 0.5 s/move increment; process persists across moves; failure mode is flagging (loss on time). Standard practice: [CPW Time Management](https://www.chessprogramming.org/Time_Management); the "play the clock" principle means *spend what the position needs, never more, never flag*.

- **Per-move allocation:** `budget = (remaining - reserve) / moves_to_go + increment`, `moves_to_go ≈ 30–40`, `reserve ≈ 15%` of remaining. Midgame with ~120 s left: `(120 − 18)/35 + 0.5 ≈ 3.4 s`. Add a hard clamp: `budget ≤ 5–8% of remaining` (sudden-death safety), and `budget ≥ 0.3 s` (never die by overhead).
- **Overhead margin:** each move costs ~50–200 ms of Python/harness overhead — subtract a fixed 0.2–0.3 s from every budget. Never spend the last ~1–2 s of the game on pondering-startup races.
- **Easy-move / stable-PV early stop:** if the root best move is unchanged across 2–3 ID iterations, the score is stable, no fail-high happened, and ≥60% of budget is used → stop and play (this is the "play the clock" heuristic; big time saver in forced quiet positions).
- **Hard stop discipline:** stop cleanly between ID iterations (check the clock once per iteration, and inside the root move loop); always have the previous iteration's best move ready — on timeout, play it. Never run a search that can't be interrupted mid-iteration (one core; keep the check cheap).
- **Increment behavior:** with 0.5 s/move the clock is near-fair: bank increments for tough moves by scaling `moves_to_go` down as the game progresses and by letting a stable-PV early stop keep the surplus. Curated-level positions likely produce shorter games — bias `moves_to_go` lower (25–30) so middlegame moves get ~4–5 s.
- **Sudden-death fallback:** if increment is nil/irrelevant (endgame clock, low time), cap per-move at `remaining/(moves_left + 2)`.
- **Pondering is FREE time:** it runs on the opponent's clock — it never comes out of our budget (§5).

## 5. Pondering

Allowed: think during the opponent's move on our own core. Implementation (standard; our own code):

1. After our move is decided and `get_move` returns, keep searching: the natural ponder target is **the position after our best root move** (opponent to move) — or after our best move **+ our predicted reply to it** (deeper). Simplest robust scheme: continue iterative deepening on the position reached by `our_move + PV[0]` (our predicted opponent reply).
2. On the next `get_move(fen, …)`: **normalize and compare** the incoming FEN with the pondered position (compare piece placement + turn + castling + EP only — strip move counters from both).
   - Match → keep the search running (don't restart; we already have a PV and TT from pondering — usually 1–2 extra plies for free).
   - Mismatch → abort, set the new root, restart ID (TT/history persist, so nothing is wasted).
3. **TT, history, killers persist across moves** — this is most of pondering's value (the search behind the opponent's ponder-move is already in the TT).
4. Protocol niceties: if the harness expects a synchronous `bestmove` per call, pondering is a *background* continuation of the same search object between calls — no threads (1 core), no extra processes (2 GB budget). Keep the search loop interruptible on the new FEN (check a flag between iterations).

Pondering value: +10–30 Elo at these TCs when hit rates are moderate, zero risk if the abort path is cheap. Keep it simple; do it after time management is solid.

## 6. Opening book + endgame

- **Polyglot book:** skip, mostly. Books are keyed by position, so a polyglot book *can* cover arbitrary curated start positions — but "curated level positions" are deliberately non-theoretical middle-ish positions where a book has few good entries, and we cannot fetch master games at runtime (no network) to build one. If (and only if) games start from the standard position sometimes: hardcode our own 1–2 choice replies for the first moves (e4/d4/e5/d5/c4/Nf3…). That is our own data, not a copied book. Determinism: add tiny randomization among equal book moves only if we want variety.
- **Syzygy tablebases ([CPW Syzygy](https://www.chessprogramming.org/Syzygy_Bases)):** sizes are the hard constraint — 3-4-5 man ≈ 938 MB total (ChessBase [Komodo/Houdini help](http://help.chessbase.com/Komodo/15/Eng/000085.htm); CPW: 939.0 MiB). **5-man alone (~0.8 GB) and 4-man (~150 MB) cannot fit the 50 MB zip. Only 3-man (~a few MB: KQvK, KRvK, KBvK, KNvK, KPvK) fits.** Decision: **ship 3-man only if it fits after engine+data** (~2–5 MB, low priority — worth maybe +10 Elo, only in endgames with 3 pieces on board). Probe **at the root only** via `chess.syzygy` (pure-Python probing is ~100 µs+ per probe; don't probe inside the search). python-chess 1.11.2 ships `chess.syzygy` ✓.
- **Book/TB are permitted shipped data** per ORIGINALITY.md — but they are data, not a substitute for search.

## 7. Recommended architecture

```
engine/
  board.py     our own board + movegen + make/unmake + zobrist   [numba-jitted]
  search.py    ID negamax PVS + TT + null + LMR + ext + qsearch  [numba-jitted]
  eval.py      tapered PST + pawn structure + mobility + king-safety [numba-jitted]
  tt.py        packed-array transposition table                   [numba-jitted]
  agent.py     get_move(fen, time_left_ms) -> uci                [pure Python]
  time.py      budget/allocation, stable-PV early stop            [pure Python]
  pondering.py continuation between get_move calls                [pure Python]
  optional: book.py (polyglot), tb.py (3-man syzygy root probe)   [pure Python]
```
- **Data flow:** `agent.py` parses FEN → builds our board → `search.py` iterates (warm jitted) → timeout arrives at a breakpoint → best root move → UCI string. python-chess is used at the edges (FEN parse, UCI conversion, perft legality dev-checks). During dev: perft vs python-chess on fixed suites must pass exactly before anything else — a wrong movegen silently corrupts everything.
- **Build order:** (1) board+movegen+perft (oracle-verified) → (2) negamax+ID+alpha-beta+ordering (captures first) → (3) eval (material+PST+taper) → (4) TT + killers/history → (5) null move + LMR + check extension → (6) time manager + UCI harness → (7) pondering → (8) tuning (Texel-style on our own tables; self-play matches; optional Stockfish as OUTSIDE-/tmp sparring partner only, never in repo/zip — ORIGINALITY.md).
- **Budget check (measured, §3):** imports ~430 MB (numba) + TT ~128–256 MB + misc/overhead ~200–400 MB → **~0.8–1.1 GB peak**, comfortably inside 2 GB. Do not import torch. Set numba cache dir to /tmp (read-only repo). Warm up JIT + tables in the 60 s init.
- **Expected strength (honest, CCRL-ish):** pure-Python-with-python-chess ceiling is ~depth 6 → roughly **1900–2000** (sunfish, the reference pure-Python engine, is rated ~1900-community-estimate, NOT CCRL-listed; it searches ~30 knps CPython [sunfish GitHub README](https://github.com/thomasahle/sunfish), matching our measured pure-Python figures). A well-built **numba** engine at depth 8–10 with a reasonable eval and all standard pruning should land **~2100–2400 CCRL-class** at comparable TCs — reference scale: Embla 2.0.7 (C++, but a useful rating anchor) = 2142 on CCRL 40/40. The realistic top of what *classical, single-core Python+numba* can do is mid-2400s; anything beyond needs a trained NN (out of scope per ORIGINALITY). Within that envelope, the levers that move the needle: TT size + move-ordering quality, eval (tuned PST + passed pawns + king safety), null+LMR, pondering, and never flagging.

## Sources
- [CPW: Alpha-Beta / ID / PVS / Aspiration / TT / Move Ordering / MVV-LVA / Killer / History / QSearch / LMR / Null Move / Check Extension / Tapered Eval / Time Management / Pondering / Syzygy / PeSTO](https://www.chessprogramming.org)
- [PeSTO's Evaluation Function (Texel-tuned tables + taper, values)](https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function)
- [sunfish (pure-Python engine; 30 knps CPython / 81 knps PyPy; NNUE variant +200 Elo) — README](https://github.com/thomasahle/sunfish)
- [Embla 2.0.7 rating 2142, CCRL 40/40](https://www.computerchess.org/cgi/engine_details.cgi?eng=Embla+2.0.7+64-bit&print=Details+%28text%29)
- [ChessBase Komodo help: tablebase sizes (3-4-5 man = 938 MB)](http://help.chessbase.com/Komodo/15/Eng/000085.htm)
- Local benchmarks (this machine, 1 core, python-chess 1.11.2/numba 0.67.0/CPython 3.14, 2026-09-07) — scripts in `/tmp/bench/` (throwaway, not shipped).