#!/usr/bin/env python3
"""Parse the aichessathon dashboard rating graph into docs/assets/ladder-rating.json.

The dashboard's rating SVG carries, for every rated round, a tooltip with the
exact published rating (``R<n>`` = rating after round n). We read those values
directly — no pixel calibration — and cross-check the whole series against our
own match records (results/matches) and the dashboard's stats block.

Usage:
    python3 tools/parse_ladder_rating.py [capture.html]
Default: newest results/dashboard/dashboard-*.html capture.

Output: docs/assets/ladder-rating.json
"""
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAMES = ROOT / "docs/assets/ladder-games.json"
OUT = ROOT / "docs/assets/ladder-rating.json"
DASH = ROOT / "results/dashboard"


def newest_capture() -> pathlib.Path:
    caps = sorted(DASH.glob("dashboard-*.html"))
    if not caps:
        sys.exit("no results/dashboard/dashboard-*.html capture found — pass one explicitly")
    return caps[-1]


def parse_tooltips(html: str) -> dict:
    """{round: rating} from the rating SVG's per-point tooltips."""
    m = re.search(r'aria-label="Rating by round[^>]*>(.*?)</svg>', html, re.S)
    if not m:
        sys.exit("rating SVG not found in capture")
    svg = m.group(1)
    series = {}
    for tm in re.finditer(
        r'class="rg-tip-text"[^>]*>R(?:<!-- -->)?(\d+)<tspan[^>]*>(\d+)</tspan>', svg
    ):
        series[int(tm.group(1))] = int(tm.group(2))
    if not series:
        sys.exit("no tooltip points parsed from rating SVG")
    return dict(sorted(series.items()))


def parse_stats(html: str, want_record: str) -> dict:
    """Stats block from the team-facts panel; prefers the block whose record
    matches our own data (the page can embed a stale copy)."""
    blocks = []
    for m in re.finditer(r'team-facts.{0,4000}?</dl>', html, re.S):
        seg = m.group(0)
        facts = {}
        for dt, dd in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", seg, re.S):
            dd = re.sub(r"<!--.*?-->", "", dd)
            dd = re.sub(r"<[^>]+>", " ", dd)
            facts[dt.strip()] = re.sub(r"\s+", " ", dd).strip()
        if "Record" in facts:
            blocks.append(facts)
    if not blocks:
        sys.exit("no team-facts stats block found in capture")

    def to_stats(f: dict) -> dict:
        s = {}
        m = re.match(r"#\s*(\d+)\s*of\s*(\d+)\s*·\s*top\s*(\d+)%", f.get("Rank", ""))
        if m:
            s["rank"], s["teams"], s["top_pct"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.match(r"(\d+)\s*peak\s*(\d+)", f.get("Rating", ""))
        if m:
            s["rating"], s["peak"] = int(m.group(1)), int(m.group(2))
        if f.get("Record"):
            s["record"] = f["Record"]
        m = re.match(r"(\d+)", f.get("Checkmates", ""))
        if m:
            s["checkmates"] = int(m.group(1))
        m = re.match(r"(\d+)", f.get("Best streak", ""))
        if m:
            s["best_streak"] = int(m.group(1))
        return s

    for f in blocks:
        s = to_stats(f)
        if s.get("record") == want_record:
            return s
    return to_stats(blocks[0])


def main() -> None:
    capture = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else newest_capture()
    html = capture.read_text(encoding="utf-8", errors="replace")

    series = parse_tooltips(html)
    games = json.loads(GAMES.read_text())["games"]
    games_by_round = {g["round"]: g for g in games}

    # record cross-check
    w = sum(1 for g in games if g["result"] == "Win")
    d = sum(1 for g in games if g["result"] == "Draw")
    l = sum(1 for g in games if g["result"] == "Loss")
    rec = f"{w}-{d}-{l}"

    rounds = sorted(series)
    if rounds != sorted(games_by_round):
        print(f"WARNING: tooltip rounds {rounds[0]}..{rounds[-1]} ({len(rounds)}) != "
              f"games rounds {min(games_by_round)}..{max(games_by_round)} ({len(games_by_round)})")

    stats = parse_stats(html, rec)

    # derived cross-checks against the parsed series
    peak_round = max(series, key=lambda r: series[r])
    last_round = rounds[-1]
    checks = [
        ("record", stats.get("record"), rec),
        ("rating (last round)", stats.get("rating"), series[last_round]),
        ("peak", stats.get("peak"), series[peak_round]),
    ]
    alerts = []
    for name, from_stats, computed in checks:
        if from_stats != computed:
            alerts.append(f"  ! {name}: stats={from_stats} computed={computed}")

    out_series = []
    for r in rounds:
        g = games_by_round.get(r, {})
        point = {
            "round": r,
            "rating": series[r],
            "kind": "end" if r == last_round else "marker",
        }
        if g:
            point["result"] = g["result"]
            point["opponent"] = g["opponent"]
            point["colour"] = "White" if g["color"] == "w" else "Black"
        out_series.append(point)

    payload = {
        "source": "aichessathon.com/dashboard rating graph (tooltip-exact per-round ratings)",
        "source_file": capture.name,
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "calibration": "tooltip-exact (R<n> labels in the rating SVG); no pixel estimation",
        "stats": stats,
        "series": out_series,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {OUT}")
    print(f"  rounds {rounds[0]}..{last_round} ({len(rounds)}) | stats: {json.dumps(stats)}")
    print(f"  peak {series[peak_round]} @ r{peak_round} | last {series[last_round]} @ r{last_round}")
    if alerts:
        print("CROSS-CHECK ALERTS:")
        print("\n".join(alerts))
    else:
        print("  cross-checks: record / rating / peak all consistent with stats block")


if __name__ == "__main__":
    main()
