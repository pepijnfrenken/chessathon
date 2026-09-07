#!/usr/bin/env bash
# Assemble the Chessathon submission zip.
#
# The zip contains EXACTLY agent.py + engine/*.py at the zip root —
# nothing else: no docs, no tools/, no tests, no .git, no __pycache__.
# Then verify the artifact: import get_move from an unrelated cwd the way
# the competition box would, and measure import+JIT warmup (must fit the
# 60 s init budget).
#
# Usage: ./make_zip.sh   (run from the repo root)
set -euo pipefail
cd "$(dirname "$0")"

ZIP="agent.zip"
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT
PY="${PYTHON:-/tmp/chessbench/bin/python}"

echo "== cleaning stale artifact =="
rm -f "$ZIP"
find engine -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "== building $ZIP (agent.py + engine/) =="
python3 -m zipfile -c "$ZIP" agent.py engine

echo "== contents =="
python3 -m zipfile -l "$ZIP"

echo "== import+JIT warmup timing (60s budget) from /tmp =="
(
  cd /tmp
  PYTHONPATH= "$PY" - <<PY
import sys, time
sys.path.insert(0, "/home/pino/projects/chessathon/agent.zip")
t0 = time.time()
import chess
from agent import get_move
t_import = time.time() - t0
t0 = time.time()
m = get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 120000)
t_move = time.time() - t0
assert t_import + t_move < 60, f"init {t_import+t_move:.1f}s exceeds 60s"
assert m != "0000" and chess.Move.from_uci(m) in chess.Board().legal_moves, m
print(f"init (import+JIT): {t_import:.1f}s | first move: {t_move:.2f}s | legal: {m}")
PY
)

echo "== size =="
ls -l "$ZIP" | awk '{print $5 " bytes  " $9}'
echo "make_zip OK"