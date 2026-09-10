"""Modal fan-out for SF19 game reviews (dev tool, NOT shipped).

Same review as tools/review_sf.py (SF19 referee, depth default 16,
brilliant..blunder buckets) but run in a Modal container with the SF19
binary baked into the image — so ladder-round reviews never compete with
gates/bouts for the 6-core box, and multiple rounds can be reviewed in
parallel.

The repo's results/ is NOT shipped into the image; the PGN is passed as
text and the JSON review comes back as the return value, written locally
to results/leak_reviews/<pgn-stem>.sf16.json (the same path the local
tool writes).

Usage (from the repo root):
  modal run tools/modal_review.py --pgn results/matches/round-97-vs-tempo.pgn \
      --side white --depth 16 --tag r97
"""

import json
import os
from pathlib import Path

import modal

_LOCAL_ROOT = Path(__file__).resolve().parent.parent
SF_LOCAL = Path.home() / ".local/bin/stockfish"

app = modal.App("chessathon-review")


def _ignore(path: Path) -> bool:
    parts = set(path.parts)
    junk = {".git", "__pycache__", ".venv", "venv", "node_modules",
            "docs", "data", "tmp", "sessions", ".aiwg", "results"}
    return bool(parts & junk) or path.suffix in {".pyc", ".zip"}


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("chess")
    .add_local_dir(str(_LOCAL_ROOT), remote_path="/repo", ignore=_ignore,
                   copy=True)
    .add_local_file(str(SF_LOCAL), remote_path="/root/.local/bin/stockfish",
                    copy=True)
    .run_commands("chmod +x /root/.local/bin/stockfish")
)


@app.function(image=image, cpu=2.0, memory=2048, timeout=1800)
def review(spec: dict) -> dict:
    import subprocess
    import sys

    pgn_text = spec["pgn_text"]
    pgn_path = f"/tmp/{spec['pgn_name']}"
    Path(pgn_path).write_text(pgn_text)
    out_json = f"/tmp/{spec['tag']}.sf16.json"
    cmd = [sys.executable, "/repo/tools/review_sf.py", pgn_path,
           "--depth", str(spec["depth"]), "--json", out_json]
    if spec.get("side"):
        cmd += ["--side", spec["side"]]
    p = subprocess.run(cmd, cwd="/repo", capture_output=True, text=True,
                       timeout=1500)
    data = None
    try:
        data = Path(out_json).read_text()
    except Exception:
        pass
    return {"rc": p.returncode, "stdout_tail": p.stdout[-4000:],
            "stderr_tail": p.stderr[-2000:], "json_text": data}


@app.local_entrypoint()
def main(pgn: str, side: str = "", depth: int = 16, tag: str = "review"):
    pgn_text = (_LOCAL_ROOT / pgn).read_text()
    res = review.remote({"pgn_text": pgn_text, "pgn_name": Path(pgn).name,
                         "depth": depth, "side": side or None, "tag": tag})
    print(f"# modal review rc={res['rc']}")
    print(res["stdout_tail"])
    if res["stderr_tail"].strip():
        print("[stderr]", res["stderr_tail"][-800:])
    if res["json_text"]:
        out = _LOCAL_ROOT / "results" / "leak_reviews" / f"{tag}.sf16.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(res["json_text"])
        n = len(json.loads(res["json_text"]))
        print(f"wrote {out} ({n} rows)")
    else:
        print("!! no JSON produced")
