"""SEE unit battery (dev tool, NOT shipped).

Validates search.see() against an INDEPENDENT brute-force oracle of the
standard single-square exchange model:

  oracle = pseudo-legal minimax over capture moves on the TARGET square
  only (the classic "swap value": pins ignored, like SEE; x-ray handled
  naturally by re-generating captures after each make; a king recaptures
  only into a square its opponent does not attack, and a king is never
  itself recaptured). Promotions and EP are excluded from chains in both
  models (see() documents both as approximations).

The battery covers pawn/knight/bishop/rook/queen chains, LVA ordering,
x-ray revelation, queen-sacrifice arithmetic, and pin-ignoring — plus one
INFORMATION-ONLY EP case.

Run: /tmp/chessbench/bin/python tools/see_unit.py
Exit 0 iff every exact case matches; prints a per-case table.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import board as B   # noqa: E402
from engine import search as S  # noqa: E402

_VICTIM = {1: 100, 2: 320, 3: 330, 4: 500, 5: 900, 6: 20000}
_MBUF = np.zeros(256, dtype=np.int32)


def uci_sq(u: str) -> int:
    """uci square -> 0x88 index."""
    return (int(u[1]) - 1) * 16 + (ord(u[0]) - ord("a"))


def _make(st, mv):
    captured = st['squares'][0][B.m_to(mv)]
    prev = (st['castle'][0], st['ep'][0], st['halfmove'][0], st['key'][0])
    B.make_move_apply(st, mv)
    return captured, prev


def _undo(st, mv, captured, prev):
    B.unmake_move(st, mv, captured, prev[0], prev[1], prev[2], prev[3])


def best_reply(st, target, depth=0):
    """Max net gain for the side to move continuing the exchange ON the
    target square only (stand pat = 0 ends the chain)."""
    if depth > 12:
        return 0
    sqr = st['squares'][0]
    if abs(sqr[target]) == B.KING:
        return 0                     # a king is never recaptured
    n = B.gen_moves(st, _MBUF, True)
    # snapshot the target captures BEFORE any recursion (recursion
    # reuses _MBUF — reading it back in the loop would see clobbered data)
    caps = []
    for i in range(n):
        mv = _MBUF[i]
        if B.m_to(mv) == target and B.m_flags(mv) not in (B.F_EP,
                                                          B.F_PROMOCAP):
            caps.append((mv, abs(sqr[B.m_from(mv)])))
    best = 0
    for mv, mover in caps:
        victim = abs(sqr[target])    # what this capture wins (before make)
        captured, prev = _make(st, mv)
        king_ok = True
        if mover == B.KING:
            # after the king lands, the ENEMY (side now to move) must not
            # attack the target square
            if B.attacked(st, B.m_to(mv), st['side'][0]):
                king_ok = False
        if king_ok:
            gain = _VICTIM[victim] - best_reply(st, target, depth + 1)
            if gain > best:
                best = gain
        _undo(st, mv, captured, prev)
    return best


def oracle(fen: str, frm_u: str, to_u: str) -> int:
    """Brute-force swap value of the capture frm_u x to_u in `fen`."""
    st = B.parse_fen(fen)
    frm, to = uci_sq(frm_u), uci_sq(to_u)
    mv = B.make_move(frm, to, B.F_CAPTURE, 0)   # battery: non-EP, non-promo
    victim = abs(st['squares'][0][to])
    captured, prev = _make(st, mv)
    val = _VICTIM[victim] - best_reply(st, to)
    _undo(st, mv, captured, prev)
    return val


# (label, fen, from, to, expected, note) — expected values hand-derived
# from the single-square chain arithmetic; the oracle independently
# recomputes them and see() must match both.
CASES = [
    ("pawn-takes-clean",
     "8/8/8/8/3p4/4P3/8/K6k w - - 0 1", "e3", "d4", 100,
     "undefended pawn: +100"),
    ("pawn-takes-defended",
     "8/8/8/2p5/3p4/4P3/8/K6k w - - 0 1", "e3", "d4", 0,
     "cxd4 recapture: even"),
    ("queen-loses-to-rook",
     "8/8/8/8/3p4/8/3r4/Q3K2k w - - 0 1", "a1", "d4", -800,
     "Qxd4 Rxd4: pawn for queen"),
    ("lva-knight-before-rook",
     "8/8/8/8/3p4/8/2nr4/Q3K2k w - - 0 1", "a1", "d4", -800,
     "N c2 (LVA) recaptures, rook idle: same -800"),
    ("deep-chain-xray",
     "8/8/8/8/3p4/8/2nr4/Q2R2Kk w - - 0 1", "a1", "d4", -800,
     "Qxd4 Nc2xd4; the d2 rook blocks Rd1's x-ray the whole chain: "
     "100-900"),
    ("rook-xray-behind",
     "3r4/8/8/5N2/3p4/8/8/K6k w - - 0 1", "f5", "d4", -220,
     "Nxd4, rook d8 revealed through d5-d7: 100-320"),
    ("bishop-trade-loses-10",
     "8/8/8/5n2/3n4/4B3/8/K6k w - - 0 1", "e3", "d4", -10,
     "Bxd4 Nf5xd4: 320-330"),
    ("pawn-takes-queen",
     "8/8/8/8/3q4/4P3/8/K6k w - - 0 1", "e3", "d4", 900,
     "undefended queen: +900"),
    ("pinned-rook-ignored",
     "4r2k/8/8/8/8/8/3pR3/4K3 w - - 0 1", "e2", "d2", 100,
     "Rxd2 'illegal' by the e8-rook pin; both models ignore pins AND "
     "nothing black attacks d2: +100"),
    ("king-recapture-undefended",
     "8/8/8/8/3p4/8/8/3K3k w - - 0 1", "d1", "d4", 100,
     "Kxd4 clean: +100, chain ends"),
    ("king-chain-recapture",
     "8/8/8/4k3/3p4/8/8/3N3K w - - 0 1", "d1", "d4", -220,
     "Nxd4, black Kxd4: 100-320, chain ends at the king"),
    ("rook-chain-lva",
     "8/8/8/3r4/3p4/8/3r4/3R2Kk w - - 0 1", "d1", "d4", -400,
     "Rxd4, any of three black rooks recaptures: 100-500"),
    ("queen-vs-knight-pawn",
     "8/8/4n3/8/3p4/8/8/Q3K2k w - - 0 1", "a1", "d4", -800,
     "Qxd4 Nxd4: pawn for queen; no white recapture"),
    ("knight-equal-trade",
     "8/8/4n3/8/3n4/4N3/8/K6k w - - 0 1", "e3", "d4", 0,
     "Nxd4 Ne6xd4: even trade"),
]


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"# SEE unit battery: {len(CASES)} cases, independent oracle "
          f"(pseudo-legal single-square swap)", flush=True)
    bad = 0
    for label, fen, frm, to, exp, note in CASES:
        if only and label != only:
            continue
        v = oracle(fen, frm, to)
        st = B.parse_fen(fen)
        sv = int(S.see(st, uci_sq(frm), uci_sq(to)))
        ok = v == sv == exp
        bad += 0 if ok else 1
        print(f"  {'OK ' if ok else 'FAIL'} {label:24s} oracle={v:+5d} "
              f"see={sv:+5d} exp={exp:+5d}  ({note})", flush=True)

    # informational EP case: see() documents the approximation (pawn
    # victim, landing-square geometry) — no exact assert possible.
    st = B.parse_fen("8/8/8/3pP3/8/8/8/K6k w - d6 0 1")
    print(f"  NOTE EP e5xd6: see={int(S.see(st, uci_sq('e5'), uci_sq('d6')))}"
          f" (documented approximation: pawn victim, landing-square "
          f"geometry)", flush=True)
    print(f"\n== result: {'ALL PASS' if bad == 0 else f'{bad} FAILURES'}",
          flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())