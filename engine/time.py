"""Chessathon engine Phase 1b — time management (pure Python, cold path).

Budget model (research 01 section 4, our implementation):
  reserve  = min(15s + 30*increment, remaining/2)   <- never-flag floor
  budget   = (remaining - reserve)/30 + increment   <- moves_to_go ~30
  clamps: >= 300ms (overhead floor), <= 45s (soft cap), and never spend
  so much that < 2s would remain.
"""


def budget_ms(remaining_ms: int, inc_ms: int = 500) -> int:
    """Milliseconds to spend on the current move given the clock shape."""
    if remaining_ms <= 0:
        return 50
    reserve = min(15000 + 30 * inc_ms, remaining_ms // 2)
    usable = remaining_ms - reserve
    if usable <= 0:                      # clock is nearly gone
        return max(200, remaining_ms - 1500)
    budget = usable // 30 + inc_ms
    if budget > 45000:
        budget = 45000
    if budget < 300:
        budget = 300
    if remaining_ms > 4000:              # never leave < 2s behind
        cap = remaining_ms - 2000
        if budget > cap:
            budget = cap
    # absolute safety: never commit more than we have minus ~150ms slack
    if budget > remaining_ms - 150:
        budget = max(50, remaining_ms - 150)
    return int(budget)