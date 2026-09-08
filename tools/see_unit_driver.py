#!/usr/bin/env python3
"""Driver for see_unit.py: one fresh subprocess per case (this sandbox's
numba dispatch can stall intermittently on repeated in-process calls in a
single process — subprocess isolation makes the battery deterministic).
Retries each case once on timeout. Exit 0 iff all cases pass.
"""
import subprocess
import sys
import time
from pathlib import Path

import see_unit as U

PY = sys.executable
HERE = Path(__file__).resolve().parent

labels = [c[0] for c in U.CASES]
bad = 0
for label in labels:
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                [PY, str(HERE / "see_unit.py"), label],
                capture_output=True, text=True, timeout=240)
            out = (r.stdout + r.stderr).strip().splitlines()
            line = next((l for l in out if label in l), "no-line")
            print(f"{'attempt%d' % attempt} {line} "
                  f"(exit={r.returncode} {time.perf_counter()-t0:.0f}s)",
                  flush=True)
            if r.returncode == 0 and "FAIL" not in line:
                break
            bad += 1
        except subprocess.TimeoutExpired:
            print(f"attempt{attempt} {label} TIMEOUT", flush=True)
            bad += 1
    else:
        continue
    continue

print(f"\n== result: {'ALL PASS' if bad == 0 else f'{bad} FAILURES'}")
sys.exit(0 if bad == 0 else 1)