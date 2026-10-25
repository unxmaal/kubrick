"""Is a shot-scale labeller good enough for #3's measured rules? Compare rule verdicts and effects computed
from its per-shot labels with those from human labels over the same shots."""

import math
from collections import Counter

import numpy as np

from kubrick import grammar


def shot_labels(per_second: np.ndarray, starts: list[int], n_frames: int, fps: float) -> list[int]:
    """Each shot's label: the most common labelled second inside it, or -1 if none is labelled."""
    bounds = [0, *starts, n_frames]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        seconds = range(int(a // fps), min(math.ceil(b / fps), len(per_second)))
        values = [int(per_second[s]) for s in seconds if per_second[s] >= 0]
        out.append(Counter(values).most_common(1)[0][0] if values else -1)
    return out


def effect(segs, stat, draws: int, seed: int) -> float:
    r = grammar.compare(segs, stat, draws, seed)
    return r["observed"] - r["null_mean"]


def effect_interval(segs, stat, draws: int = 100, boots: int = 200, seed: int = 0) -> tuple[float, float, float]:
    """(2.5th percentile, estimate, 97.5th percentile) of observed minus null, resampling segments."""
    rng = np.random.default_rng(seed)
    mid = effect(segs, stat, draws, seed)
    samples = [effect([segs[i] for i in rng.integers(0, len(segs), len(segs))], stat, draws, seed + k + 1)
               for k in range(boots)]
    samples = [s for s in samples if not math.isnan(s)]
    return float(np.percentile(samples, 2.5)), mid, float(np.percentile(samples, 97.5))


def check(human: list[int], predicted: list[int], draws: int = 100, boots: int = 200, seed: int = 0) -> dict:
    """Per measured rule: both verdicts, the human effect's interval, and whether the labeller is fit: the same
    verdict against the null, and a predicted effect inside the human interval."""
    hs, ps = grammar.scale_segments(np.array(human)), grammar.scale_segments(np.array(predicted))
    out = {}
    for rule, stat in grammar.MEASURES.items():
        h, p = grammar.compare(hs, stat, draws, seed), grammar.compare(ps, stat, draws, seed)
        lo, mid, hi = effect_interval(hs, stat, draws, boots, seed)
        pe = p["observed"] - p["null_mean"]
        out[rule] = {"human": h, "predicted": p, "human_effect": [lo, mid, hi], "predicted_effect": pe,
                     "fit": bool(h["above_null"] == p["above_null"] and lo <= pe <= hi)}
    return out
