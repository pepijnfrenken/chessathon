#!/usr/bin/env python3
"""Fetch ladder game PGNs + agent logs from the aichessathon dashboard (ADD-ONLY).

I/O conventions (learned the hard way — see PROCESS.md §13, Sep 10 incident):
  * ADD-ONLY round files: an existing round-NN-vs-*.pgn / .log is never
    rewritten, so in-flight readers (replays, leak tooling) never see files
    change under them. Use --force to deliberately re-fetch a round.
  * games.csv IS refreshed every run (it is a metadata snapshot used for
    machine/timestamp attribution only — NEVER for OUR colour; derive side
    from the PGN headers).
  * PGN payloads are cut at the game result: the HTML capture can append a
    few junk characters after the result token; strip everything after it.
  * Fail loudly when the metadata CSV parse yields zero rows, instead of
    writing '-vs-unknown' files (Sep 9 incident: a full re-fetch produced
    43 unknown-named duplicates of already-committed round files).

Usage: python3 tools/fetch_dashboard.py [--force] [--dry-run]
"""
import csv
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "matches"
META = ROOT / "results" / "dashboard"
COOKIE = Path.home() / ".hermes" / "creds" / "aichessathon-cookie.txt"

# game result token at the end of the (captured) PGN, possibly + trailing junk
RESULT_RE = re.compile(r"(1-0|0-1|1/2-1/2|\*)([^\s(]{0,8})\s*$")


def get(url):
    req = urllib.request.Request(url, headers={
        "Cookie": COOKIE.read_text().strip(),
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    return urllib.request.urlopen(req, timeout=60).read()


def clean_pgn(txt):
    """Cut capture junk after the game result token (site serves clean PGNs)."""
    txt = txt.rstrip()
    m = RESULT_RE.search(txt)
    if m and m.group(2):
        txt = txt[:m.start()] + m.group(1)
    return txt


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    META.mkdir(parents=True, exist_ok=True)

    html = get("https://aichessathon.com/dashboard").decode("utf-8", "replace")
    rows = []
    for m in re.finditer(r"Rated (\d+)", html):
        rows.append([int(m.group(1)), m.end()])
    out_rows = []
    for i, (rnd, end) in enumerate(rows):
        slice_end = rows[i + 1][1] if i + 1 < len(rows) else len(html)
        seg = html[end:slice_end]
        pg = re.search(r"data:application/x-chess-pgn;charset=utf-8,([^\"]+)", seg)
        lg = re.search(r"/api/platform/logs/([0-9a-f-]{36})", seg)
        out_rows.append({"round": rnd,
                         "pgn_uri": pg.group(1) if pg else None,
                         "log_id": lg.group(1) if lg else None})

    csv_raw = get("https://aichessathon.com/api/platform/logs/export").decode()
    meta = {}
    for row in csv.DictReader(csv_raw.splitlines()):
        m = re.match(r"Rated (\d+)", row.get("round", ""))
        if m:
            meta[int(m.group(1))] = row
    if not meta:
        sys.exit("FATAL: metadata CSV parse returned 0 rows — refusing to write "
                 "unknown-named files (check the export endpoint / cookie).")
    if not dry:
        (META / "games.csv").write_text(csv_raw)

    skipped, written, missing = [], [], []
    for r in out_rows:
        md = meta.get(r["round"], {})
        opp = md.get("opponent", "unknown")
        fname = OUT / f"round-{r['round']:02d}-vs-{slug(opp)}.pgn"
        if r["pgn_uri"]:
            if fname.exists() and fname.stat().st_size > 0 and not force:
                skipped.append(fname.name)
            elif not dry:
                fname.write_text(clean_pgn(urllib.parse.unquote(r["pgn_uri"])))
                written.append(fname.name)
        else:
            missing.append(f"r{r['round']} pgn")
        if r["log_id"]:
            lname = OUT / f"round-{r['round']:02d}-vs-{slug(opp)}.log"
            if lname.exists() and lname.stat().st_size > 0 and not force:
                skipped.append(lname.name)
            elif not dry:
                try:
                    lname.write_bytes(get(
                        f"https://aichessathon.com/api/platform/logs/{r['log_id']}"))
                    written.append(lname.name)
                except Exception as e:
                    missing.append(f"r{r['round']} log ({e})")

    print(f"rows parsed: {len(out_rows)} | meta rows: {len(meta)}")
    print(f"written: {len(written)} | skipped (exist): {len(skipped)} | missing: {missing}")
    for w in written:
        print("  +", w)
    for s in skipped[:8]:
        print("  = (skip)", s)
    if len(skipped) > 8:
        print(f"  = (skip) ... and {len(skipped) - 8} more")


if __name__ == "__main__":
    main()
