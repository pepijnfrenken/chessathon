"""Modal fan-out for the LADDER-FORMAT bout (dev tool, NOT shipped).

Same idea as tools/bout_ladder.py — full games from the ACTUAL ladder start
positions at the real 120 s + 0.5 s clock — but fanned across Modal
containers instead of pinned to the 6-core VPS. Each container plays one
colour-balanced pair (the same FEN twice, colours swapped) with a single
pair of engine processes (real-clock per-move budgets via
tools/engine_side_clk.py + each tree's own engine/time.py).

The VPS stays free for builders/auditors; here 24 games ≈ 12 min wall.

Usage (from the repo root):
  CHESSATHON_TREE_A=/tmp/chessathon-v8ref CHESSATHON_TREE_B=/tmp/chessathon-v7ref \
    modal run tools/modal_bout.py --games 24 --seed 11 --per-shard 2 --tag v8_vs_v7

Ladder FENs are parsed locally from results/matches/round-*.log (no chess
needed in the driver), deduped, then seeded-shuffled into pairs.

Outputs: results/bout_modal_<tag>_summary.txt + _games.json
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path

import modal

_LOCAL_ROOT = Path(__file__).resolve().parent.parent

TREE_A = os.environ.get("CHESSATHON_TREE_A", "/tmp/chessathon-v8ref")
TREE_B = os.environ.get("CHESSATHON_TREE_B", "/tmp/chessathon-v7ref")

START_FEN_RE = re.compile(r"^\s*Start FEN\s+(.+)$", re.M)
ROUND_RE = re.compile(r"^\s*Round\s+Rated (\d+)", re.M)
OPENING_RE = re.compile(r"^\s*Opening\s+(.+)$", re.M)

app = modal.App("chessathon-bout")


def _ignore(path: Path) -> bool:
    parts = set(path.parts)
    junk = {".git", "__pycache__", ".venv", "venv", "node_modules",
            "docs", "results", "data", "tmp", "sessions", ".aiwg"}
    return bool(parts & junk) or path.suffix in {".pyc", ".zip"}


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("numpy", "numba", "chess")
    .add_local_dir(str(_LOCAL_ROOT), remote_path="/repo", ignore=_ignore,
                   copy=True)
    .add_local_dir(TREE_A, remote_path="/tree_a", ignore=_ignore, copy=True)
    .add_local_dir(TREE_B, remote_path="/tree_b", ignore=_ignore, copy=True)
)


def _run_shard(spec: dict) -> dict:
    """Play the games in this shard (real clock) in THIS container."""
    sys.path.insert(0, "/repo")
    sys.path.insert(0, "/repo/tools")
    import chess  # noqa: F401  (bout_ladder imports it too)

    from bout_ladder import load_budget_fn, play_game, spawn, wait_ready

    def log(line: str):
        print(line, flush=True)

    base_ms, inc_ms = spec["base_ms"], spec["inc_ms"]
    grace_s = spec["grace_s"]
    t0 = time.time()
    budget_a = load_budget_fn("/tree_a")
    budget_b = load_budget_fn("/tree_b")
    pa = spawn("/tree_a", "/tmp/nc_a", "hand:1111")
    pb = spawn("/tree_b", "/tmp/nc_b", "hand:1111")
    out = []
    fatal = False
    try:
        wait_ready(pa, "A", log)
        wait_ready(pb, "B", log)
        rng = random.Random(0)
        for i, gspec in enumerate(spec["games"]):
            log(f"game {spec['lo'] + i + 1} round {gspec['round']} "
                f"{'A' if gspec['a_white'] else 'B'}-white "
                f"({gspec.get('opening', '')})")
            g = play_game(pa, pb, spec["name_a"], spec["name_b"], gspec, rng,
                          budget_a, budget_b, base_ms, inc_ms, grace_s, log,
                          spec["lo"] + i + 1)
            if g is None:
                log("  (skip: game already over at start FEN)")
                continue
            dts = g["movetimes"]
            out.append({
                "idx": spec["lo"] + i, "round": gspec["round"],
                "fen": gspec["fen"], "a_white": gspec["a_white"],
                "result_w": g["result_w"], "res_a": g["res_a"],
                "flags": [list(f) for f in g["flags"]], "ply": g["ply"],
                "wall_s": round(g["wall_s"], 1),
                "mv_avg_ms": round(sum(dts) / max(1, len(dts)), 1),
                "mv_max_ms": round(max(dts, default=0.0), 1),
            })
            if g["fatal"]:
                fatal = True
                break
    finally:
        for p in (pa, pb):
            try:
                p.stdin.close()
            except Exception:
                pass
            p.kill()
    return {"lo": spec["lo"], "games": out, "fatal": fatal,
            "elapsed": time.time() - t0}


@app.function(image=image, cpu=2.0, memory=2048, timeout=3600)
def run_shard(spec: dict) -> dict:
    try:
        return _run_shard(spec)
    except Exception as exc:  # noqa: BLE001
        return {"lo": spec.get("lo"), "games": [], "fatal": True,
                "error": f"{type(exc).__name__}: {exc}"}


def _ladder_pool(min_round: int):
    out, seen = [], set()
    for log in sorted((_LOCAL_ROOT / "results" / "matches").glob("round-*.log")):
        txt = log.read_text(errors="replace")
        rm, fm = ROUND_RE.search(txt), START_FEN_RE.search(txt)
        if not (rm and fm):
            continue
        rnd = int(rm.group(1))
        if rnd < min_round:
            continue
        fen = fm.group(1).strip()
        if fen in seen:
            continue
        seen.add(fen)
        op = OPENING_RE.search(txt)
        out.append({"round": rnd, "fen": fen,
                    "opening": op.group(1).strip() if op else ""})
    out.sort(key=lambda d: d["round"])
    return out


@app.local_entrypoint()
def main(games: int = 24, seed: int = 11, per_shard: int = 2,
         base_ms: int = 120000, inc_ms: int = 500, grace_s: float = 90.0,
         min_round: int = 48, tag: str = "ladder",
         name_a: str = "A", name_b: str = "B"):
    if games % 2:
        sys.exit("--games must be even (colour-swapped pairs)")
    pool = _ladder_pool(min_round)
    rng = random.Random(seed)
    picks = rng.sample(pool, min(len(pool), games // 2))
    sched = []
    for item in picks:
        sched.append(dict(item, a_white=True))
        sched.append(dict(item, a_white=False))

    specs = []
    for lo in range(0, len(sched), per_shard):
        specs.append({"games": sched[lo:lo + per_shard], "lo": lo,
                      "base_ms": base_ms, "inc_ms": inc_ms,
                      "grace_s": grace_s, "name_a": name_a, "name_b": name_b})
    print(f"# modal ladder-format bout: {len(sched)} games over {len(specs)} "
          f"shards | pool {len(pool)} FENs (r{min_round}+) | seed {seed} | "
          f"{base_ms}ms+{inc_ms}ms | A={TREE_A} B={TREE_B}", flush=True)
    t0 = time.time()
    results = list(run_shard.map(specs))
    wall = time.time() - t0

    per_game, errs, fatal_shards = [], [], 0
    for r in results:
        if r.get("error"):
            errs.append(r["error"])
        if r.get("fatal"):
            fatal_shards += 1
        per_game.extend(r["games"])
    per_game.sort(key=lambda g: g["idx"])

    w = l = d = 0
    for g in per_game:
        if g["res_a"] == 1.0:
            w += 1
        elif g["res_a"] == 0.0:
            l += 1
        else:
            d += 1
    n = w + l + d
    score = (w + 0.5 * d) / n if n else 0.0
    se = (score * (1 - score) / n) ** 0.5 if n else 0.0
    dts = [g["mv_avg_ms"] for g in per_game]
    lines = [f"=== modal ladder-format bout tag={tag} ===",
             f"A={TREE_A} vs B={TREE_B} | real clock {base_ms}+{inc_ms}ms | "
             f"seed {seed} | games {n} over {len(specs)} shards | wall {wall:.0f}s",
             f"A score: {w}W-{l}L-{d}D ({score:.3f}, normal-approx 95% CI "
             f"+-{1.96 * se:.3f})"]
    if dts:
        lines.append(f"avg move time {sum(dts) / len(dts):.0f}ms "
                     f"(max avg {max(dts):.0f}ms)")
    flags = sum(len(g["flags"]) for g in per_game)
    lines.append(f"flags {flags} | fatal shards {fatal_shards} | errors {len(errs)}")
    if flags:
        for g in per_game:
            if g["flags"]:
                lines.append(f"  FLAG g{g['idx']} r{g['round']}: {g['flags']}")
    for ln in lines:
        print(ln, flush=True)

    outdir = _LOCAL_ROOT / "results"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"bout_modal_{tag}_summary.txt").write_text(
        "\n".join(lines) + "\n")
    (outdir / f"bout_modal_{tag}_games.json").write_text(
        json.dumps(per_game, indent=1) + "\n")
    print(f"wrote {outdir / f'bout_modal_{tag}_summary.txt'}", flush=True)
