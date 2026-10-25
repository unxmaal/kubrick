"""Measured grammar rules: statistics over shot-scale sequences, each against a reordering null."""

import numpy as np

from kubrick import scale

WIDE = (6, 7)  # LS, ELS


def scale_segments(labels: np.ndarray) -> list[list[int]]:
    """Runs of held scale collapsed to one entry each, split wherever a label is off the ordinal ladder or
    missing. A segment needs two shots to hold a transition. Same-scale cuts are invisible in these labels."""
    ladder = set(scale.ORDINAL)
    segs, cur, prev = [], [], None
    for v in labels.tolist():
        if v not in ladder:
            if len(cur) > 1:
                segs.append(cur)
            cur, prev = [], None
            continue
        if v != prev:
            cur.append(v)
        prev = v
    if len(cur) > 1:
        segs.append(cur)
    return segs


def _pairs(segs):
    return [(a, b) for s in segs for a, b in zip(s, s[1:])]


def wide_then_closer(segs: list[list[int]]) -> float:
    after_wide = [(a, b) for a, b in _pairs(segs) if a in WIDE]
    return float(np.mean([b < a for a, b in after_wide])) if after_wide else float("nan")


def one_step_share(segs: list[list[int]]) -> float:
    pairs = _pairs(segs)
    return float(np.mean([abs(b - a) == 1 for a, b in pairs])) if pairs else float("nan")


MEASURES = {"wide-then-closer": wide_then_closer, "one-step-scale-cuts": one_step_share}


def shuffled(segs: list[list[int]], rng) -> list[list[int]]:
    """The same shots in each segment, in a random order: keeps what a film uses, drops when it uses it."""
    return [list(rng.permutation(s)) for s in segs]


def compare(segs: list[list[int]], stat, draws: int = 200, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    observed = stat(segs)
    null = np.array([stat(shuffled(segs, rng)) for _ in range(draws)])
    null = null[~np.isnan(null)]
    mean = float(null.mean()) if len(null) else float("nan")
    return {"observed": observed, "null_mean": mean, "null_sd": float(null.std()) if len(null) else float("nan"),
            "above_null": bool(observed > mean) if not np.isnan(observed) and not np.isnan(mean) else None}
