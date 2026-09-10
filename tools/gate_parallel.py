"""Parallel multi-seed gate runner (dev tool, NOT shipped).

Runs K independent gate_match_tree.py matches CONCURRENTLY (one per seed),
then pools their scores. Same per-game regime as a single gate (fix ms/move,
colour-balanced pairs, hand-written opening pool); different seeds change
the opening order. On this box (6 cores; 1 core per engine proc; the
sanctioned cap is 3 pairs) three gates turn a ~30 min / 24-game gate into
~30 min / 72 games: 3x the evidence at the same wall clock.

Why multi-seed at all: single gates are NOISY. Two identical re-runs (same
seed 7, same trees, Sep 10) scored 0.417 and 0.562 — time-limited search
flips whole games on timing jitter, so a lone 24-game score over-reads.
The POOLED number is the decision instrument; single gates remain the
legacy format referenced by older calibration records.

Usage:
    python tools/gate_parallel.py --side-b-root /tmp/chessathon-v7ref \
        --seeds 7,11,13 --games 24 --move-ms 500 --tag v8dp

Outputs (under --outdir, default results/):
    gate_<tag>_s<seed>.log + .stream.log per gate, gate_<tag>_summary.txt

Note: does not check co-load itself; run when >= 2*K cores are free
(K=3 when the box is otherwise idle, K=2 when one other instrument runs).
"""

import argparse
import math
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SCORE_RE = re.compile(r"score:\s*(\d+)W-(\d+)L-(\d+)D\s*\(([0-9.]+)\)")
FLAG_RE = re.compile(r"FLAGS?:")

_lock = threading.Lock()


def run_one(seed, args, results, outdir):
    logp = outdir / f"gate_{args.tag}_s{seed}.log"
    streamp = outdir / f"gate_{args.tag}_s{seed}.stream.log"
    cmd = ["stdbuf", "-oL", "-eL", sys.executable,
           str(HERE / "gate_match_tree.py"),
           "--side-a", args.side_a, "--side-b", args.side_b,
           "--side-b-root", args.side_b_root,
           "--games", str(args.games), "--move-ms", str(args.move_ms),
           "--seed", str(seed), "--log", str(logp)]
    t0 = time.time()
    w = l = d = 0
    flags = []
    rc = None
    try:
        with open(streamp, "w") as sf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 text=True, cwd=str(ROOT))
            assert p.stdout is not None
            for line in p.stdout:
                sf.write(line)
                sf.flush()
                print(f"[s{seed}] {line.rstrip()}", flush=True)
                if FLAG_RE.search(line):
                    flags.append(line.strip())
                m = SCORE_RE.search(line)
                if m:
                    w, l, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            rc = p.wait()
    except Exception as exc:  # noqa: BLE001
        rc = f"EXC {exc!r}"
    rec = dict(seed=seed, w=w, l=l, d=d, rc=rc, flags=flags,
               secs=time.time() - t0, stream=str(streamp))
    with _lock:
        results[seed] = rec
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side-a", default="hand:1111")
    ap.add_argument("--side-b", default="hand:1111")
    ap.add_argument("--side-b-root", required=True)
    ap.add_argument("--seeds", default="7,11,13")
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--move-ms", type=int, default=500)
    ap.add_argument("--tag", default="par")
    ap.add_argument("--max-parallel", type=int, default=3)
    ap.add_argument("--outdir", default=str(ROOT / "results"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    print(f"# gate_parallel tag={args.tag} seeds={seeds} games={args.games} "
          f"move-ms={args.move_ms} parallel={args.max_parallel} "
          f"out={outdir}", flush=True)

    # polite heads-up if other engine work is already running
    try:
        other = subprocess.run(["pgrep", "-fc", "gate_match_tree"],
                               capture_output=True, text=True)
        n = int((other.stdout or "0").strip() or 0)
        if n > 0:
            print(f"# WARN: {n} other gate_match_tree process(es) running — "
                  f"expect co-load", flush=True)
    except Exception:  # noqa: BLE001
        pass

    results = {}
    pending = list(seeds)
    threads = []
    t0 = time.time()
    while pending or threads:
        while pending and len(threads) < args.max_parallel:
            s = pending.pop(0)
            th = threading.Thread(target=run_one,
                                  args=(s, args, results, outdir), daemon=True)
            th.start()
            threads.append(th)
        time.sleep(0.5)
        threads = [t for t in threads if t.is_alive()]

    elapsed = time.time() - t0
    tw = sum(r["w"] for r in results.values())
    tl = sum(r["l"] for r in results.values())
    td = sum(r["d"] for r in results.values())
    n = tw + tl + td
    score = (tw + 0.5 * td) / n if n else 0.0
    se = math.sqrt(score * (1 - score) / n) if n else 0.0

    lines = [f"=== gate_parallel tag={args.tag} ===",
             f"seeds {seeds} | games/gate {args.games} @ {args.move_ms}ms | "
             f"wall {elapsed:.0f}s"]
    for s in sorted(results):
        r = results[s]
        n_i = max(1, r["w"] + r["l"] + r["d"])
        per_seed = (r["w"] + 0.5 * r["d"]) / n_i
        flag_note = f" FLAG-LINES:{len(r['flags'])}" if r["flags"] else ""
        lines.append(f"  seed {s:4d}: {r['w']}W-{r['l']}L-{r['d']}D "
                     f"({per_seed:.3f}) rc={r['rc']} {r['secs']:.0f}s"
                     f"{flag_note}")
    lines.append(f"POOLED: {tw}W-{tl}L-{td}D over {n} games -> {score:.3f} "
                 f"(normal-approx 95% CI +-{1.96 * se:.3f})")
    band = ("POSITIVE (>=0.55)" if score >= 0.55 else
            "NEUTRAL (0.45-0.55)" if score >= 0.45 else
            "NEGATIVE (<0.45)")
    lines.append(f"band: {band}   [bands as calibrated solo; pooled N "
                 f"tightens them, it does not shift them]")
    total_flags = sum(len(r["flags"]) for r in results.values())
    if total_flags:
        lines.append(f"!! {total_flags} FLAG line(s) — inspect the per-gate "
                     f"streams before trusting this run")
    summary_path = outdir / f"gate_{args.tag}_summary.txt"
    summary_path.write_text("\n".join(lines) + "\n")
    for ln in lines:
        print(ln, flush=True)
    print(f"summary: {summary_path}", flush=True)
    return 0 if total_flags == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
