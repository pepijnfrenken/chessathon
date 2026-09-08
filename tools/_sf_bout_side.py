"""Subprocess entry for run_vs_stockfish.py: imports agent + engine_side
(the latter lives in tools/, so a plain -c import fails from repo root).
Run: python tools/_sf_bout_side.py  (cwd = repo root)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo

import agent  # noqa: F401  (warmup + env)
import engine_side  # noqa: F401

engine_side.main()
