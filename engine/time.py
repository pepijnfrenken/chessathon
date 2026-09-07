"""Chessathon engine Phase 1b — time management (pure Python, cold path).

Budget model (our implementation; research 01 section 4 informed the
shape): spend `remaining/45 + increment` per move, clamped to [50ms,
45 s] and to never commit more than what is left minus 100 ms. Because
every move spends ~R/45 of what remains, the clock decays geometrically
(44/45 per move) and can never run out on any game length — the never-flag
property holds at every clock shape, from the 120 s competition clock
(~3.2 s/move early) down to 2 s + 0.1 s harness clocks (~144 ms/move).

`get_move` only sees total remaining time, so the increment is assumed
(agent._INC_MS, 500 ms for the competition clock).
"""


def budget_ms(remaining_ms: int, inc_ms: int = 500) -> int:
    """Milliseconds to spend on the current move given the clock shape."""
    if remaining_ms <= 0:
        return 50
    b = remaining_ms // 45 + inc_ms
    if b > 45000:
        b = 45000
    if b < 50:
        b = 50
    if b > remaining_ms - 100:
        b = max(50, remaining_ms - 100)
    return int(b)