"""Modal runner for a per-tree probe script (dev tool, NOT shipped).

Runs an arbitrary probe script ONCE PER TREE inside one container, each in
its own NUMBA_CACHE_DIR, and returns the captured stdout for each. Used for
cheap diagnostics that need a real engine (r92 tunnel picks, static reads,
depth sweeps) without touching the 6-core VPS box.

Usage (from the repo root):
  CHESSATHON_TREE_A=/tmp/chessathon-v9k CHESSATHON_TREE_B=/tmp/chessathon-v8ref \
    modal run tools/modal_probe.py --script tools/probe_r92_collapse.py \
      --env SWEEP=1 --tag r92_v9k

Outputs: results/probe_modal_<tag>.txt
"""

import os
import sys
from pathlib import Path

import modal

_LOCAL_ROOT = Path(__file__).resolve().parent.parent

TREE_A = os.environ.get("CHESSATHON_TREE_A", "/tmp/chessathon-v8ref")
TREE_B = os.environ.get("CHESSATHON_TREE_B", "/tmp/chessathon-v7ref")

app = modal.App("chessathon-probe")


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


@app.function(image=image, cpu=1.0, memory=2048, timeout=1800)
def run_probe(spec: dict) -> dict:
    import subprocess

    script = spec["script"]          # path inside /repo (e.g. tools/x.py)
    env_extra = spec["env"]
    out = {}
    for label, root in (("A", "/tree_a"), ("B", "/tree_b")):
        env = dict(os.environ)
        env["NUMBA_CACHE_DIR"] = f"/tmp/nc_probe_{label}"
        env["NUMBA_NUM_THREADS"] = "1"
        env.update(env_extra)
        p = subprocess.run(
            [sys.executable, f"/repo/{script}"], cwd=root, env=env,
            capture_output=True, text=True, timeout=1500)
        out[label] = {"root": root, "rc": p.returncode,
                      "stdout": p.stdout[-20000:],
                      "stderr_tail": p.stderr[-2000:]}
    return out


@app.local_entrypoint()
def main(script: str = "tools/probe_r92_collapse.py", tag: str = "probe",
         env: str = ""):
    env_extra = {}
    for kv in env.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            env_extra[k.strip()] = v.strip()
    print(f"# modal probe: script={script} env={env_extra} "
          f"A={TREE_A} B={TREE_B}", flush=True)
    res = run_probe.remote({"script": script, "env": env_extra})
    lines = [f"=== modal probe tag={tag} ===",
             f"script {script} | env {env_extra}",
             f"A = {TREE_A}", f"B = {TREE_B}", ""]
    for label in ("A", "B"):
        r = res[label]
        lines.append(f"----- tree {label} ({r['root']}) rc={r['rc']} -----")
        lines.append(r["stdout"].rstrip())
        if r["stderr_tail"].strip():
            lines.append(f"[stderr tail] {r['stderr_tail'].strip()[-500:]}")
        lines.append("")
    text = "\n".join(lines)
    print(text, flush=True)
    out = _LOCAL_ROOT / "results" / f"probe_modal_{tag}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n")
    print(f"wrote {out}", flush=True)
