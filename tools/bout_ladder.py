"""LADDER-FORMAT bout: two engine trees, real clock, the ACTUAL ladder
start positions (dev tool, NOT shipped).

Why this exists: every other full-game instrument we own plays from our
own 11 hand-written opening lines (0-8 plies) at a fixed ms/move. Every
rated ladder game instead starts from a platform-preset position at
move 5-10 (~9-19 plies) with a 120 s + 0.5 s clock. This tool closes
that representativeness gap: full games from the exact start FENs of our
real ladder rounds, with the real clock shape, side A vs side B.

Design:
  * Start positions: parsed live from results/matches/round-*.log
    (`Start FEN` + `Round` lines) so the pool always tracks the corpus.
    Deduped; --min-round filters to an era (default: all rounds).
  * Clock: 120 s base + 0.5 s increment per side. Per move the driver
    computes the budget from the side's own remaining time using that
    side's engine/time.py `budget_ms(rem, inc)` (loaded standalone from
    the tree root, no package import / no numba), sends it to the side
    over the `budget <ms>` protocol, and debits REAL wall-clock time.
    Flag = clock <= 0 after a move. (Mirrors the platform rules; the
    shipped agent derives the same budget from the harness's time_left.)
  * Each pair = one FEN played twice with swapped colours (balance).
  * Engines: tools/engine_side_clk.py (per-move budget protocol,
    stateless fallback for old trees, q5 warmup shape).
  * Flags recorded, game scored as loss for the offending side: crash,
    illegal, null-move, hang (no reply within budget + grace), timeout.
    A single flag ends only that game; a dead side ends the run.
  * Output: --out dir with SUMMARY.txt, stream.log (live), gNN PGNs
    with %clk comments.

This is a MONITORING / due-diligence instrument, not a calibrated gate
line: read it as "how do these two trees actually play ladder-shaped
games", not as a 0.45-threshold decision. For ladder-format checks of a
candidate vs shipped, 16 games ≈ 45-60 min on the box (1 core/side).

Usage:
    python tools/bout_ladder.py --side-a-root . --side-b-root /tmp/chessathon-v7ref \
        --side-a-name v8 --side-b-name v7 --games 16 --seed 11 \
        --out results/bout_ladder_v8_vs_v7 [--min-round 48] [--schedule-only]
"""

import argparse
import importlib.util
import os
import random
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import chess
import chess.pgn

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from common import MAX_PLY, adjudicate, side_env  # noqa: E402

START_FEN_RE = re.compile(r"^\s*Start FEN\s+(.+)$", re.M)
ROUND_RE = re.compile(r"^\s*Round\s+Rated (\d+)", re.M)
COLOUR_RE = re.compile(r"^\s*Colour\s+(\w+)", re.M)
OPENING_RE = re.compile(r"^\s*Opening\s+(.+)$", re.M)


def load_budget_fn(root: str):
    """Load engine/time.py from a tree root standalone (it is dependency-
    free); returns budget_ms(remaining_ms, inc_ms)."""
    path = Path(root) / "engine" / "time.py"
    spec = importlib.util.spec_from_file_location(
        f"engtime_{abs(hash(root)) % 10**8}", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.budget_ms


def ladder_pool(min_round: int):
    """Unique ladder start FENs from the committed round logs."""
    out, seen = [], set()
    for log in sorted((_ROOT / "results" / "matches").glob("round-*.log")):
        txt = log.read_text(errors="replace")
        rm, fm = ROUND_RE.search(txt), START_FEN_RE.search(txt)
        if not (rm and fm):
            continue
        rnd = int(rm.group(1))
        if rnd < min_round:
            continue
        fen = fm.group(1).strip()
        if fen in seen:
            continue
        seen.add(fen)
        opening = OPENING_RE.search(txt)
        out.append({"round": rnd, "fen": fen,
                    "colour": (COLOUR_RE.search(txt) or [None, "?"])[1],
                    "opening": opening.group(1).strip() if opening else ""})
    out.sort(key=lambda d: d["round"])
    return out


class Log:
    def __init__(self, path: Path):
        self.fh = open(path, "w")

    def __call__(self, line: str):
        print(line, flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()


def clk_str(ms: float) -> str:
    ms = max(0, int(ms))
    return f"{ms // 60000}:{(ms % 60000) / 1000:06.3f}"


def spawn(root: str, cache: str, spec: str, default_ms: int = 300):
    env = side_env(spec, default_ms)
    env["NUMBA_CACHE_DIR"] = cache
    env["NUMBA_NUM_THREADS"] = "1"
    return subprocess.Popen(
        [sys.executable, str(_HERE / "engine_side_clk.py"), root],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=root, env=env)


def wait_ready(proc, label: str, log: Log):
    """Warmup banner on stderr is the ready signal (~50 s cold)."""
    line = proc.stderr.readline()
    if "engine_side" not in line:
        raise RuntimeError(f"{label} failed to start: {line!r}")
    log(f"  [{label}] {line.strip()}")


def ask(proc, budget_ms: int, fen: str, grace_s: float, log: Log):
    """Send one move request; return (resp, dt_ms, err) where err flags
    a harness-level problem (hang / dead pipe)."""
    if proc.poll() is not None:
        return None, 0.0, "dead"
    proc.stdin.write(f"budget {budget_ms}\n")
    proc.stdin.write(fen + "\n")
    proc.stdin.flush()
    timeout = budget_ms / 1000.0 + grace_s
    t0 = time.monotonic()
    r, _, _ = select.select([proc.stdout], [], [], timeout)
    if not r:
        return None, (time.monotonic() - t0) * 1000.0, "hang"
    line = proc.stdout.readline()
    dt = (time.monotonic() - t0) * 1000.0
    if line == "":
        return None, dt, "dead"
    return line.strip(), dt, None


def play_game(a_proc, b_proc, a_name, b_name, spec: dict, rng,
              budget_a, budget_b, base_ms, inc_ms, grace_s, log: Log,
              game_no: int):
    """One ladder-format game. Returns dict(result_from_A, flags, ply,
    pgn, wall_s, movetimes)."""
    fen = spec["fen"]
    board = chess.Board(fen)
    if board.is_game_over():
        return None  # bad pool entry, caller skips
    a_white = spec["a_white"]
    sides = {chess.WHITE: ("a", a_proc, budget_a) if a_white
             else ("b", b_proc, budget_b),
             chess.BLACK: ("b", b_proc, budget_b) if a_white
             else ("a", a_proc, budget_a)}
    names = {"a": a_name, "b": b_name}
    for p in (a_proc, b_proc):
        try:
            if p.poll() is None:
                p.stdin.write("reset\n")
                p.stdin.flush()
        except Exception:
            pass
    clocks = {chess.WHITE: base_ms, chess.BLACK: base_ms}
    flags, movetimes = [], []
    fatal = False
    pg = chess.pgn.Game()
    pg.headers["Event"] = "ladder-format bout"
    pg.headers["Site"] = "local (dev instrument)"
    pg.headers["Round"] = str(spec["round"])
    pg.headers["White"] = a_name if a_white else b_name
    pg.headers["Black"] = b_name if a_white else a_name
    pg.headers["FEN"] = fen
    pg.headers["SetUp"] = "1"
    pg.headers["OpeningSource"] = spec.get("opening", "")
    node = pg
    loser = None
    ply = 0
    t_game = time.monotonic()
    while not board.is_game_over() and ply < MAX_PLY:
        stm = board.turn
        side_key, proc, bud_fn = sides[stm]
        rem = clocks[stm]
        bud = max(50, min(int(bud_fn(rem, inc_ms)), 45000))
        if bud > rem - 100:
            bud = max(50, rem - 100)
        resp, dt, err = ask(proc, bud, board.fen(), grace_s, log)
        if err == "hang":
            flags.append(("hang", names[side_key],
                          f"no reply in {bud}ms+{grace_s}s at ply {ply + 1}"))
            loser, fatal = side_key, True
            break
        if err == "dead":
            flags.append(("crash", names[side_key],
                          f"side process died at ply {ply + 1}"))
            loser, fatal = side_key, True
            break
        if resp.startswith("ERROR"):
            flags.append(("crash", names[side_key], resp))
            loser = side_key
            break
        if resp == "0000":
            flags.append(("null-move", names[side_key],
                          f"0000 mid-game at ply {ply + 1}"))
            loser = side_key
            break
        try:
            mv = chess.Move.from_uci(resp)
        except ValueError:
            flags.append(("illegal", names[side_key], f"unparseable {resp!r}"))
            loser = side_key
            break
        if mv not in board.legal_moves:
            flags.append(("illegal", names[side_key], resp))
            loser = side_key
            break
        clocks[stm] = min(rem - dt + inc_ms, base_ms)
        movetimes.append(dt)
        board.push(mv)
        node = node.add_variation(mv)
        node.comment = f"[%clk {clk_str(clocks[stm])}]"
        ply += 1
        if clocks[stm] <= 0:
            flags.append(("timeout", names[side_key],
                          f"clock {clocks[stm]:.0f}ms after ply {ply}"))
            loser = side_key
            break
        log(f"    ply {ply:3d} {'W' if stm else 'B'} {resp:5s} "
            f"dt={dt:6.0f}ms bud={bud:5d}ms "
            f"clk W{clocks[chess.WHITE]/1000:6.1f}s B{clocks[chess.BLACK]/1000:6.1f}s")
    if loser is not None:
        # loser is a side KEY ("a"/"b"); result in White's POV.
        winner_key = "b" if loser == "a" else "a"
        winner_is_white = (winner_key == "a") == a_white
        result_w = "1-0" if winner_is_white else "0-1"
    else:
        result_w = adjudicate(board, ply)
    pg.headers["Result"] = result_w
    # from A's perspective
    if result_w == "1/2-1/2":
        res_a = 0.5
    elif (result_w == "1-0") == a_white:
        res_a = 1.0
    else:
        res_a = 0.0
    return {"res_a": res_a, "result_w": result_w, "flags": flags, "ply": ply,
            "pgn": pg, "wall_s": time.monotonic() - t_game,
            "movetimes": movetimes, "round": spec["round"],
            "a_white": a_white, "fen": fen, "fatal": fatal}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side-a-root", default=".")
    ap.add_argument("--side-b-root", required=True)
    ap.add_argument("--side-a-name", default="A")
    ap.add_argument("--side-b-name", default="B")
    ap.add_argument("--side-a-spec", default="hand:1111")
    ap.add_argument("--side-b-spec", default="hand:1111")
    ap.add_argument("--games", type=int, default=16,
                    help="total games (must be even; pairs play one FEN twice)")
    ap.add_argument("--min-round", type=int, default=48)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--base-ms", type=int, default=120000)
    ap.add_argument("--inc-ms", type=int, default=500)
    ap.add_argument("--grace-s", type=float, default=90.0)
    ap.add_argument("--out", required=False)
    ap.add_argument("--schedule-only", action="store_true")
    args = ap.parse_args()

    if args.games % 2:
        sys.exit("--games must be even (colour-swapped pairs)")

    pool = ladder_pool(args.min_round)
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    pairs = args.games // 2
    if pairs > len(pool):
        print(f"# note: cycling {len(pool)} FENs for {pairs} pairs")
    specs = []
    for i in range(pairs):
        item = pool[i % len(pool)]
        specs.append(dict(item, a_white=True))
        specs.append(dict(item, a_white=False))

    if args.schedule_only:
        print(f"pool: {len(pool)} unique ladder FENs (min-round {args.min_round})")
        for i, s in enumerate(specs):
            print(f"  g{i + 1:2d} round {s['round']:3d} "
                  f"{'A-white' if s['a_white'] else 'B-white'}  "
                  f"{s['fen']}  ({s['opening']})")
        return 0

    if not args.out:
        sys.exit("--out required unless --schedule-only")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = Log(out / "stream.log")
    budget_a = load_budget_fn(args.side_a_root)
    budget_b = load_budget_fn(args.side_b_root)

    log(f"# ladder-format bout: {args.side_a_name} (A) vs {args.side_b_name} (B)")
    log(f"# A root: {Path(args.side_a_root).resolve()}")
    log(f"# B root: {Path(args.side_b_root).resolve()}")
    log(f"# clock {args.base_ms}ms + {args.inc_ms}ms/move; "
        f"{args.games} games; seed {args.seed}; "
        f"pool {len(pool)} FENs r{args.min_round}+; {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}")

    a_proc = spawn(args.side_a_root, f"/tmp/numba_cache_clk_a_{args.seed}",
                   args.side_a_spec)
    b_proc = spawn(args.side_b_root, f"/tmp/numba_cache_clk_b_{args.seed}",
                   args.side_b_spec)
    try:
        wait_ready(a_proc, f"{args.side_a_name} A", log)
        wait_ready(b_proc, f"{args.side_b_name} B", log)
        wins = losses = draws = 0
        all_results = []
        t0 = time.monotonic()
        for i, spec in enumerate(specs):
            if a_proc.poll() is not None or b_proc.poll() is not None:
                log(f"# ABORT: a side died before game {i + 1}")
                break
            log(f"game {i + 1:2d}/{args.games}  round {spec['round']} "
                f"{'A' if spec['a_white'] else 'B'}-white  {spec['opening']}")
            g = play_game(a_proc, b_proc, args.side_a_name, args.side_b_name,
                          spec, rng, budget_a, budget_b, args.base_ms,
                          args.inc_ms, args.grace_s, log, i + 1)
            if g is None:
                log("  (skip: game already over at start FEN)")
                continue
            if g["res_a"] == 1.0:
                wins += 1
            elif g["res_a"] == 0.0:
                losses += 1
            else:
                draws += 1
            n = wins + losses + draws
            score = (wins + 0.5 * draws) / n
            mv_avg = sum(g["movetimes"]) / max(1, len(g["movetimes"]))
            mv_max = max(g["movetimes"], default=0)
            flag_s = (" FLAGS:" + ";".join(f"{k}/{s}/{d}"
                                           for k, s, d in g["flags"])) \
                if g["flags"] else ""
            line = (f"  -> {g['result_w']} (A: {'W' if g['res_a'] == 1 else ('D' if g['res_a'] == 0.5 else 'L')}) "
                    f"ply={g['ply']:3d} wall={g['wall_s']:6.0f}s "
                    f"mv~{mv_avg:5.0f}ms max {mv_max:6.0f}ms | "
                    f"{args.side_a_name} {wins}-{losses}-{draws} ({score:.3f}){flag_s}")
            log(line)
            gpath = out / (f"g{i + 1:02d}_r{g['round']}_"
                           f"{'a' if g['a_white'] else 'b'}w.pgn")
            with open(gpath, "w") as fh:
                print(g["pgn"], file=fh)
            all_results.append(g)
            if g["fatal"]:
                log(f"# ABORT: fatal desync at game {i + 1} ({g['flags']})")
                break
        dts = [d for g in all_results for d in g["movetimes"]]
        summary = [
            f"=== SUMMARY: {args.side_a_name} (A) vs {args.side_b_name} (B) ===",
            f"games {len(all_results)} | A score {wins}W-{losses}L-{draws}D "
            f"({(wins + 0.5 * draws) / max(1, len(all_results)):.3f})",
            f"wall {time.monotonic() - t0:.0f}s | move times: avg "
            f"{sum(dts) / max(1, len(dts)):.0f}ms, max {max(dts, default=0):.0f}ms",
            f"flags {sum(len(g['flags']) for g in all_results)}",
        ]
        for ln in summary:
            log(ln)
        (out / "SUMMARY.txt").write_text("\n".join(summary) + "\n")
        return 0
    finally:
        for p in (a_proc, b_proc):
            try:
                p.stdin.write("quit\n")
                p.stdin.flush()
            except Exception:
                pass
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
