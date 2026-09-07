"""Shuffle / repetition regression checker (dev tool, NOT shipped).

Plays a set of won-endgame FENs at a fixed per-move budget between an
engine config (default hand:1111) and a bare-material defender
(hand:0000), and reports how the strong side converts:

  - game result + ply + material diff at the end
  - POSITION REPETITIONS: when the same zobrist-keyed position occurs a
    2nd / 3rd time on the game path (3 occurrences = a threefold draw).
    For a won game we want NO 3rd occurrence, and ideally no 2nd
    occurrence either (shuffling that revisits squares is how won games
    threefold into draws — the ladder r54/r55 pattern).
  - SHUFFLE STREAKS: maximal runs of consecutive plies where the strong
    side's moves all move ONE piece and visit at most 4 distinct target
    squares (e.g. rook Rb1-Ra1-Rb1-... or king bounce a1-b1-a1). A
    streak >= 4 in a won position with an alternative non-repeating move
    available is the exact anti-shuffle regression target.

Exit code: 0 iff every case marked WON converts (result is a win for the
strong side) AND no position reaches its 3rd occurrence before the game
ends (i.e. no threefold draw). Losses/draws for NON-won cases are
tolerated (suite cases are all won; a failed conversion = exit 1).

Usage:
    python tools/shuffle_check.py [--move-ms 300] [--only KPK,KRvK]
                                  [--max-plies 300]
"""

import argparse
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import chess

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

from common import MAX_PLY, side_env  # noqa: E402
from sprt import play_game  # noqa: E402

# (name, FEN(won side = White), must_convert)
CASES = [
    ("KQvK",   "7k/8/8/8/8/8/8/KQ6 w - - 0 1", True),
    ("KRvK",   "7k/8/8/8/8/8/8/KR6 w - - 0 1", True),
    ("KPK",    "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1", True),
    ("KRPvK",  "8/8/8/3k4/8/8/4RP2/4K3 w - - 0 1", True),
    # quiet shuffle trap: won KRvK already in the drive phase (kings
    # close) — the old engine shuffles the rook a1-b1/c1 while the king
    # approaches; THREE same-position repeats = draw.
    ("KRvK-close", "6k1/8/8/8/8/8/1K6/R7 w - - 0 1", True),
    # KQvK where the queen can shuffle along the 2nd rank while the king
    # wanders (worst-case for root-level repetition avoidance: many
    # equivalent queen shuffles).
    ("KQvK-mid", "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1", True),
]


def _mirror_fen(fen: str) -> str:
    parts = fen.split()
    rows = parts[0].split("/")[::-1]
    flipped = []
    for row in rows:
        out = ""
        for ch in row:
            if ch.isalpha():
                out += ch.swapcase()
            else:
                out += ch
        flipped.append(out)
    new_side = "b" if parts[1] == "w" else "w"
    return "/".join(flipped) + " " + new_side + " " + " ".join(parts[2:])


def _keys_and_streaks(start_fen: str, moves: str, strong_is_white: bool) -> tuple:
    """Replay `moves` on a python-chess board from `start_fen`. Returns:
      - 2nd/3rd-occurrence ply positions (list of (key_occurrence, ply))
      - max shuffle streak of the strong side (same piece, <=4 target
        squares) already present before the draw risk materializes."""
    board = chess.Board(start_fen)
    seen = {}
    n2 = []
    n3 = []
    streak = 0
    max_streak = 0
    prev_from = None
    targets = set()
    for i, uci in enumerate(moves.split()):
        mv = chess.Move.from_uci(uci)
        board.push(mv)
        key = board._transposition_key()
        occ = seen.get(key, 0) + 1
        seen[key] = occ
        if occ == 2:
            n2.append(i + 1)
        elif occ == 3:
            n3.append(i + 1)
        # after push, it's the OTHER side to move: the move just played
        # belongs to the strong side iff the side now to move is not it
        just_played_strong = (board.turn != (chess.WHITE if strong_is_white
                                             else chess.BLACK))
        if just_played_strong:
            if mv.from_square == prev_from:
                targets.add(mv.to_square)
                if len(targets) <= 4:
                    streak += 1
                    if streak > max_streak:
                        max_streak = streak
                else:
                    streak = 1
                    targets = {mv.to_square}
            else:
                streak = 1
                targets = {mv.to_square}
            prev_from = mv.from_square
    return n2, n3, max_streak


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strong", default="hand:1111")
    ap.add_argument("--weak", default="hand:0000")
    ap.add_argument("--move-ms", type=int, default=300)
    ap.add_argument("--only", default="")
    ap.add_argument("--max-plies", type=int, default=MAX_PLY)
    args = ap.parse_args()

    s_cfg, s_gate = args.strong.split(":")
    w_cfg, w_gate = args.weak.split(":")

    def spawn(cfg, gate):
        env = side_env(f"{cfg}:{gate}", args.move_ms)
        return subprocess.Popen(
            [sys.executable, str(_HERE / "engine_side.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env)

    sp, wp = spawn(s_cfg, s_gate), spawn(w_cfg, w_gate)
    rng = random.Random(11)
    only = set(x.strip() for x in args.only.split(",") if x.strip())
    failures = 0
    try:
        for name, fen, must in CASES:
            if only and name not in only:
                continue
            for strong_white in (True, False):
                game_fen = fen if strong_white else _mirror_fen(fen)
                sides = {chess.WHITE: {"proc": (sp if strong_white else wp),
                                       "name": "strong" if strong_white
                                       else "weak"},
                         chess.BLACK: {"proc": (wp if strong_white else sp),
                                       "name": "weak" if strong_white
                                       else "strong"}}
                g = play_game(game_fen, sides, rng)
                res = g["result"]
                ok = (res == "1-0") if strong_white else (res == "0-1")
                n2, n3, streak = _keys_and_streaks(game_fen, g["moves"],
                                                   strong_white)
                tag = "WIN " if ok else ("LOSS" if res[-1] == "0" or
                                         res[-1] == "1" else "DRAW")
                rep = (f" 2x@{n2}" if n2 else " no2x") + \
                      (f" 3x@{n3} <== THREEFOLD" if n3 else "")
                print(f"{name:10s} strong-as-{'white' if strong_white else 'black':5s} "
                      f"ply={g['ply']:3d} {tag} streak={streak:2d}{rep}")
                if g["flags"]:
                    print("   FLAGS:", g["flags"])
                    failures += 1
                if must and not ok:
                    failures += 1
                if n3 and ok and res != "1/2-1/2":
                    # threefold before converting is the shuffle failure
                    print("   <== threefold encountered before conversion")
                    failures += 1
        return 1 if failures else 0
    finally:
        for p in (sp, wp):
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