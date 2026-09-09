"""One real-clock-mode match pair: cand vs v5 from two engine_side trees,
120s+0.5s clocks with the engine's own budget policy (remaining/45+inc,
clamped) applied by this driver. Saves a PGN. Usage:
  python bout_pair.py <cand_root> <v5_root> <pair_idx> <out_dir> <seed>
"""
import os, random, sys, time
import chess, chess.pgn

sys.path.insert(0, "/home/pino/projects/chessathon/tools")
from common import side_env, adjudicate, VICTIM

CAND = sys.argv[1]; V5 = sys.argv[2]; IDX = int(sys.argv[3])
OUT = sys.argv[4]; SEED = int(sys.argv[5])

INC = 500; BASE = 120000
MAX_PLY = 300

def spawn(root):
    env = side_env("hand:1111", 0)  # budget unused; driver passes FENs only
    env["CHESSATHON_MOVE_BUDGET_MS"] = "120000"  # hard cap, driver clamps via clock below? engine_side uses env only.
    env["NUMBA_CACHE_DIR"] = "/tmp/numba_cache_chessathon_" + \
        os.path.basename(root.rstrip("/"))
    import subprocess
    return subprocess.Popen(
        [sys.executable, "/tmp/q5l3/q5_engine_side.py", root],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=root, env=env)

def budget_ms(remaining_ms):
    b = int(remaining_ms) // 45 + INC
    return int(max(50, min(b, 45000)))

def ask(proc, fen, budget_ms_):
    proc.stdin.write(f"budget {budget_ms_}\n")
    proc.stdin.write(fen + "\n"); proc.stdin.flush()
    r = proc.stdout.readline()
    if not r:  # EOF: engine died — dump its stderr tail
        err = "?"
        try:
            proc.stdin.close()
            err = proc.stderr.read()[-2000:]
        except Exception:
            pass
        raise RuntimeError(f"engine died rc={proc.poll()} stderr:\n{err}")
    return r.strip()

def game(a_root, b_root, fen, a_white, rng, path):
    a = spawn(a_root); b = spawn(b_root)
    board = chess.Board(fen)
    clocks = {chess.WHITE: BASE, chess.BLACK: BASE}
    sides = {chess.WHITE: a if a_white else b, chess.BLACK: b if a_white else a}
    # engines JIT-warm at import (~50s): their startup banner on STDERR is
    # the ready signal. stdout is reserved for move replies ONLY.
    for p in (a, b):
        ready = p.stderr.readline()
        if "engine_side" not in ready:
            raise RuntimeError(f"engine failed to start: {ready!r}")
    pg = chess.pgn.Game(); pg.headers["Event"] = f"q5fix1-L3-pair{IDX}"
    pg.headers["White"] = "q5cand" if a_white else "v5"
    pg.headers["Black"] = "v5" if a_white else "q5cand"
    node = pg
    ply = 0; flags = []
    try:
        while not board.is_game_over() and ply < MAX_PLY:
            stm = board.turn
            rem = clocks[stm]
            bud = budget_ms(rem)
            t0 = time.monotonic()
            uci = ask(sides[stm], board.fen(), budget_ms(rem))
            dt = (time.monotonic() - t0) * 1000
            if uci.startswith("ERROR"):
                flags.append(uci); break
            if uci == "0000":
                break
            m = chess.Move.from_uci(uci)
            print(f"[pair {IDX}] ply {ply+1} {'W' if stm else 'B'} {uci} dt={dt:.0f}ms budget={bud}ms", flush=True)
            clocks[stm] = min(rem - dt + INC, BASE)
            if clocks[stm] <= 0:
                print(f"[pair {IDX}] FLAG at ply {ply} dt={dt:.0f}ms", flush=True)
                flags.append("flag"); break
            board.push(m); node = node.add_variation(m); ply += 1
            if ply % 20 == 0:
                print(f"[pair {IDX}] ply {ply} clocks W{clocks[chess.WHITE]/1000:.0f}s B{clocks[chess.BLACK]/1000:.0f}s", flush=True)
        res = adjudicate(board, ply)
    finally:
        for p in (a, b):
            try: p.stdin.write("quit\n"); p.stdin.flush()
            except Exception: pass
            p.terminate()
    pg.headers["Result"] = res
    if flags: pg.headers["Flags"] = " ".join(flags)
    with open(path, "w") as f:
        print(pg, file=f, end="")
    return res, ply, flags

def main():
    rng = random.Random(SEED * 100 + IDX)
    from common import OPENING_FENS
    fen = rng.choice(OPENING_FENS)
    a_white = IDX % 2 == 0
    p1 = f"{OUT}/pair{IDX}_g1.pgn"
    res1, ply1, fl1 = game(CAND, V5, fen, a_white, rng, p1)
    fen2 = rng.choice(OPENING_FENS)
    p2 = f"{OUT}/pair{IDX}_g2.pgn"
    res2, ply2, fl2 = game(CAND, V5, fen2, not a_white, rng, p2)
    # score from cand perspective (cand = a)
    def pts(res, cand_white):
        if res == "1/2-1/2": return 0.5
        return 1.0 if (res == "1-0") == cand_white else 0.0
    print(f"PAIR {IDX}: g1 {res1} ply={ply1} flags={fl1} | g2 {res2} ply={ply2} flags={fl2} | cand_pts {pts(res1,a_white)+pts(res2,not a_white):.1f}/2")

main()
