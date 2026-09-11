#!/usr/bin/env bash
# Refresh the full ladder record: fetch new rounds -> rebuild data -> redraw charts.
#
# Usage:  tools/refresh_ladder.sh
# Then:   review `git diff`, commit.
#
# Safe to run any time; the fetcher is additive (existing round files are never
# rewritten) and every step is deterministic from the fetched record.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/5 fetch dashboard rounds (add-only) =="
python3 tools/fetch_dashboard.py

echo "== 2/5 rebuild per-game records (ladder-games.json) =="
python3 tools/parse_game_lengths.py | tail -4

echo "== 3/5 rebuild rating series (ladder-rating.json) =="
python3 tools/parse_ladder_rating.py

echo "== 4/5 redraw rating chart =="
python3 tools/make_ladder_chart.py

echo "== 5/5 redraw game-length chart =="
python3 tools/make_games_chart.py

echo
echo "done — check 'git status' / 'git diff', then commit:"
echo "  git add -A && git commit -m '[record] ladder refresh: <rounds> ...'"
