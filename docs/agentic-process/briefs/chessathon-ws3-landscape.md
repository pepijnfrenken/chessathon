# Chessathon Research — Workstream 3: Competition Landscape & Rules

You are building the RESEARCH KNOWLEDGE BASE for a chess-engine competition (AI Chessathon, London, Sept 2026, Optiver-sponsored). Produce **markdown docs**, NOT code. Save output under `/home/pino/projects/chessathon/docs/research/`.

## Context (verified from the official site + docs)
- Qualification 4-11 Sep 2026, online, worldwide, rated ladder (hourly rounds 08:00-22:00), then a 13-round Swiss over locked builds decides London seats (50 seats, UK uni students for the in-person final 12 Sep).
- Environment: 1 core, 2GB RAM, no GPU/network; python-chess 1.11.2 + torch-cpu/numpy/onnxruntime/numba; 120s+0.5s/move; 60s init; pondering allowed; 50MB zip; classical search a full entry; 3rd-party engines banned in submission; books/tablebases allowed; house bots with public CCRL ratings play the ladder.
- Prize £1000/500/250; Daily Five side event 6-10 Sep (5 positions, 20 min, no engines, UK students, 3 daily wildcard seats).

## Your task: write `docs/research/04-competition-landscape.md`
Research (web, GitHub, prior art) and document:

1. **What it takes to win a "build a chess engine in a week" comp** — find similar competitions (e.g. previous chess AI hackathons, SEER/Weiss-type dev stories, Lichess bot championships, TCEC amateur classes, "chess programming wiki" guidance, prior Optiver/quant-sponsored chess events if any). What Elo/CCRL do winning amateur engines typically have? What's the realistic bar to place top-3 in a 50-seat final of UK CS students with 1 core/120s?
2. **CCRL rating context**: what does a ~2000 / ~2400 / ~2600 CCRL blitz engine look like in terms of search depth and eval (nodes/sec on 1 core)? Map "depth 6-8 numba-jitted alpha-beta with PST eval" to an approximate CCRL/lichess strength. What do the house bots (CCRL public) imply about the ladder baseline?
3. **Lessons from past winners / strong amateur engines**: what separates winning entries (search depth? eval quality? time management? avoiding blunders/losing on time? opening book?). Common failure modes (illegal moves, crashes, time losses, horizon blunders) and how the rules punish them.
4. **Rule exploitation / strategy**: with 300-ply adjudication on material, pondering allowed, 0.5s increment, 60s init, and games from curated level positions — what strategic edges exist? (e.g. safe time management to never flag, forcing wins into tablebase positions, playing solidly to avoid blunders vs gambling for tricks). Daily Five fair-play considerations (do NOT advise cheating; just note the human-only constraint and that wildcard seats are separate).
5. **Team + logistics**: 1-3 people; submission rate 6/day; validation smoke games; uploads close 11 Sep 11:00. Recommend a build/test/upload schedule for a solo dev or 2-person team from Sep 7 to Sep 11 (we're already mid-qualification). What to prioritize with limited days: correctness > strength > speed? At what point do you lock builds vs iterate?

Be honest about uncertainty (we don't know the exact field strength). Dense, practical, cited, under ~200 lines.

<!-- source session: 2026-09-07T06-32-44-566Z_01a07a91-b516-7000-99f5-c07b34a803c1.jsonl -->
