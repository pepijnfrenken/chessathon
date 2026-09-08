"""Modal CPU fan-out for chessathon gate matches / SPRT games.

Runs many independent engine-vs-engine games in parallel across Modal CPU
containers. Each container runs one game (or a small batch) using the repo's
own tools/engine_side.py protocol — the SAME code as local gates, just fanned
out. Results stream back and are aggregated like gate_match.py does.

This is a DEV tool. NOT shipped in agent.zip (ORIGINALITY.md: everything in
the zip is ours, but dev tooling stays in tools/ — cloud execution doesn't
change the engine code itself; the engine that plays is byte-identical to
local).

Usage:
  modal run tools/modal_runner.py --games 24 --side-a "hand:1111" --side-b "hand:0000" --move-ms 300 --seed 7
  (env CHESSATHON_EVAL_CONFIG etc are passed per-side via engine_side envs)

Design notes:
  - Modal CPU containers are cheap (~$0.000002/core-sec tier, free tier
    included). 24 games x 2 sides x ~1 core each = a few minutes.
  - Each worker imports engine_side (JIT warmup ~35s) then plays ONE game
    against a peer worker over stdin/stdout... simpler: run BOTH sides in ONE
    container (two subprocesses) per game — one game = one container = clean
    isolation, no networking between containers needed.
  - Game result (W/L/D + ply + flags) returned per container; aggregator sums.
"""
import os
import subprocess
import sys
import time

import modal

app = modal.App("chessathon-gate")

# Image: python + numba/numpy (engine deps) + python-chess (tools use it)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("numpy", "numba", "python-chess")
)

# Mount the repo read-only so containers see the exact engine code
REPO = "/home/pino/projects/chessathon"
repo_mount = modal.Mount.from_local_dir(REPO, remote_path="/repo")

# Chessbench python (the venv with numba the local runs use) is NOT needed —
# Modal's image has numba. But the tools import engine via sys.path; engine_side
# needs cwd=/repo and PYTHONPATH=/repo.


def _run_one_game(side_a: str, side_b: str, move_ms: int, seed: int, opening_idx: int,
                  a_is_white: bool) -> dict:
    """Play one game between side_a and side_b configs in THIS container.
    a_is_white alternates colors per game for fairness."""
    import sys

    sys.path.insert(0, "/repo")
    import os
    import subprocess

    import chess
    from tools import common  # noqa: F401  (openings + adjudication)

    def spawn_side(cfg: str):
        env = dict(os.environ)
        name, gate = cfg.split(":")
        env["CHESSATHON_EVAL_CONFIG"] = name
        env["CHESSATHON_EVAL_GATE"] = gate
        env["CHESSATHON_MOVE_BUDGET_MS"] = str(move_ms)
        return subprocess.Popen(
            [sys.executable, "/repo/tools/engine_side.py"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=env, cwd="/repo",
        )

    a, b = spawn_side(side_a), spawn_side(side_b)
    try:
        ready_a = a.stdout.readline().strip()
        ready_b = b.stdout.readline().strip()
        if ready_a != "ready" or ready_b != "ready":
            return {"error": f"warmup failed: {ready_a!r} {ready_b!r}"}

        # opening FEN from common (mirrors local gate); fall back to startpos
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        try:
            if hasattr(common, "OPENING_FENS") and opening_idx < len(common.OPENING_FENS):
                fen = common.OPENING_FENS[opening_idx]
        except Exception:
            pass
        board = chess.Board(fen)
        # Normalize side assignment by color
        white_proc = a if a_is_white else b
        black_proc = b if a_is_white else a

        ply = 0
        flags = []
        while not board.is_game_over() and ply < 300:
            proc = white_proc if board.turn == chess.WHITE else black_proc
            proc.stdin.write(board.fen() + "\n")
            proc.stdin.flush()
            uci = proc.stdout.readline().strip()
            if uci == "0000":
                break
            try:
                mv = chess.Move.from_uci(uci)
                if mv not in board.legal_moves:
                    flags.append(f"illegal:{uci}:{board.fen()}")
                    break
                board.push(mv)
                ply += 1
            except Exception as e:
                flags.append(f"parse:{uci}:{e}")
                break
        # Result from side A's perspective
        if board.is_checkmate():
            mate_color = "W" if board.turn == chess.BLACK else "B"  # side that mated
            a_won = (mate_color == "W") == a_is_white
            res = "A" if a_won else "B"
        elif board.is_stalemate() or board.is_insufficient_material() or ply >= 300:
            res = "D"
        elif board.can_claim_draw():
            res = "D"
        else:
            res = "D"
        return {"result": res, "ply": ply, "flags": flags}
    finally:
        for p in (a, b):
            try:
                p.stdin.close()
                p.kill()
            except Exception:
                pass


@app.function(image=image, mounts=[repo_mount], cpu=2, memory=2048, timeout=900)
def play_one_game(args: dict) -> dict:
    return _run_one_game(**args)


@app.local_entrypoint()
def main(
    games: int = 24,
    side_a: str = "hand:1111",
    side_b: str = "hand:0000",
    move_ms: int = 500,
    seed: int = 7,
):
    """Fan out `games` independent games across Modal CPU containers."""
    args_list = [
        {
            "side_a": side_a, "side_b": side_b, "move_ms": move_ms,
            "seed": seed, "opening_idx": i % 11,
            "a_is_white": (i % 2 == 0),
        }
        for i in range(games)
    ]
    print(f"Fanning out {games} games: {side_a} vs {side_b} @ {move_ms}ms (colors alternate)", flush=True)
    t0 = time.time()
    results = list(play_one_game.map(args_list))
    dt = time.time() - t0

    # Aggregate like gate_match.py — result is from side A's perspective ("A"/"B"/"D")
    wins = losses = draws = 0
    flags = []
    plies = []
    errs = 0
    for r in results:
        if "error" in r:
            errs += 1
            print(f"  ERR: {r['error']}", flush=True)
            continue
        plies.append(r["ply"])
        flags.extend(r["flags"])
        res = r["result"]
        if res == "A":
            wins += 1
        elif res == "B":
            losses += 1
        elif res == "D":
            draws += 1

    score = (wins + draws / 2) / max(1, wins + losses + draws)
    print(f"\n=== {side_a} vs {side_b}: {wins}W {losses}L {draws}D over {games} games (score {score:.3f}) ===", flush=True)
    print(f"flags: {flags if flags else 'ZERO'}", flush=True)
    print(f"errors: {errs}", flush=True)
    if plies:
        print(f"avg ply: {sum(plies)/len(plies):.1f} (max {max(plies)})", flush=True)
    print(f"wall time: {dt:.1f}s for {games} games", flush=True)
