#!/usr/bin/env python3
"""q5-v8dp L2: compare two leak-probe outputs against the corpus + SF16.

  python tools/leak_compare.py <corpus.json> <tagA> <probeA> <tagB> <probeB>

Joins the two probe outputs on (game, ply) with the corpus rows and reports:

  - per-row: SF16 eval_before (our-side POV referee truth), both engines'
    searched score and chosen move, and the candidate-minus-control delta
  - summary: mean/median score delta, moves changed, rows where the
    candidate is >=300cp WORSE than the control (the regression class the
    leak gate looks for) and >=300cp better, plus each tree's mean/median
    |score - eval_before| deviation from referee truth

Mate-coded engine scores (|s| >= 29000) are reported as-is but excluded from
the mean/median deviation arithmetic (they are not cp-scale).
"""
import json
import statistics
import sys


def parse(path):
    """Key rows by (game, ply). Format: '<tag> <game> ply=N vloss=... ...';
    the first token is the tag and every following token is key=value, so
    the game name and every field are unambiguous (no space padding)."""
    out = {}
    for line in open(path):
        p = line.split()
        if not p or p[0].startswith("#"):
            continue
        # token 0 = tag, token 1 = game name (no '='), tokens 2.. = key=value
        if "=" in p[1] or len(p) < 3 or not p[2].startswith("ply="):
            continue
        d = {"tag": p[0], "game": p[1]}
        for kv in p[2:]:
            k, _, v = kv.partition("=")
            d[k] = v
        if "ply" not in d or "game" not in d:
            continue
        out[(d["game"], int(d["ply"]))] = d
    return out


def clean(s):
    return abs(s) < 29000


def main():
    corpus, ta, fa, tb, fb = sys.argv[1:6]
    rows = json.load(open(corpus))
    A, B = parse(fa), parse(fb)
    print(f"corpus={corpus} rows={len(rows)}  A={ta} ({len(A)} probed)  "
          f"B={tb} ({len(B)} probed)")
    print(f"{'game':30} {'ply':>4} {'sf16':>7} {ta+'_s':>8} {ta+'_mv':>6} "
          f"{tb+'_s':>8} {tb+'_mv':>6} {'dA-B':>7}")
    deltas, devA, devB, changed, worse300, better300 = [], [], [], 0, [], []
    for e in rows:
        k = (e["game"], e["ply"])
        a, b = A.get(k), B.get(k)
        if not a or not b:
            print(f"MISSING {k}")
            continue
        sa, sb, sf = int(a["score"]), int(b["score"]), int(e["eval_before"])
        d = sa - sb
        deltas.append(d)
        if (clean(sa), clean(sb)) == (True, True):
            devA.append(abs(sa - sf))
            devB.append(abs(sb - sf))
        mv_changed = a["best"] != b["best"]
        changed += mv_changed
        if d <= -300:
            worse300.append((k, sf, sb, sa))
        if d >= 300:
            better300.append((k, sf, sb, sa))
        print(f"{e['game'][:30]:30} {e['ply']:4d} {sf:7d} {sa:8d} "
              f"{a['best']:>6} {sb:8d} {b['best']:>6} {d:7d}"
              f"{'  MV!' if mv_changed else ''}")
    print()
    print(f"rows compared        : {len(deltas)}")
    print(f"mean score delta A-B : {statistics.mean(deltas):+.1f} cp")
    print(f"median score delta   : {statistics.median(deltas):+.1f} cp")
    print(f"moves changed        : {changed}")
    print(f"A >=300cp WORSE rows : {len(worse300)}")
    for k, sf, sb, sa in worse300:
        print(f"   {k} sf16={sf} B={sb} A={sa}")
    print(f"A >=300cp better rows: {len(better300)}")
    for k, sf, sb, sa in better300:
        print(f"   {k} sf16={sf} B={sb} A={sa}")
    if devA:
        print(f"mean |score-SF16|    : A={statistics.mean(devA):.0f} cp "
              f"B={statistics.mean(devB):.0f} cp (n={len(devA)} cp-scale rows)")
        print(f"median |score-SF16|  : A={statistics.median(devA):.0f} cp "
              f"B={statistics.median(devB):.0f} cp")


if __name__ == "__main__":
    main()
