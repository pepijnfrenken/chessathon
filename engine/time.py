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
    # q5-tm1: late-game floor. The decay model above leaves a large
    # surplus unused (median 36% of the clock left over 53 rated games;
    # 25% over games >= 50 moves; zero games below 10 s) while the
    # r92/r100 loss class shows the razor phase (moves ~30-65) needs
    # ~3 s+ per move: r92 post-mortem (blunder band <= 2 s, avoided
    # >= 3 s) and the r100 m50 depth sweep (losing family <= depth 10,
    # drawing family >= 11). Floor the per-move budget at 3 s once the
    # remaining clock can afford it; never more than 1/10 of what is
    # left, so the geometric decay and the never-flag property stand.
    floor = 3000
    cap = remaining_ms // 10
    if cap < floor:
        floor = cap
    if b < floor:
        b = floor
    # q5-tm1b: tail-safe reserve. tm1 alone drains long games (bout: end
    # clocks 1-21 s vs v9k's 4-60 s, minima 1.0 s at 300 plies) because it
    # keeps spending ~R//10 into the tail. Cap the spend so the clock has
    # a stable point once the increment is counted: spend <= max(250,
    # (R - 5000) // 8) -> below R = 9 s each move nets +500 ms, at
    # R = 9 s spend = 500 ms = the increment; above, the clock relaxes
    # back down. Binds only when (R - 5000)/8 < 3000 i.e. R < 29 s, so
    # every razor-phase budget (R >= 30 s) is untouched.
    tail = (remaining_ms - 5000) // 8
    if tail < 250:
        tail = 250
    if b > tail:
        b = tail
    if b > 45000:
        b = 45000
    if b < 50:
        b = 50
    if b > remaining_ms - 100:
        b = max(50, remaining_ms - 100)
    return int(b)