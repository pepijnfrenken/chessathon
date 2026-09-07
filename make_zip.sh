#!/usr/bin/env bash
# Assemble the Chessathon submission zip.
#
# The zip must contain EXACTLY agent.py at the zip root — nothing else:
# no docs, no tools/, no tests, no .git, no __pycache__. Then verify the
# artifact: list contents and import get_move from an unrelated cwd the
# way the competition box would.
#
# Usage: ./make_zip.sh   (run from the repo root)
set -euo pipefail
cd "$(dirname "$0")"

ZIP="agent.zip"
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT

echo "== cleaning stale artifact =="
rm -f "$ZIP"

echo "== building $ZIP (agent.py only) =="
python3 -m zipfile -c "$ZIP" agent.py

echo "== contents =="
python3 -m zipfile -l "$ZIP"

echo "== import+move test from /tmp (simulated box) =="
PY="${PYTHON:-python3}"
(
  cd /tmp
  "$PY" - <<'PY'
import sys
sys.path.insert(0, "/home/pino/projects/chessathon/agent.zip")
from agent import get_move
m = get_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 120000)
import chess
assert m != "0000" and chess.Move.from_uci(m) in chess.Board().legal_moves, m
print("zip agent returned legal move:", m)
PY
)

echo "== size =="
ls -l "$ZIP" | awk '{print $5 " bytes  " $9}'
echo "make_zip OK"