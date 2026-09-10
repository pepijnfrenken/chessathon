#!/usr/bin/env python3
"""Render the public game-length chart from docs/assets/ladder-games.json.

Usage:  python3 tools/make_games_chart.py
Output: docs/assets/ladder-games.png (+ .svg)

Panel A: every rated game — game length (move the game ended on) by round,
coloured by result, engine-generation bands, wins rolling median.
Panel B: outcome mix (wins·draws·losses) by game-length bucket x engine
generation — the "moves to win, and how it evolved" heatmap.
"""
import json
import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import ticker

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "docs/assets/ladder-games.json").read_text())
games = DATA["games"]

COL = {"Win": "#16a34a", "Draw": "#94a3b8", "Loss": "#dc2626"}

ERAS = ["v1 / v2", "v3 / v4", "v5", "v6 / v7"]
ERA_RANGE = {"v1 / v2": (47.5, 60.5), "v3 / v4": (60.5, 69.5),
             "v5": (69.5, 89.5), "v6 / v7": (89.5, 99.5)}
ERA_COL = {"v1 / v2": "#64748b", "v3 / v4": "#3b82f6",
           "v5": "#15803d", "v6 / v7": "#9333ea"}
ERA_BG = {"v1 / v2": "#eef2f7", "v3 / v4": "#e8f0fe",
          "v5": "#e9f7ef", "v6 / v7": "#f3e8fd"}


def era_of(r):
    if r <= 60:
        return "v1 / v2"
    if r <= 69:
        return "v3 / v4"
    if r <= 89:
        return "v5"
    return "v6 / v7"


fig = plt.figure(figsize=(12.5, 9.0), dpi=200)
gs = fig.add_gridspec(2, 1, height_ratios=[2.15, 1.0], hspace=0.30,
                      left=0.075, right=0.985, top=0.885, bottom=0.135)
axA = fig.add_subplot(gs[0])
axB = fig.add_subplot(gs[1])

# ---------------- Panel A: game length by round ----------------
axA.set_xlim(47.5, 99.5)
axA.set_ylim(4, 134)

for er in ERAS:
    x0, x1 = ERA_RANGE[er]
    axA.axvspan(x0, x1, color=ERA_BG[er], alpha=0.75, lw=0, zorder=0)
    axA.text((x0 + x1) / 2, 132, er, ha="center", va="top", fontsize=8.5,
             color=ERA_COL[er], weight="bold", zorder=6)

for res in ("Win", "Draw", "Loss"):
    pts = [g for g in games if g["result"] == res]
    axA.scatter([g["round"] for g in pts], [g["last_move_number"] for g in pts],
                s=40, c=COL[res], edgecolors="white", linewidths=0.7, zorder=4,
                label={"Win": "win", "Draw": "draw", "Loss": "loss"}[res])

wins = sorted([g for g in games if g["result"] == "Win"], key=lambda g: g["round"])
xs, ys = [], []
for i in range(len(wins)):
    chunk = wins[max(0, i - 6):i + 1]
    if len(chunk) >= 4:
        xs.append(wins[i]["round"])
        ys.append(float(np.median([c["last_move_number"] for c in chunk])))
axA.plot(xs, ys, color="#15803d", lw=1.6, ls=(0, (4, 2)), alpha=0.9, zorder=5,
         label="wins: rolling median (last 7)")

ann = [
    (79, 16, "fastest mate (16)", (64.5, 7.5)),
    (87, 111, "longest win (111)", (90.5, 117)),
    (64, 119, "longest game (119, loss)", (48.5, 124)),
]
for x, y, txt, (tx, ty) in ann:
    axA.annotate(txt, xy=(x, y), xytext=(tx, ty), fontsize=8.6, color="#334155",
                 arrowprops=dict(arrowstyle="-", color="#94a3b8", lw=0.9), zorder=7)

axA.grid(axis="y", color="#e2e8f0", lw=0.8, alpha=0.8)
axA.set_axisbelow(True)
for side in ("top", "right"):
    axA.spines[side].set_visible(False)
for side in ("left", "bottom"):
    axA.spines[side].set_color("#cbd5e1")
axA.tick_params(colors="#475569", labelsize=9)
axA.yaxis.set_major_locator(ticker.MultipleLocator(20))
axA.xaxis.set_major_locator(ticker.MultipleLocator(5))
axA.set_ylabel("game length (full moves played)", fontsize=10, color="#334155")
axA.set_xlabel("rated round", fontsize=10, color="#334155")
axA.legend(loc="lower right", frameon=True, framealpha=0.9, edgecolor="#e2e8f0",
           fontsize=9, ncol=2)

# ---------------- Panel B: heatmap era x length bucket ----------------
BUCKETS = [(">90", 91, 999), ("71–90", 71, 90), ("56–70", 56, 70),
           ("41–55", 41, 55), ("26–40", 26, 40), ("≤25", 0, 25)]

mat = np.zeros((len(BUCKETS), len(ERAS)))
texts = [["" for _ in ERAS] for _ in BUCKETS]
for bi, (lab, lo, hi) in enumerate(BUCKETS):
    for ei, er in enumerate(ERAS):
        sel = [g for g in games if era_of(g["round"]) == er
               and lo <= g["last_move_number"] <= hi]
        if sel:
            w = sum(1 for g in sel if g["result"] == "Win")
            d = sum(1 for g in sel if g["result"] == "Draw")
            l = sum(1 for g in sel if g["result"] == "Loss")
            mat[bi, ei] = w + d + l
            texts[bi][ei] = f"{w}·{d}·{l}"

vmax = max(1.0, mat.max())
im = axB.imshow(mat, cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
for bi in range(len(BUCKETS)):
    for ei in range(len(ERAS)):
        if texts[bi][ei]:
            shade = mat[bi, ei] / vmax
            axB.text(ei, bi, texts[bi][ei], ha="center", va="center",
                     fontsize=10, color="white" if shade > 0.62 else "#0f172a",
                     weight="bold")
axB.set_xticks(range(len(ERAS)), ERAS)
for tick, er in zip(axB.get_xticklabels(), ERAS):
    tick.set_color(ERA_COL[er])
    tick.set_fontweight("bold")
    tick.set_fontsize(9.5)
axB.set_yticks(range(len(BUCKETS)), [b[0] for b in BUCKETS])
axB.tick_params(colors="#475569", labelsize=9)
axB.set_ylabel("game length (moves)", fontsize=10, color="#334155")
axB.set_xticks(np.arange(-0.5, len(ERAS), 1), minor=True)
axB.set_yticks(np.arange(-0.5, len(BUCKETS), 1), minor=True)
axB.grid(which="minor", color="white", linewidth=2.2)
axB.tick_params(which="minor", bottom=False, left=False)
cb = fig.colorbar(im, ax=axB, fraction=0.022, pad=0.012)
cb.ax.tick_params(labelsize=8, colors="#475569")
cb.set_label("games in cell", fontsize=8.5, color="#475569")
cb.outline.set_edgecolor("#e2e8f0")
axB.set_title("Outcome mix by length and engine generation — cell text = wins·draws·losses, shade = games",
              fontsize=9.5, color="#334155", loc="left", pad=8)

# ---------------- titles / footer ----------------
fig.suptitle("En Passant Labs at the AI Chessathon — how games ended, round by round",
             x=0.075, ha="left", fontsize=14.5, weight="bold", color="#0f172a", y=0.972)
fig.text(0.075, 0.933,
         "52 rated games · Sep 7–10 2026 · green = win, grey = draw, red = loss · shaded bands = engine generation",
         fontsize=9.8, color="#64748b")

fig.text(0.012, 0.012,
         "Length = the full-move number at which the game finished (games start from a fixed 4–9-move opening prefix, competition format). All 25 wins were checkmates; draws were threefold repetition or insufficient material.\n"
         "Generations: v1/v2 r48–60 · v3/v4 r61–69 · v5 r70–89 · v6/v7 r90–99 (v9k live from r100, beyond this chart). Move counts cross-checked 52/52 against the platform export. Chart: tools/make_games_chart.py.",
         fontsize=7.6, color="#64748b", ha="left", va="bottom")

out = ROOT / "docs/assets"
fig.savefig(out / "ladder-games.png", facecolor="white")
fig.savefig(out / "ladder-games.svg", facecolor="white")
print("saved:", out / "ladder-games.png", "and .svg")
