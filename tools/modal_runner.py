"""Modal CPU fan-out for chessathon gate matches (dev tool, NOT shipped).

WHY: the VPS box is 6 cores — a local pooled gate (3 seeds x 24 games) needs
~30-35 min of wall and the whole box. Modal runs each shard in its own
container: 72 games over ~18-36 containers finish in single-digit minutes,
leaving the box free for builders/audits. This is the SAME code path as the
local gate (repo tools/ sprt.play_game + common.OPENING_FENS + adjudication,
engine_side_tree.py with a fixed per-move budget; both trees byte-identical
to their git archives), just fanned out.

DISCIPLINE (Sep 9 rule, unchanged): Modal's CPUs differ from the VPS, so a
500 ms budget searches a different depth -> score distributions shift. Use
Modal for VARIANT SELECTION + extra sample size; the calibrated 0.45 band
still needs a quiet-box VPS confirmation. Cross-box offset is measured by
running the SAME schedule (seed set) locally and on Modal and comparing
pooled scores — do that once per candidate, not per variant.

Semantics mirrored from tools/gate_match_tree.py:
  - schedule: per seed, for each of games//2 pairs, for order in (0, 1):
    fen = rng.choice(OPENING_FENS); order 0 -> tree A is White.
  - scoring: draw = 1/2-1/2; win if (res == "1-0") == (order == 0).
  - one long-lived engine process per side per shard; `reset` between games
    (sprt.play_game does this); flags reported and fatal for the shard.

Usage (from the repo root):
  CHESSATHON_TREE_A=/tmp/chessathon-v8ref CHESSATHON_TREE_B=/tmp/chessathon-v7ref \
    modal run tools/modal_runner.py --games 24 --seeds 7,11,13 --move-ms 500 \
      --tag v8_cal --per-shard 2

  (# needs the modal CLI; the driver itself imports no chess — the schedule
   is rebuilt inside each container from (seed, games, slice).)

Outputs (written locally at the end):
  results/gate_modal_<tag>_summary.txt   — same shape as gate_parallel
  results/gate_modal_<tag>_games.json    — per-game records
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import modal

_LOCAL_ROOT = Path(__file__).resolve().parent.parent

TREE_A = os.environ.get("CHESSATHON_TREE_A", "/tmp/chessathon-v8ref")
TREE_B = os.environ.get("CHESSATHON_TREE_B", "/tmp/chessathon-v7ref")

app = modal.App("chessathon-gate")


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
    """Play games [lo, hi) of (seed, games) inside THIS container."""
    sys.path.insert(0, "/repo")
    sys.path.insert(0, "/repo/tools")
    import subprocess

    import chess
    from common import OPENING_FENS, side_env
    from sprt import play_game

    seed, games = spec["seed"], spec["games"]
    lo, hi = spec["lo"], spec["hi"]
    move_ms = spec["move_ms"]
    t0 = time.time()

    # Rebuild the full schedule for this seed, keep our slice. Same rng
    # consumption as gate_match_tree (one rng.choice per game, inside the
    # order loop).
    rng = random.Random(seed)
    sched = []
    for _g in range(games // 2):
        for order in (0, 1):
            sched.append((rng.choice(OPENING_FENS), order))
    my = list(enumerate(sched))[lo:hi]

    def spawn(root: str, cfg: str):
        env = side_env(cfg, move_ms)
        env["NUMBA_CACHE_DIR"] = "/tmp/nc_" + Path(root).name
        env["NUMBA_NUM_THREADS"] = "1"
        return subprocess.Popen(
            [sys.executable, "/repo/tools/engine_side_tree.py", root],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, cwd="/repo", env=env)

    pa = spawn("/tree_a", spec["spec_a"])
    pb = spawn("/tree_b", spec["spec_b"])
    out = []
    try:
        for idx, (fen, order) in my:
            sides = {
                chess.WHITE: {"proc": pa, "name": "a"} if order == 0
                else {"proc": pb, "name": "b"},
                chess.BLACK: {"proc": pb, "name": "b"} if order == 0
                else {"proc": pa, "name": "a"},
            }
            gd = play_game(fen, sides, rng, timeout_s=900)
            out.append({"idx": idx, "seed": seed, "order": order,
                        "fen": fen, "result": gd["result"],
                        "flags": [list(f) for f in gd["flags"]],
                        "ply": gd["ply"]})
    finally:
        for p in (pa, pb):
            try:
                p.stdin.close()
            except Exception:
                pass
            p.kill()
    return {"seed": seed, "lo": lo, "hi": hi, "games": out,
            "elapsed": time.time() - t0}


@app.function(image=image, cpu=2.0, memory=2048, timeout=2400)
def run_shard(spec: dict) -> dict:
    try:
        return _run_shard(spec)
    except Exception as exc:  # noqa: BLE001
        return {"seed": spec.get("seed"), "lo": spec.get("lo"),
                "hi": spec.get("hi"), "games": [],
                "error": f"{type(exc).__name__}: {exc}"}


@app.local_entrypoint()
def main(games: int = 24, seeds: str = "7,11,13", move_ms: int = 500,
         per_shard: int = 2, tag: str = "modal",
         spec_a: str = "hand:1111", spec_b: str = "hand:1111"):
    seed_list = [int(s) for s in seeds.split(",") if s.strip()]
    specs = []
    for seed in seed_list:
        for lo in range(0, games, per_shard):
            specs.append({"seed": seed, "games": games, "lo": lo,
                          "hi": min(lo + per_shard, games), "move_ms": move_ms,
                          "spec_a": spec_a, "spec_b": spec_b})
    print(f"# modal gate: {len(specs)} shards, {len(seed_list) * games} games "
          f"total; trees A={TREE_A} B={TREE_B} @ {move_ms}ms", flush=True)
    t0 = time.time()
    results = list(run_shard.map(specs))
    wall = time.time() - t0

    per_game = []
    errs = []
    for r in results:
        if r.get("error"):
            errs.append(r["error"])
        per_game.extend(r["games"])
    per_game.sort(key=lambda g: (g["seed"], g["idx"]))

    def score_of(gs):
        w = l = d = 0
        for g in gs:
            if g["result"] == "1/2-1/2":
                d += 1
            elif (g["result"] == "1-0") == (g["order"] == 0):
                w += 1
            else:
                l += 1
        n = w + l + d
        return w, l, d, ((w + 0.5 * d) / n if n else 0.0)

    tw, tl, td, pooled = score_of(per_game)
    n = tw + tl + td
    se = (pooled * (1 - pooled) / n) ** 0.5 if n else 0.0
    lines = [f"=== modal gate tag={tag} ===",
             f"trees A={TREE_A} vs B={TREE_B} | {move_ms}ms/move | "
             f"seeds {seed_list} | {games} games/seed",
             f"shards {len(specs)} | wall {wall:.0f}s | errors {len(errs)}"]
    for s in seed_list:
        gs = [g for g in per_game if g["seed"] == s]
        w, l, d, sc = score_of(gs)
        lines.append(f"  seed {s:4d}: {w}W-{l}L-{d}D ({sc:.3f}) n={w + l + d}")
    lines.append(f"POOLED: {tw}W-{tl}L-{td}D over {n} games -> {pooled:.3f} "
                 f"(normal-approx 95% CI +-{1.96 * se:.3f})")
    band = ("POSITIVE (>=0.55)" if pooled >= 0.55 else
            "NEUTRAL (0.45-0.55)" if pooled >= 0.45 else "NEGATIVE (<0.45)")
    lines.append(f"band: {band}  [VPS-calibrated bands; Modal CPUs differ — "
                 f"cross-box offset not yet measured]")
    flags = [(g["seed"], g["idx"], g["flags"]) for g in per_game if g["flags"]]
    if flags:
        lines.append(f"!! FLAGS in {len(flags)} game(s): {flags[:5]}")
    if errs:
        lines.append(f"!! shard errors: {errs[:3]}")
    for ln in lines:
        print(ln, flush=True)

    outdir = _LOCAL_ROOT / "results"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"gate_modal_{tag}_summary.txt").write_text(
        "\n".join(lines) + "\n")
    (outdir / f"gate_modal_{tag}_games.json").write_text(
        json.dumps(per_game, indent=1) + "\n")
    print(f"wrote {outdir / f'gate_modal_{tag}_summary.txt'}", flush=True)
