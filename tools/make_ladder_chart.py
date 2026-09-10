#!/usr/bin/env python3
"""Render the public ladder-rating chart from docs/assets/ladder-rating.json.

Usage:  python3 tools/make_ladder_chart.py
Output: docs/assets/ladder-rating.png (+ .svg)

The data file is produced by parsing the event dashboard's rating graph
(gridline-calibrated SVG; anchors verified against our own records:
r95 = 1686 peak, r97 = 1588). This script is part of the public record:
it shows exactly how the chart in the README was made.
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "docs/assets/ladder-rating.json").read_text())
series, stats = DATA["series"], DATA.get("stats", {})

rounds = [s["round"] for s in series]
ratings = [s["rating"] for s in series]
results = [s["result"] for s in series]

COL = {"Win": "#16a34a", "Loss": "#dc2626", "Draw": "#94a3b8", "?": "#cbd5e1"}
r_first, r_last = rounds[0], rounds[-1]
peak_i = ratings.index(max(ratings))
lo, hi = min(ratings), max(ratings)

fig, ax = plt.subplots(figsize=(12, 6.6), dpi=200)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ylim_bottom, ylim_top = lo - 60, hi + 120
ax.set_ylim(ylim_bottom, ylim_top)
ax.set_xlim(r_first - 1.5, r_last + 1.5)

# engine-era shading (bands + labels at top, only where a band is wide enough)
eras = [
    (47.5, 60.5, "#eef2f7", "v1 / v2", "#64748b"),
    (60.5, 69.5, "#e8f0fe", "v3 / v4", "#3b82f6"),
    (69.5, 89.5, "#e9f7ef", "v5", "#15803d"),
    (89.5, 99.5, "#f3e8fd", "v6 / v7", "#9333ea"),
]
for x0, x1, color, label, tcol in eras:
    ax.axvspan(x0, x1, color=color, alpha=0.6, lw=0, zorder=0)
    if label:
        ax.text((x0 + x1) / 2, ylim_top - 24, label, ha="center", va="top",
                fontsize=8.5, color=tcol, weight="bold", zorder=6)

# rating line + soft fill
ax.fill_between(rounds, ratings, ylim_bottom, color="#1d4ed8", alpha=0.06, lw=0, zorder=1)
ax.plot(rounds, ratings, color="#1d4ed8", lw=2.0, zorder=3, solid_capstyle="round")

# result markers
for res in ("Win", "Draw", "Loss"):
    xs = [r for r, v in zip(rounds, results) if v == res]
    ys = [v for v, w in zip(ratings, results) if w == res]
    if xs:
        ax.scatter(xs, ys, s=34, c=COL[res], edgecolors="white", linewidths=0.7,
                   zorder=4, label={"Win": "win", "Draw": "draw", "Loss": "loss"}[res])

# annotations — short, non-crossing
ax.text(rounds[0] + 0.4, ratings[0] + 22, f"started {int(ratings[0])}",
        fontsize=9, color="#64748b", ha="left", va="bottom")
ax.text(rounds[peak_i] + 1.3, max(ratings) + 16, f"peak {int(max(ratings))}",
        fontsize=9.5, color="#334155", ha="left", va="bottom")

# axes cosmetics
ax.set_xlabel("rated round", fontsize=10, color="#334155")
ax.set_ylabel("ladder rating (Elo)", fontsize=10, color="#334155")
ax.grid(axis="y", color="#e2e8f0", lw=0.8, alpha=0.8)
ax.set_axisbelow(True)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color("#cbd5e1")
ax.tick_params(colors="#475569", labelsize=9)

ax.set_title("En Passant Labs at the AI Chessathon — ladder rating by round",
             fontsize=14.5, weight="bold", color="#0f172a", loc="left", pad=14)
ax.text(0, 1.015, f"{len(rounds)} rated rounds  ·  Sep 7–10 2026  ·  hourly engine-vs-engine ladder",
        transform=ax.transAxes, fontsize=9.5, color="#64748b")

handles = [Line2D([], [], color="#1d4ed8", lw=2, label="rating")]
handles += [Line2D([], [], marker="o", ls="", color=COL[k], label=v, markersize=6)
            for k, v in (("Win", "win"), ("Draw", "draw"), ("Loss", "loss"))]
ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.9,
          edgecolor="#e2e8f0", fontsize=9)

# stats block — figure top-right margin (outside the axes, nothing to collide with)
rank, teams = stats.get("rank"), stats.get("teams")
box = []
if rank:
    box.append(f"#{rank} of {teams} · top {stats.get('top_pct')}%")
if stats.get("record"):
    box.append(f"record {stats['record'].replace('-', '–')} since r{r_first}")
if stats.get("rating"):
    box.append(f"rating now {stats['rating']}")
if stats.get("peak"):
    box.append(f"peak {stats['peak']}  ·  {stats.get('checkmates', '?')} checkmate wins")
fig.text(0.985, 0.985, "\n".join(box), ha="right", va="top", fontsize=9.2,
         color="#0f172a", linespacing=1.45)

fig.text(0.012, 0.012,
         "Engine generations: v1/v2 minimal + stateful  ·  v3/v4  ·  v5 key-correctness (EP/rights fixes)  ·  v6 null-sign fix (r90)  ·  v7 night3 (r91+)  ·  v9k king-PST fix live from r100.\n"
         "Data: aichessathon.com event dashboard (rating graph parsed; anchors cross-checked against the match record). Chart: tools/make_ladder_chart.py.",
         fontsize=7.6, color="#64748b", ha="left", va="bottom")

fig.subplots_adjust(left=0.075, right=0.985, top=0.855, bottom=0.14)
out = ROOT / "docs/assets"
fig.savefig(out / "ladder-rating.png", facecolor="white")
fig.savefig(out / "ladder-rating.svg", facecolor="white")
print("saved:", out / "ladder-rating.png", "and .svg")
