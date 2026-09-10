# chess-q5 — fresh-eyes audit: codex round 3 (V6 real-world debut + night build state)

COMPS-BE-FIRST READ ONLY AUDIT. Nothing runs on the box while a gate is active (no new engine runs, gates, or replays); small read-only checks and lightweight SF pass-through analysis are fine. Read ORIGINALITY.md, the latest PROCESS.md section, and the relevant gate records.

## Situation summary (as of this audit)

V6 (null-fix, codex1 H1) was uploaded and ACTIVATED on the ladder — but its FIRST real ladder game (round 90, 21:00 UTC Sep 9) went **1-0 against Chessbuster 9000** as White, checkmate after ~116 moves.

The critical tension:
- L1 gate (24 @500ms, head:1111, seed 7) = **16W-6L-2D = 0.708** — the best gate in repo history, zero flags, the first above-null-band L1 since Phase 4.
- L2 on the corrected 78-FEN corpus: 18/78 moves changed, mean delta -5.0cp, one ≥300cp regression (r76 p122 Rxh8, same move, eval_before -959 — mate-range stratum), but the fix **finds mate at r81 p82 (+28134 vs +18532, V5 misses)** — evidence the fix helps in lost positions.
- r90 SF review (depth 18, White side): {'excellent': 9, 'best': 37, 'mistake': 2, 'good': 4, 'inaccuracy': 6, 'blunder': 1}. Biggest: Nf8 (498cp blunder), Ne6+ (354cp blunder), d7 (309cp blunder), Nxd7 (295cp mistake), Rc6 (235cp mistake). One blunder, two mistakes total — but the blunder was fatal: a **7649cp Kf1 blunder** (king walk into mating net / rook infiltration, likely horizon artifact).

**V5's last 6 rounds (r83-r88, before r90): 0.5/6 (L-D-L-L-L-L)**. V5 era record: 16W-10D-14L.
**V6 era (r90+)**: 0-0-1 so far (one loss).

**NIGHT QUEUE (q5-fix1, ongoing until ~06:30 UTC on the VPS):**
- Item 1 (endgame-eval fix, codex1 §7): COMMITTED as 3c06692 — "insufficient-material zeroing no longer throws away KBN-v-K (codex1 §7)". The KBN-v-K / KNNN-v-K zero-eval bug is fixed.
- Item 2 (PST pawn-flip, codex1 H2): **STATUS UNKNOWN at this moment**. The watcher fired a false-positive on the COMPCLAMP commit (2a115cd) at 20:55; I re-armed the watcher with a stricter filter ("L1" + pawn-flip wording). Codex2 was stopped before it could do anything wrong. **Has item 2 committed? If so, what's its gate record? If not, what's its state?**
- Item 3 (H3 root ordering): **STATUS UNKNOWN**.
- Zip staging at /tmp/night-candidates/: check what zips are staged.

## Requested analysis (the core of this audit)

The repair of the night-queue items is good progress — KBN-v-K throwing away won endgames is a real blunder-class fix. But the bigger question is: **why did V6 lose its first real game when the L1 gate was 0.708?**

### Hypothesis A: r90 was a statistical fluke
- One long game (116 moves), one catastrophic blunder (Kf1 at 7649cp — a king-safety collapse). The rest of the game was good: 37 best, 9 excellent, 4 good, only 2 mistakes and 1 blunder. Maybe Chessbuster 9000 played well enough to punish a single miss.
- Risk: if fluke, we're fine. If not, we're shipping a regression.

### Hypothesis B: the L1 gate (500ms/game) doesn't capture real-clock failure modes
- 500ms time control per move vs real 120s+0.5s. At short clocks, the search depth is limited and the null-move fix gives +20% nodes → deeper tree within the budget → better play.
- At real clocks, the tree is ALREADY deep enough that the null-move fix's benefit is smaller or zero — but NEW failure modes (like the Kf1 blunder: horizon/mate-in-N missed because the null-move pruning PRUNED the critical variation, or the qsearch missed the mating sequence) can emerge.
- The Kf1 blunder at 7649cp is suspicious: it's exactly the kind of error you'd expect if the null-move pruning cut a branch that contained the mating sequence. The original codex1 H1 hypothesis was correct (the sign error was real), but the FIX itself might have introduced a new search artifact.
- This is testable: replay r90's pre-Kf1 position (before the 7649cp blunder) with the null-fix ON vs the null-fix OFF (V5) vs the corrected-sign version, and see which variant finds the mate. If the null-fix ON misses it when OFF/V5 finds it, we have a regression.

### Hypothesis C: V6 played a worse move earlier and got into a bad position that it couldn't escape
- The review shows the GAME was good for most of the moves (37 best) — so the engine was playing well. The Kf1 blunder late-game killed it.
- This is consistent with Hypothesis A or B — if the position was fine until the blunder, it's a fluke + search artifact. If the position deteriorated earlier (and the blunder was the culmination), we need to know where.

### Hypothesis D: V5 would also have lost this game
- V5 lost 4 of its last 6 games (r83-r88). V5 is not winning. Maybe Chessbuster 9000 just beats both.
- Testable: replay r90's critical positions with V5 (the known good version) — if V5 makes the SAME Kf1 blunder (or a different fatal one), then r90 is not a V6 regression, it's just a hard game. If V5 finds the mate or avoids the blunder, r90 is a V6 regression.

### Hypothesis E: the Kf1 blunder is a horizon problem in the qsearch or mate-recognition
- Kf1 is a king move INTO danger. If the evaluation doesn't properly penalize king positions near enemy pieces, or the qsearch misses a forced sequence, the search could see Kf1 as roughly equal and play it.
- The night-queue item 1 (KBN-v-K fix) is relevant here: if the insufficient-material zeroing was masking KBN-v-K as a draw, the engine might not search properly for KBN vs K mates. But r90 was a queen+rook vs king endgame, not KBN-v-K — different endgame class. Still, the general pattern of "endgame mate recognition fails" could be the common thread.
- The Kf1 blunder might be a **horizon + evaluation interaction**: the engine evaluates the Kf1 position as roughly equal (because it doesn't see the deep mate), and plays it because it thinks the king is safe. If the evaluation properly penalized king safety in this endgame structure, or if the search had an extra ply, the blunder might not happen.

## Specific questions for codex

1. **Has the PST pawn-flip (item 2) committed? If so, what is its gate record? If not, what is fix1 currently doing?** Read the latest 20 git log lines and the current PROCESS.md section.
2. **Replay the r90 critical position(s) with V6 vs V5 vs the null-fix-variants**: find the position just before Kf1 (the 7649cp blunder), replay it at real-clock-equivalent depth with (a) V5-as-shipped, (b) V6-as-shipped (null-fix ON), (c) null-fix OFF (byte-identical to V5 in that one line), (d) a deeper search (extra time budget). Which variant finds the mate? Which variant plays Kf1? This is the crux.
3. **Is the Kf1 blunder a horizon problem, an evaluation problem, or a search artifact?** Decompose the Kf1 position: what does the static eval say? What does the qsearch see? What does the full search see at depth N vs N+1? Is the mating sequence within horizon of the search, or beyond?
4. **What is the risk of repeat Kf1-style blunders?** If the null-fix introduces a new pruning artifact that hides mating sequences in king-endgames, we could get repeat failures. Estimate: in a typical long endgame, how often does the null-move pruning cut a branch that contains the only mating sequence? Is this rare or common?
5. **Should V6 be rolled back to V5 for the remaining Sep 10 rounds?** If r90 was a regression (V5 would have won this game, or V6 has a repeatable failure mode), and we have time before the freeze, rolling back to V5 and then uploading a fixed version is safer than shipping v6-now and hoping r90 was a fluke. If r90 was a fluke (V5 would have lost too), keep V6.
6. **What is the path forward?** Options:
   - (a) Keep V6, diagnose the Kf1 blunder, fix it (horizon/mate-recognition patch), re-gate, upload → play the fixed version from ~r92 onward.
   - (b) Roll back to V5 NOW, play V5 for r91-r94 (if any), then upload a fixed V6.1 before the freeze. V5 is currently safer (proven in real games), but it's losing too (0.5/6). So we'd be playing a losing version for 2-3 rounds while we fix V6.
   - (c) Keep V6, don't fix the Kf1 blunder specifically, but fix the general endgame/horizon problem (the KBN-v-K fix is already in; maybe add mate-recognition to qsearch, or king-safety evaluation terms) — a broader fix that addresses both the r90 blunder and any similar patterns.
   - (d) Keep V6, accept the r90 loss as a fluke, play V6 for the remaining rounds, and only fix if a pattern emerges.

## Evidence available for replay
- /home/pino/projects/chessathon/results/matches/round-90-vs-chessbuster-9000.pgn (the game)
- /home/pino/projects/chessathon/results/leak_reviews/round-90-vs-chessbuster-9000.sf18.json (the review — already exists)
- The v6 build: /tmp/chess-v6-nullfix.zip (current active version on ladder)
- V5 build: /tmp/chess-v5-reference.zip or equivalent (the version V5 played before V6 activation)
- The night-queue commits (if any): git log --oneline on the repo
- The PST decomposition: docs/research/07-pst-phantom-decomposition.md (if it exists)
- The eval_decompose.py tool (if it exists): tools/eval_decompose.py

## Hard rules
- READ-ONLY: no code changes, no uploads, no new engine-vs-engine games. Read the repo, read the PGNs, read the reviews, run light analysis. If a search replay is needed, keep it to ONE position at a time, one engine process, short (1-2 min max). Never start a full gate.
- Provider: codex quota. If it dies, save partial and exit. Never OpenRouter.
- Output: /tmp/chess-q5-codex3-report.md + chat summary. Verdict: (1) is r90 a regression or fluke? (2) what's the Kf1 blunder mechanism? (3) keep V6 or roll back? (4) what's the path forward? (5) status of night-queue items 2 and 3.

## Time context
We have time until the freeze (Sep 11 10:00 UTC). The ladder rounds continue hourly 07:00-22:00 UTC (so r91 is due ~22:00 UTC Sep 9, r92 ~23:00, etc.). V6 is currently the active build on the ladder (if validation passed and r90 was against V6). The user wants an audit and verdict now so we can decide whether to keep playing V6 or roll back.

<!-- source session: 2026-09-09T21-53-00-583Z_01a08828 -->
