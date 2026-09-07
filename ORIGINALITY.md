# ORIGINALITY & COMPLIANCE — MANDATORY READING (highest priority)

> **Every agent that writes code in this repo MUST read this file first and
> comply. Violations risk retroactive disqualification of the entire team.**
> Source: https://aichessathon.com/docs (verified 2026-09-07). When in
> doubt, ask Pino before proceeding — never guess.

## Why this exists

The AI Chessathon bans third-party engines and requires that everything we
ship is **our own original work**: code we wrote, models we trained. Judges
read the source of any flagged game, every finalist walks through how the
agent was built, obfuscated agents are disqualified, and disqualification
**can be retroactive**. Our edge must be a *well-built original engine*,
never a copied one.

## The rules (verbatim from the official docs)

- **Third-party engines are prohibited. That means Stockfish, Lc0, Maia and
  any wrapper around one.** Your moves come from code you wrote and any
  model you ship is one you trained.
- **An engine you wrote yourself before the event is your own code.**
- **A model is not required; a classical search is a full entry.**
- **Training data is unrestricted**, including positions annotated by an
  existing engine. (This permits *learning from* engine output — it does
  NOT permit *shipping* an engine or its code.)
- **Books and tablebases are permitted as shipped data** (`chess.polyglot`
  and `chess.syzygy` are in the base image).
- **What you ship has to be source a judge can read** — a flagged game can
  be cleared by reading your agent. Model weights (`.onnx`, `.safetensors`,
  `.pt`) are fine as *data*; native binaries are rejected.
- **Obfuscated agents are disqualified.** Each finalist team walks through
  how its agent was built.

## What this means for us — HARD RULES

### ✅ ALLOWED (and our plan)
1. **Write every line of engine code ourselves**, from scratch, in this
   repo, during this event. The commit history of this repo IS the proof
   of original development.
2. **Standard, published algorithms are public knowledge** — implementing
   negamax, alpha-beta pruning, iterative deepening, transposition tables,
   quiescence search, MVV-LVA / killer / history move ordering, null-move
   pruning, LMR, and piece-square-table evaluation *fresh, in our own
   code*, is original work. (These are concepts, like knowing the rules of
   chess. The code we write around them must be ours.)
3. **A neural net is OPTIONAL but legal IF we train it ourselves.** The
   official rule: "any model you ship is one you trained" and "the ban
   covers only what ships inside the submission." **Training can happen
   ANYWHERE — locally, on Modal GPUs, on a rented box — only the weights
   ship.** `.onnx`, `.safetensors` and `.pt` weights are judge-readable
   data (not native binaries) and are explicitly allowed in the zip.
   Training data is unrestricted, including positions annotated by an
   existing engine. The line: we never ship someone else's weights or
   inference code — we ship OUR weights + OUR Python inference (onnxruntime
   is preinstalled on the box).
4. **Opening books and tablebases as data files** if we choose to use
   them (polyglot books, Syzygy TBs). These are shipped *data*, explicitly
   permitted.
5. **Use Stockfish ONLY as a local sparring partner for strength testing**
   — downloaded OUTSIDE this repo (e.g. `/tmp` or `~/tools`), never
   committed, never in the zip. It may also annotate OUR training data
   (data is unrestricted) — but only ever as a data generator, never as
   shipped code or shipped weights. Keep it fully out of the repo so it
   can never leak into a build.

### ❌ FORBIDDEN
1. **NO copying, pasting, porting, or "adapting" any existing engine's
   source code** — not sunfish, not python-chess example engines, not
   Stockfish derivatives, not any GitHub engine. Reading about algorithms
   is fine; copying implementation files is not. If an agent is tempted to
   "use this open-source engine as a starting point" — THAT IS A VIOLATION.
   Start from an empty file and write our own.
2. **NO shipping any pretrained / downloaded model weights** (no Stockfish/
   Leela/Maia nets, no downloaded `.onnx`/`.pt` checkpoints we didn't
   train). We MAY train our own net anywhere and ship OUR weights — but
   downloading someone else's trained net is a violation even as data.
3. **NO wrapping or calling any external engine**, at runtime or via
   subprocess, in the submission.
4. **NO native binaries / compiled extensions** in the zip (also
   technically impossible — no compiler in the image, Cython rejected).
5. **NO obfuscation, minification, or hiding what the code does.** Every
   module must be readable and explainable. We keep a `BUILD.md` design
   log so Pino can walk a judge through every design decision.
6. **NO code fetched from the internet during the build** — agents work
   offline from the research KB; the KB cites sources for *knowledge*, but
   the implementation is written here.

## Provenance practices (make originality visible)

1. **Frequent, granular commits** as the engine is built — the git history
   shows the code growing organically. No giant single "import engine"
   commit.
2. **`BUILD.md`** at repo root: design decisions, why each component
   exists, what we tried, what we measured. Updated as we go.
3. **Every source file** starts with a short header comment: what it does
   and the design intent (readable by a judge).
4. **A `make_zip.sh`** that assembles the submission from exactly the
   files we intend (agent.py + data) — nothing else, no strays.
5. Research docs may cite external sources and standard eval-table values
   (e.g. published PST numbers) with attribution — using published
   *numbers/data* with citation is acceptable, but prefer values we tune
   ourselves so the eval is demonstrably ours. If we use a published PST
   table, we say so in BUILD.md with the source.

## The one-sentence rule

> **Everything inside agent.zip is code we wrote in this repo during this
> event (plus permitted data files), and we can explain all of it to a
> judge. If we did not write it here, it does not ship.**

— Pino (team lead), 2026-09-07
