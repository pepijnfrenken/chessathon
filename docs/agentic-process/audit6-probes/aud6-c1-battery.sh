#!/bin/bash
# aud6 C1 battery: wait for the builder's gate/flag to clear, then run the PST
# rank-orientation A/B (shipped / +K / +KBR). ONE engine process at a time.
# Re-checks the flag BETWEEN variants and aborts cleanly if it reappears, so
# this can never co-load the orchestrator's bout.
set -u
LOG=/tmp/aud6-c1-battery.log
: > "$LOG"
echo "battery started $(date -u +%H:%M:%S)" >> "$LOG"

busy () { [ -e /tmp/chessathon-v8dp-gate.flag ] || pgrep -f "[g]ate_match|[b]out_ladder|[e]ngine_side_clk" >/dev/null; }

# --- wait for the box ---
while busy; do sleep 20; done
echo "box FREE at $(date -u +%H:%M:%S); starting runs" >> "$LOG"
sleep 5

run_variant () {
  local V="$1" NC="/tmp/aud6-np10-${1:-off}"
  local OUT="/tmp/aud6-c1-${1:-shipped}.txt"
  if busy; then echo "ABORT before ${V}: box busy again $(date -u +%H:%M:%S)" >> "$LOG"; return 1; fi
  echo "=== variant '${V}' start $(date -u +%H:%M:%S)" >> "$LOG"
  CHESSATHON_PSTFLIP="$V" TREE=/tmp/aud6-scratch-pstfix NC="$NC" CORPUS_MS=1200 \
    PYTHONDONTWRITEBYTECODE=1 /tmp/chessbench/bin/python /tmp/aud6-probe10.py \
    > "$OUT" 2>&1
  echo "=== variant '${V}' done rc=$? $(date -u +%H:%M:%S) -> $OUT" >> "$LOG"
}

run_variant ""    || exit 0
run_variant "K"   || exit 0
run_variant "KBR" || exit 0
echo "BATTERY DONE $(date -u +%H:%M:%S)" >> "$LOG"
