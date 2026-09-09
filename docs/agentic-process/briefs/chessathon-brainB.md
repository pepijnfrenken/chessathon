# Chess brainstorm — AGENT B: meta / wild / different-approach probes

## Mission (research/brainstorm, READ-ONLY — you NEVER write the repo)
Pino wants RADICAL, different-approach ideas for the chessathon — anything
outside the classical-search-tweak box that the rules permit, tested
against the shipped V5 engine. Think: winning the LADDER/ELO game, not
just the position game. Ranked probe menu with implementation sketches.
Ground everything in the repo + the actual ladder corpus. No idea is too
weird as long as it is (a) legal under ORIGINALITY.md, (b) implementable
in ≤1 day, (c) testable head-to-head vs V5.

## Repo + rules
- Repo: ~/projects/chessathon. ORIGINALITY.md is LAW (everything shipped
  = code we wrote in-repo this event; no third-party code, no pretrained
  models; books/data allowed only if self-generated). Classical search
  allowed as a full entry; the engine exposes get_move(fen, time_left_ms)
  -> uci in agent.py, plus init hook; 1 core, 2GB RAM, no network at
  match time, 120s+0.5s clock, 60s init, pondering ALLOWED (process stays
  alive between get_move calls — but note the stateful engine already
  persists game state; check what survives).
- READ-ONLY: never modify the repo. Report: /tmp/chess-brainB-report.md
  (append as you go).
- Model hiccups: wait 20-60s, retry; never guess. PY = /tmp/chessbench/bin/python.

## Read first
1. ORIGINALITY.md (rules — before anything)
2. agent.py FULL — what state survives between get_move calls, what the
   harness does before/after (reset calls? same-process lifetime?)
3. PROCESS.md §5-6; results/matches/ round PGNs + .log files — the ladder
   corpus (~r48-r71): opponent names, our results, %clk time data where
   present. What are the opponents' patterns? (Weak bots blundering late?
   Flag-play? Deep openers? Draw-offers?)
4. engine/time.py budget policy; engine/search.py head comments; docs/
   research/ if any.
5. Ladder facts in PROCESS.md §6 P4: rank 336/387, ~45-50 rated rounds
   left before freeze, uploads ≤6/day until Sep 11 11:00, latest-passing
   upload plays.

## What to produce — 5-8 ranked probes
Themes to develop (invent beyond these — that's the job):
- OPPONENT-ADAPTIVE meta (legal? allowed data = our own games + public
  ladder info? check ORIGINALITY + what we can know pre-game — the
  competition may announce pairings; can agent.py read anything at init?)
- OPENING SELECTION: self-generated book from our own engine games —
  sharp-vs-solid per opponent class, clock-economy lines, avoiding lines
  where OUR eval skew (Quirk 1) bites
- PONDERING exploitation: what exactly can we compute between moves
  within the box contract (2GB, own core, process alive)? Pre-search
  opponent replies; keep a warm TT; note init<60s constraint.
- ENDGAME "opponent is weak" exploitation: deliberate simplification
  strategy vs low-rated bots (they misplay K+P endings) — but framed from
  EVIDENCE in the ladder corpus (how do our losses actually happen vs
  wins? who flags? who shuffles?)
- TIME/FLAG game: geometric decay is never-flag by design; opponents'
  time profiles from %clk (r70 profiling showed 7-20s openers) — is
  there a legal clock-pressure strategy? (120s+0.5)
- DETERMINISM as a weapon/weakness: our engine is deterministic per
  clock; opponents may replay OUR games (we're public?) — what leaks?
  (build-version fingerprinting, PROCESS.md §5 #8)
- Anything ELSE legal that a 1-core classical engine can do that nobody
  else will have done.
For each: idea / why it wins games (cite ladder evidence) / legality
check vs ORIGINALITY.md + box contract / implementation sketch + effort /
test design vs V5 (head-to-head gates at 500ms AND real-clock sims —
regime matters; see PROCESS.md gate notes) / risk.

## Verdict discipline
End with TOP-3 for this week + one "too weird, but note for the write-up"
idea. Final summary = LAST section of /tmp/chess-brainB-report.md.
