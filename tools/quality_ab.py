#!/usr/bin/env python3
"""quality_ab.py — local pre-upload quality A/B: candidate build vs shipped V5.

Scores both builds' moves on REAL ladder games with an independent referee
(SF19, brilliant..blunder buckets) to answer "is the candidate locally
better before we upload it?" — real-clock evidence, no self-play CI noise,
no 500ms-regime blindness.

Pipeline per corpus game:
  1. replay  — candidate engine plays the real ladder game; the opponent
     follows the PGN while legal; our moves use exact %clk time_left where
     present (sim clock fallback). The candidate's game is recorded as PGN.
  2. review  — SF19 @ --sf-depth scores our moves in the REAL game (V5) and
     in the REPLAY game (candidate). (Real-game reviews already on disk in
     results/leak_reviews/<game>.sf16.json are reused.)
  3. compare — bucket counts, mean cp_loss, and per-leak classification at
     V5's blunder/mistake plies: retained / avoided / replaced-worse.

Verdict (advisory, printed with numbers): candidate is "locally better"
iff leaks avoided >= 1 AND replaced-worse == 0 AND blunders+mistakes not
increased AND mean cp_loss not worse beyond noise (~10cp). Small corpus =
the numbers matter more than the PASS/FAIL label.

Usage (run from repo root with /tmp/chessbench/bin/python):
  # full A/B of the live tree (HEAD) or an env-toggle candidate
  python tools/quality_ab.py --candidate HEAD \\
      --game round-74-vs-rohan.pgn:white \\
      --game round-70-vs-kingsguard.pgn:black \\
      [--env CHESSATHON_CLAMP=1] [--sf-depth 16] \\
      --out results/quality_ab/<label>
  # a specific commit (archived to the out dir):
  python tools/quality_ab.py --candidate <commit-sha> --game ...:white ...

Self-test: --candidate HEAD on a game the ladder played with V5 must
reproduce the real game move-for-move on exact clocks; bucket maps should
be ~equal. Orchestrator warns if replay fidelity < 90%.

NOTE CPU sequencing: replays are real-clock (load-sensitive) and SF reviews
are heavy — never run while a 500ms gate is running.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = "/tmp/chessbench/bin/python"   # venue-mirror venv (python-chess + numba)
SF_REVIEW = REPO / "tools" / "review_sf.py"
DEFAULT_SF_DEPTH = 16
LEAK_REVIEW_DIR = REPO / "results" / "leak_reviews"

# ---------------------------------------------------------------------------
# replay worker (subcommand "replay") — one game per process, fresh JIT/state
# ---------------------------------------------------------------------------
WORKER = r"""#!/usr/bin/env python3
# quality_ab replay worker (spawned by the orchestrator; cwd = candidate root)
import argparse, json, sys, time
import chess, chess.pgn

ap = argparse.ArgumentParser()
ap.add_argument("--pgn"); ap.add_argument("--side", choices=["white", "black"])
ap.add_argument("--out-json"); ap.add_argument("--out-pgn")
a = ap.parse_args()

sys.path.insert(0, ".")          # candidate root: agent.py + engine/ live here
import agent  # noqa: E402       # numba JIT warmup ~40s, intended

game = chess.pgn.read_game(open(a.pgn))
our_side = chess.WHITE if a.side == "white" else chess.BLACK
moves = list(game.mainline_moves())

def start_board(g):
    b = g.board()
    if g.headers.get("SetUp") and g.headers.get("FEN"):
        b.set_fen(g.headers["FEN"])
    return b

# pass 1: global ply of each move + %clk clock-after per ply (no engine yet)
clk_after = {}        # ply (1-based) -> ms left after that ply's move
our_plies = []        # global plies of OUR moves
b = start_board(game)
for i, mv in enumerate(moves):
    ply = i + 1
    if b.turn == our_side:
        our_plies.append(ply)
    try:
        c = (list(game.mainline())[i]).clock()
    except Exception:
        c = None
    if c is not None:
        clk_after[ply] = int(c * 1000)
    b.push(mv)

# exact clocks = %clk present for every our-move ply except the first
# (time_left before our move at ply p = clock left after our previous move)
prev_our = {}
for idx, p in enumerate(our_plies):
    if idx > 0:
        prev_our[p] = our_plies[idx - 1]
have_exact = len(our_plies) <= 1 or all(
    prev_our[p] in clk_after for p in our_plies[1:])
if not have_exact:
    print("no full %clk coverage -> simulated clock", file=sys.stderr)

# pass 2: play the game
sim = {chess.WHITE: 120_000, chess.BLACK: 120_000}
rows = []
played = []           # uci of every move played in the replay
stop_reason = "played to end"
t0 = time.perf_counter()
rboard = start_board(game)
for i, mv in enumerate(moves):
    ply = i + 1
    if rboard.turn == our_side:
        k = len(rows) + 1
        fen = rboard.fen()
        if have_exact and ply != our_plies[0]:
            tl = clk_after[prev_our[ply]]
        elif have_exact:
            tl = 120_000
        else:
            tl = sim[our_side]
        t1 = time.perf_counter()
        got = agent.get_move(fen, tl)
        took = (time.perf_counter() - t1) * 1000
        if not have_exact:
            sim[our_side] -= int(took)
            sim[our_side] += 500
            if sim[our_side] < 0:
                stop_reason = "flag (sim clock)"
                break
        gm = chess.Move.from_uci(got) if got and got != "0000" else None
        ok = gm is not None and gm in rboard.legal_moves
        matched = ok and gm == mv
        try:
            game_san = rboard.san(mv)
        except Exception:
            game_san = mv.uci()
        rows.append({"k": k, "ply": ply, "game_san": game_san,
                     "cand_uci": got, "matched": matched,
                     "tl_ms": tl, "took_ms": int(took)})
        if not ok:
            stop_reason = "illegal/0000 from candidate"
            break
        played.append(gm.uci())
        rboard.push(gm)
        if rboard.is_game_over():
            stop_reason = "game over: " + str(rboard.result())
            break
    else:
        if mv not in rboard.legal_moves:
            stop_reason = "opponent PGN move illegal after deviation (ply %d)" % ply
            break
        played.append(mv.uci())
        rboard.push(mv)

# write replay PGN (recorded candidate game, original headers preserved)
g2 = chess.pgn.Game()
g2.headers.update(game.headers)
g2.headers["Result"] = "*" if not rboard.is_game_over() else rboard.result()
node = g2
b2 = start_board(game)
for u in played:
    node = node.add_variation(chess.Move.from_uci(u))
    b2.push(node.move)
open(a.out_pgn, "w").write(str(g2) + "\n")

elapsed = time.perf_counter() - t0
agree = sum(1 for r in rows if r["matched"])
print("replay: %d/%d our moves matched | %s | %.0fs (incl JIT)" %
      (agree, len(rows), stop_reason, elapsed))
json.dump({"pgn": a.pgn, "side": a.side, "rows": rows,
           "stop_reason": stop_reason, "matched": agree,
           "our_moves": len(rows), "have_exact_clocks": have_exact},
          open(a.out_json, "w"), indent=1)
"""


def _worker_script() -> str:
    p = Path("/tmp") / "qa_worker_replay.py"
    p.write_text(WORKER)
    return str(p)


def review(pgn_path: Path, depth: int, out_json: Path) -> list:
    """Run review_sf on a PGN; returns its rows (all sides in JSON)."""
    subprocess.run([PY, str(SF_REVIEW), str(pgn_path), "--depth", str(depth),
                    "--json", str(out_json)], check=True, cwd=REPO)
    return json.load(open(out_json))


def load_real_review(name: str, real_pgn: Path, depth: int) -> list:
    """Reuse battery JSONs (results/leak_reviews/<game>.sf16.json) if present."""
    cached = LEAK_REVIEW_DIR / f"{name}.sf{depth}.json"
    if cached.exists():
        return json.load(open(cached))
    return review(real_pgn, depth, cached)


def our_rows(rows: list, side: str) -> list:
    return [r for r in rows if r["side"] == side]


def stats(rows: list) -> dict:
    losses = [r["cp_loss"] for r in rows]
    # F1 (audit2): raw mean is dominated by SF mate-clamp entries
    # (>=20000 cp) — report winsorized (capped at 1000) and median
    # alongside; verdicts use the trimmed means (see checks below).
    trimmed = [min(x, 1000) for x in losses]
    med = sorted(losses)[len(losses) // 2] if losses else 0
    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {"n": len(rows), "counts": counts,
            "mean_cp_loss": round(sum(losses) / len(losses), 1) if losses else 0.0,
            "mean_trimmed": round(sum(trimmed) / len(trimmed), 1) if trimmed else 0.0,
            "median_cp_loss": med,
            "max_cp_loss": max(losses) if losses else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="HEAD",
                    help="HEAD (live tree) or a git commit sha")
    ap.add_argument("--game", action="append", required=True,
                    help="PGN name:side relative to results/matches/ (repeatable)")
    ap.add_argument("--env", action="append", default=[],
                    help="ENV=value passed to replay workers (repeatable)")
    ap.add_argument("--sf-depth", type=int, default=DEFAULT_SF_DEPTH)
    ap.add_argument("--out", required=True, help="output dir (created)")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cand_root = REPO
    if a.candidate != "HEAD":
        snap = out / "candidate_tree"
        subprocess.run(["git", "archive", a.candidate], check=True, cwd=REPO,
                       stdout=open(snap.with_suffix(".tar"), "wb"))
        subprocess.run(["tar", "-xf", str(snap.with_suffix(".tar")), "-C",
                        str(snap)], check=True)
        cand_root = snap
    env = dict(os.environ)
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v
    env["NUMBA_CACHE_DIR"] = f"/tmp/qa-numba-{Path(a.out).name}"

    worker = _worker_script()
    games = [(g.partition(":")[0].removesuffix(".pgn"),
              g.partition(":")[2] or "white")
             for g in a.game]
    per_game = {}
    for name, side in games:
        real_pgn = REPO / "results" / "matches" / f"{name}.pgn"
        v5_rows = our_rows(load_real_review(name, real_pgn, a.sf_depth), side)
        # 1) replay candidate against the PGN
        rj = out / f"{name}.replay.json"
        rpgn = out / f"{name}.replay.pgn"
        subprocess.run([PY, worker, "--pgn", str(real_pgn), "--side", side,
                        "--out-json", str(rj), "--out-pgn", str(rpgn)],
                       check=True, cwd=cand_root, env=env, timeout=1800)
        rep = json.load(open(rj))
        # 2) SF19-review the replay (candidate's game)
        cand_rows = our_rows(
            review(rpgn, a.sf_depth, out / f"{name}.replay.sf{a.sf_depth}.json"),
            side)
        s_v5, s_cand = stats(v5_rows), stats(cand_rows)
        # 3) leak classification: V5 blunder/mistake our-moves by index k
        #    vs the candidate's move at the same k (only pre-divergence plies
        #    share a position; after divergence the candidate's own game is
        #    scored standalone)
        leak_cls = {"retained": [], "avoided": [], "replaced_worse": [],
                    "unreached": 0}
        rep_by_k = {r["k"]: r for r in rep["rows"]}
        on_line = True   # candidate still following the real game's line
        for idx, r in enumerate(v5_rows):
            k = idx + 1
            cr = rep_by_k.get(k)
            if cr is None:
                leak_cls["unreached"] += 1   # replay ended before this ply
                continue
            bad = r["verdict"] in ("blunder", "mistake")
            if bad and on_line:
                cm = cand_rows[k - 1] if k - 1 < len(cand_rows) else None
                if cm is not None:
                    entry = (r["san"], cm["san"], r["cp_loss"], cm["cp_loss"])
                    if cr["matched"]:
                        leak_cls["retained"].append(entry)
                    elif cm["verdict"] in ("blunder", "mistake"):
                        leak_cls["replaced_worse"].append(entry)
                    else:
                        leak_cls["avoided"].append(entry)
            elif bad and not on_line:
                # candidate deviated earlier and never faced this position
                leak_cls["unreached"] += 1
            if not cr["matched"]:
                on_line = False
        per_game[name] = {"side": side, "v5": s_v5, "cand": s_cand,
                          "leaks": leak_cls,
                          "fidelity": rep["matched"], "our_moves": rep["our_moves"],
                          "replay_stop": rep["stop_reason"],
                          "have_exact_clocks": rep["have_exact_clocks"]}
        print(f"[{name}] V5 {s_v5['counts']} mean {s_v5['mean_cp_loss']} "
              f"trimmed {s_v5['mean_trimmed']} | "
              f"cand {s_cand['counts']} mean {s_cand['mean_cp_loss']} "
              f"trimmed {s_cand['mean_trimmed']} | "
              f"fidelity {rep['matched']}/{rep['our_moves']}", flush=True)

    # F2 (audit2): aggregate checks run on TRIMMED means (F1: raw means
    # are clamp-dominated); print faced/total leak denominators.
    # F5: paired shared-prefix delta per game (moves before first
    # divergence, identical positions) is the only like-for-like signal.
    tot = {"v5": {"bm": 0, "mean": 0.0, "n": 0, "tmean": 0.0},
           "cand": {"bm": 0, "mean": 0.0, "n": 0, "tmean": 0.0}}
    leaks_tot = {"retained": 0, "avoided": 0, "replaced_worse": 0}
    faced_tot = {"faced": 0, "total": 0}
    for name, pg in per_game.items():
        for key, src in (("v5", pg["v5"]), ("cand", pg["cand"])):
            tot[key]["bm"] += src["counts"].get("blunder", 0) \
                + src["counts"].get("mistake", 0)
            tot[key]["mean"] += src["mean_cp_loss"] * src["n"]
            tot[key]["tmean"] += src["mean_trimmed"] * src["n"]
            tot[key]["n"] += src["n"]
        for cls in leaks_tot:
            leaks_tot[cls] += len(pg["leaks"][cls])
        lk = pg["leaks"]
        faced = len(lk["retained"]) + len(lk["avoided"]) \
            + len(lk["replaced_worse"])
        pg["faced"] = faced
        faced_tot["faced"] += faced
        faced_tot["total"] += len(pg["leaks"].get("all", [])) \
            + len(lk["retained"]) + len(lk["avoided"]) \
            + len(lk["replaced_worse"]) + lk["unreached"]
    for key in tot:
        if tot[key]["n"]:
            tot[key]["mean"] = round(tot[key]["mean"] / tot[key]["n"], 1)
            tot[key]["tmean"] = round(tot[key]["tmean"] / tot[key]["n"], 1)

    checks = {
        "leaks_avoided>=1": leaks_tot["avoided"] >= 1,
        "no_replaced_worse": leaks_tot["replaced_worse"] == 0,
        "no_more_blunders": tot["cand"]["bm"] <= tot["v5"]["bm"],
        "mean_not_worse": tot["cand"]["tmean"] <= tot["v5"]["tmean"] + 10.0,
    }
    verdict = "PASS (locally better)" if all(checks.values()) else \
              ("WEAK (mixed evidence)" if sum(checks.values()) >= 2
               else "FAIL (not better)")
    rep_lines = [
        f"# quality A/B — candidate {a.candidate} vs shipped V5 (SF19 d{a.sf_depth})",
        "",
        f"corpus: {', '.join(f'{n} ({s})' for n, s in games)}",
        "",
        "## Aggregate",
        f"- V5:        blunders+mistakes {tot['v5']['bm']} | mean cp_loss "
        f"{tot['v5']['mean']} | trimmed {tot['v5']['tmean']} "
        f"(n={tot['v5']['n']})",
        f"- candidate: blunders+mistakes {tot['cand']['bm']} | mean cp_loss "
        f"{tot['cand']['mean']} | trimmed {tot['cand']['tmean']} "
        f"(n={tot['cand']['n']})",
        f"- leaks: retained {leaks_tot['retained']} | avoided "
        f"{leaks_tot['avoided']} | replaced-worse {leaks_tot['replaced_worse']} "
        f"| faced {faced_tot['faced']}/{faced_tot['total']} "
        "(faced = reached pre-divergence; small faced/total = lottery)",
        "",
        "## Checks",
    ] + [f"- {k}: {'OK' if v else 'FAIL'}" for k, v in checks.items()] + [
        "", f"## VERDICT: {verdict}", "", "## Per game",
    ]
    for name, pg in per_game.items():
        rep_lines += [
            f"### {name} ({pg['side']})",
            f"- replay fidelity {pg['fidelity']}/{pg['our_moves']} "
            f"({pg['replay_stop']}; exact clocks {pg['have_exact_clocks']})",
            f"- V5  {pg['v5']['counts']} mean {pg['v5']['mean_cp_loss']} "
            f"trimmed {pg['v5']['mean_trimmed']} median "
            f"{pg['v5']['median_cp_loss']} max {pg['v5']['max_cp_loss']}",
            f"- cand {pg['cand']['counts']} mean {pg['cand']['mean_cp_loss']} "
            f"trimmed {pg['cand']['mean_trimmed']} median "
            f"{pg['cand']['median_cp_loss']} max {pg['cand']['max_cp_loss']}",
            f"- leaks: {json.dumps(pg['leaks'])} faced {pg['faced']}",
        ]
    rep = "\n".join(rep_lines) + "\n"
    (out / "REPORT.md").write_text(rep)
    json.dump({"totals": tot, "leaks": leaks_tot, "checks": checks,
               "verdict": verdict, "per_game": per_game},
              open(out / "report.json", "w"), indent=1)
    print("\n" + rep)
    if a.candidate == "HEAD":
        ok = all(pg["our_moves"] == 0
                 or pg["fidelity"] / pg["our_moves"] >= 0.9
                 for pg in per_game.values())
        fids = [f"{pg['fidelity']}/{pg['our_moves']}" for pg in per_game.values()]
        print(f"SELF-TEST fidelity {fids} -> "
              + ("instrument OK" if ok else "check divergences (machine artifacts?)"))


if __name__ == "__main__":
    main()
