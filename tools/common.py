"""Shared dev-harness bits: opening positions + game adjudication.

DEV TOOL ONLY (never shipped in agent.zip). Imported by tools/local_game.py,
tools/sprt.py and the training-data generator. Deliberately does NOT import
agent or engine (those pull a 30 s numba warmup); sprt/texel tools import
this directly.

Openings are written by hand (our own), 10 varied: classic, closed, sharp,
flank and gambit lines. Each is a short move sequence from the start
position producing a distinct middlegame-ish FEN.
"""

import os

import chess

_OPENING_MOVES = [
    [],                                                  # start position
    ["e2e4", "e7e5", "g1f3", "b8c6"],                    # Ruy-ish
    ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6"],    # QGD
    ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"],    # Italian
    ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4",
     "f3d4", "g8f6"],                                    # Sicilian Najdorf-ish
    ["e2e4", "e7e6", "d2d4", "d7d5", "e4e5", "c7c5"],    # French
    ["e2e4", "c7c6", "d2d4", "d7d5", "e4d5", "c6d5"],    # Caro-Kann exchange
    ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6",
     "g1f3", "c7c5"],                                    # Tarrasch-ish
    ["g1f3", "d7d5", "d2d4", "g8f6", "c2c4", "e7e6",
     "b1c3", "f8e7"],                                    # QID-ish/London-ish
    ["c2c4", "e7e5", "b1c3", "g8f6", "g2g3", "f8b4",     # English
     "f1g2", "e8g8"],
    ["e2e4", "d7d5", "e4d5", "g8f6", "c2c4", "c7c6"],    # Scandinavian-ish
]


def _build_fens() -> list[str]:
    fens = []
    for moves in _OPENING_MOVES:
        board = chess.Board()
        for uci in moves:
            mv = chess.Move.from_uci(uci)
            assert mv in board.legal_moves, (moves, uci)
            board.push(mv)
        fens.append(board.fen())
    return fens


OPENING_FENS = _build_fens()

VICTIM = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}

MAX_PLY = 300


def side_env(spec: str, move_ms: int) -> dict:
    """Subprocess env for one engine_side config. `spec` is
    `config:gate[:searchflags]` where searchflags is a comma-separated
    list of search-feature toggles (empty/absent = all on):
        nolmr    -> CHESSATHON_LMR=0          (disable late move reduction)
        nulldeep -> CHESSATHON_NULL_DEEP=1    (deepen null reduction at
                   depth >= 6 to R=3 — the P4 A/B probe)
        see      -> CHESSATHON_SEE=1           (SEE capture ordering in
                   qsearch — the P1 A/B probe)
        seeprune -> CHESSATHON_SEEPRUNE=1      (prune SEE<0 qsearch
                   captures — the P1 pruning half)
        compclamp -> CHESSATHON_COMPCLAMP=1    (P8 compensation-aware
                   eval clamp — BUILD.md "P8")
    Used by sprt.py / gate_match.py so side-A and side-B can differ in
    the SEARCH (not just the eval) for feature gates."""
    parts = spec.split(":")
    cfg, gate = parts[0], parts[1]
    search = parts[2] if len(parts) > 2 else ""
    env = dict(os.environ)
    env["CHESSATHON_EVAL_CONFIG"] = cfg
    env["CHESSATHON_EVAL_GATE"] = gate
    env["CHESSATHON_MOVE_BUDGET_MS"] = str(move_ms)
    toggles = set(t for t in search.split(",") if t)
    env["CHESSATHON_LMR"] = "0" if "nolmr" in toggles else "1"
    env["CHESSATHON_NULL_DEEP"] = "1" if "nulldeep" in toggles else "0"
    env["CHESSATHON_SEE"] = "1" if "see" in toggles else "0"
    env["CHESSATHON_SEEPRUNE"] = "1" if "seeprune" in toggles else "0"
    env["CHESSATHON_COMPCLAMP"] = "1" if "compclamp" in toggles else "0"
    return env


def adjudicate(board: chess.Board, ply: int) -> str:
    """Result string for a capped/ended game: real result, or the
    300-ply material cap (rook-lead or more with mating potential is a
    win, else a draw) — our own adjudication rule."""
    if board.is_game_over():
        return board.result(claim_draw=True)
    if ply >= MAX_PLY:
        mat_white = sum(VICTIM[p.piece_type]
                        for p in board.piece_map().values()
                        if p.color == chess.WHITE)
        mat_black = sum(VICTIM[p.piece_type]
                        for p in board.piece_map().values()
                        if p.color == chess.BLACK)
        diff = mat_white - mat_black
        return "1-0" if diff >= 500 else ("0-1" if diff <= -500
                                          else "1/2-1/2")
    return "1/2-1/2"  # should not happen: caller checks game over first