#!/usr/bin/env python3
"""Parse every rated-round PGN (+ CSV/log cross-check) into per-game records.

Output: docs/assets/ladder-games.json

Per game: round, date, opponent, our colour, result, termination,
start move, total plies, final move number (game length in moves),
our move count, duration. Cross-checks PGN-vs-CSV-vs-log move counts.
"""
import csv
import datetime
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MATCHES = ROOT / "results/matches"
CSV = ROOT / "results/dashboard/games.csv"
OUT = ROOT / "docs/assets/ladder-games.json"

NUM_RE = re.compile(r"^(\d+)\.+$")
NUM_ATTACHED_RE = re.compile(r"^(\d+)\.+(\S+)$")
SAN_RE = re.compile(
    r"^(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?|O-O-O|O-O)[+#]?$"
)
RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}
US = "En Passant Labs"


def parse_pgn(text: str) -> dict:
    head, _, body = text.partition("\n\n") if "\n\n" in text else (text, "", "")
    if not body:
        # some files use \r\n
        head, _, body = text.partition("\r\n\r\n")
    headers = dict(re.findall(r'\[(\w+)\s+"(.*?)"\]', head))
    # strip comments { ... }
    mt = re.sub(r"\{[^}]*\}", " ", body)
    tokens = mt.split()
    plies = 0
    last_mover = None  # 'w' or 'b'
    last_move_number = None
    unmatched = []
    for tok in tokens:
        m = NUM_RE.match(tok)
        if m:
            # number token carries mover colour via dot-count: 1. => white, 1... => black
            last_move_number = int(m.group(1))
            last_mover = "b" if "..." in tok else "w"
            continue
        m2 = NUM_ATTACHED_RE.match(tok)
        if m2 and tok.count(".") >= 1 and SAN_RE.match(m2.group(2)):
            last_move_number = int(m2.group(1))
            last_mover = "b" if "..." in tok else "w"
            plies += 1
            continue
        if tok in RESULT_TOKENS:
            continue
        if SAN_RE.match(tok):
            plies += 1
            continue
        unmatched.append(tok)

    fen = headers.get("FEN", "")
    parts = fen.split()
    start_fullmove = int(parts[5]) if len(parts) >= 6 else 1
    side_to_move = parts[1] if len(parts) >= 2 else "w"

    our_color = "w" if headers.get("White") == US else "b"

    # result from our perspective
    r = headers.get("Result", "*")
    if r == "1/2-1/2":
        result = "Draw"
    elif (r == "1-0" and our_color == "w") or (r == "0-1" and our_color == "b"):
        result = "Win"
    elif r == "*":
        result = "?"
    else:
        result = "Loss"

    # count our moves: alternate from side_to_move
    first_mover = side_to_move
    our_moves = 0
    mover = first_mover
    # recompute over the surviving SAN tokens in order
    movers = []
    for tok in tokens:
        m = NUM_RE.match(tok)
        if m:
            mover = "b" if "..." in tok else "w"
            continue
        m2 = NUM_ATTACHED_RE.match(tok)
        if m2 and SAN_RE.match(m2.group(2)):
            mover = "b" if "..." in tok else "w"
            movers.append(mover)
            continue
        if tok in RESULT_TOKENS:
            continue
        if SAN_RE.match(tok):
            movers.append(mover)

    our_moves = sum(1 for c in movers if c == our_color)

    return {
        "round": int(headers.get("Round", 0)),
        "date": headers.get("Date", ""),
        "opponent": headers.get("Black") if our_color == "w" else headers.get("White"),
        "color": our_color,
        "result": result,
        "termination": (headers.get("Termination", "") or "").strip().lower(),
        "start_move": start_fullmove,
        "pre_played": start_fullmove - 1,
        "plies": plies,
        "last_move_number": last_move_number,
        "last_mover": last_mover,
        "our_moves": our_moves,
        "unmatched": unmatched[:5],
    }


def main():
    games = []
    for pgn in sorted(MATCHES.glob("*.pgn")):
        rec = parse_pgn(pgn.read_text())
        rec["file"] = pgn.name
        games.append(rec)

    games.sort(key=lambda g: g["round"])

    # cross-check vs CSV
    csv_rows = {}
    with CSV.open() as f:
        for row in csv.DictReader(f):
            rnd = int(row["round"].split()[-1])
            csv_rows[rnd] = row

    problems = []
    for g in games:
        row = csv_rows.get(g["round"])
        if not row:
            problems.append(f"r{g['round']}: no CSV row")
            continue
        g["csv_moves"] = int(row["moves"])
        g["csv_result"] = row["result"]
        g["csv_termination"] = row["termination"]
        g["duration_s"] = None
        log = MATCHES / (g["file"].replace(".pgn", ".log"))
        if log.exists():
            lt = log.read_text()
            m = re.search(r"Game lasted\s+([\d.]+)\s*s", lt)
            if m:
                g["duration_s"] = float(m.group(1))
            m2 = re.search(r"\n\s*Moves\s+(\d+)", lt)
            if m2:
                g["log_moves"] = int(m2.group(1))
        if g["csv_result"] != g["result"]:
            problems.append(f"r{g['round']}: result pgn={g['result']} csv={g['csv_result']}")
        norm_term = g["termination"].replace("_", " ")
        if norm_term and norm_term != g["csv_termination"].lower().replace("_", " "):
            if not (norm_term == "checkmate" and "checkmate" in g["csv_termination"].lower()):
                problems.append(
                    f"r{g['round']}: term pgn={g['termination']} csv={g['csv_termination']}"
                )
        if g.get("log_moves") is not None and g["our_moves"] != g["log_moves"]:
            problems.append(
                f"r{g['round']}: our_moves pgn={g['our_moves']} log={g.get('log_moves')}"
            )
        if g["unmatched"]:
            problems.append(f"r{g['round']}: unmatched tokens {g['unmatched']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated": datetime.datetime.utcnow().isoformat() + "Z",
                "source": "results/matches/*.pgn + results/dashboard/games.csv",
                "games": games,
            },
            indent=1,
        )
    )

    print(f"games: {len(games)}")
    print(
        f"{'rnd':>4} {'res':<5} {'col':<2} {'term':<22} {'start':>5} {'plies':>5} "
        f"{'lastN':>5} {'our':>3} {'csv':>3} {'dur_s':>7}"
    )
    for g in games:
        print(
            f"{g['round']:>4} {g['result']:<5} {g['color']:<2} {g['termination']:<22} "
            f"{g['start_move']:>5} {g['plies']:>5} {g['last_move_number']:>5} "
            f"{g['our_moves']:>3} {g['csv_moves']:>3} "
            f"{(g['duration_s'] if g['duration_s'] is not None else -1):>7}"
        )
    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
    else:
        print("no cross-check problems")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
