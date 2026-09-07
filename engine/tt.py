"""Chessathon engine Phase 1b — transposition table.

Packed numpy arrays (NOT dicts — dict costs ~100-200 MB per million
entries), 16 bytes/entry, default 2^22 = 4.2M entries = 64 MB.

Entry layout (one uint64 "val" per key):
  [move:20][score+32000:16][depth:8][bound:2] = 46 bits
The key (uint64) lives in a parallel array; an entry is empty when its
key is 0. Two candidate slots per position (independent hash functions),
depth-preferred replacement.

Mate scores are stored mate-distance-adjusted at the *node* and restored
at the *node* (standard MATE-ply bookkeeping) so stored mate distances are
intrinsic to the position, not the search path. Never store draw scores
(0) or timeout sentinels — callers filter those.
"""

import numpy as np

from numba import njit

BOUND_NONE = 0
BOUND_LOWER = 1     # fail-high: true score >= stored
BOUND_UPPER = 2     # fail-low: true score <= stored
BOUND_EXACT = 3

# bits per entry (packing constants)
_MOVE_BITS = 20
_SCORE_OFFSET = 32000
_SCORE_BITS = 16
_DEPTH_BITS = 8
_BOUND_BITS = 2


def make(num_entries: int = 1 << 22):
    """Allocate a fresh table: (keys, vals) uint64 arrays."""
    return (np.zeros(num_entries, dtype=np.uint64),
            np.zeros(num_entries, dtype=np.uint64))


@njit(inline="always")
def _idx(keys, key, shift: int, mask):
    return int((key >> shift) & mask)


@njit
def tt_probe(keys, vals, mask, key, ply):
    """Return (hit, bound, score, depth, move) for `key`.

    `key` must be a non-zero position key. Score is converted back from
    MATE-ply storage using the node ply. Bound BOUND_NONE means no hit.
    """
    idx = int(key & mask)
    if keys[idx] == key:
        v = vals[idx]
        move = int(v & ((1 << _MOVE_BITS) - 1))
        score = int((v >> _MOVE_BITS) & ((1 << _SCORE_BITS) - 1)) - _SCORE_OFFSET
        depth = int((v >> (_MOVE_BITS + _SCORE_BITS)) & 0xFF)
        bound = int((v >> (_MOVE_BITS + _SCORE_BITS + _DEPTH_BITS)) & 3)
        if score > 29000:
            score -= ply
        elif score < -29000:
            score += ply
        return True, bound, score, depth, move
    idx = _idx(keys, key, 22, mask)
    if keys[idx] == key:
        v = vals[idx]
        move = int(v & ((1 << _MOVE_BITS) - 1))
        score = int((v >> _MOVE_BITS) & ((1 << _SCORE_BITS) - 1)) - _SCORE_OFFSET
        depth = int((v >> (_MOVE_BITS + _SCORE_BITS)) & 0xFF)
        bound = int((v >> (_MOVE_BITS + _SCORE_BITS + _DEPTH_BITS)) & 3)
        if score > 29000:
            score -= ply
        elif score < -29000:
            score += ply
        return True, bound, score, depth, move
    return False, BOUND_NONE, 0, 0, 0


@njit
def tt_store(keys, vals, mask, key, ply, depth, bound, score, move):
    """Store (or replace) an entry for `key`. Depth-preferred across the
    two candidate slots. `score` may be a mate score — stored MATE-ply
    adjusted with the node ply."""
    if score > 29000:
        score += ply
    elif score < -29000:
        score -= ply
    packed = (int(move)
              | ((score + _SCORE_OFFSET) << _MOVE_BITS)
              | (int(depth) << (_MOVE_BITS + _SCORE_BITS))
              | (int(bound) << (_MOVE_BITS + _SCORE_BITS + _DEPTH_BITS)))
    idx0 = int(key & mask)
    idx1 = _idx(keys, key, 22, mask)

    if keys[idx0] == key or keys[idx0] == 0:
        keys[idx0] = key
        vals[idx0] = packed
        return
    if keys[idx1] == key or keys[idx1] == 0:
        keys[idx1] = key
        vals[idx1] = packed
        return
    d0 = int((vals[idx0] >> (_MOVE_BITS + _SCORE_BITS)) & 0xFF)
    d1 = int((vals[idx1] >> (_MOVE_BITS + _SCORE_BITS)) & 0xFF)
    if d1 < d0:
        keys[idx1] = key
        vals[idx1] = packed
    else:
        keys[idx0] = key
        vals[idx0] = packed


@njit
def tt_clear(keys):
    keys[:] = 0