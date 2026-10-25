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


BLOCK = 20  # shots per resampling block; long enough to keep runs of cuts, short enough for many blocks


def difference_interval(human: list[int], predicted: list[int], stat, draws: int = 100, boots: int = 200,
                        seed: int = 0, block: int = BLOCK) -> tuple[float, float, float]:
    """Paired block bootstrap of (predicted effect - human effect) over the same shots: resample blocks of
    shots, score both label sets on the same blocks with the same null draws. Returns the 2.5th percentile,
    median and 97.5th percentile. Resampling shots, not segments, works for a film that is one segment."""
    h, p = np.array(human), np.array(predicted)
    starts = list(range(0, len(h), block))
    rng = np.random.default_rng(seed)
    diffs = []
    for k in range(boots):
        pick = rng.integers(0, len(starts), len(starts))
        hb = np.concatenate([np.append(h[starts[i]:starts[i] + block], -1) for i in pick])
        pb = np.concatenate([np.append(p[starts[i]:starts[i] + block], -1) for i in pick])
        d = effect(grammar.scale_segments(pb), stat, draws, seed + k + 1) \
            - effect(grammar.scale_segments(hb), stat, draws, seed + k + 1)
        if not math.isnan(d):
            diffs.append(d)
    return float(np.percentile(diffs, 2.5)), float(np.median(diffs)), float(np.percentile(diffs, 97.5))


def leave_one_out(films: dict[str, dict], cuts: dict[str, dict], kind: str = "boost", draws: int = 100,
                  boots: int = 200, seed: int = 0) -> dict[str, dict]:
    """For each film: fit the labeller on the others (scale._fit, the path evaluate measures), label every
    second that has a human label, and check fitness per rule over the film's own shots."""
    from kubrick import scale

    out = {}
    for test in films:
        train = [n for n in films if n != test]
        scale._one_configuration(films, list(films))
        clf, pca = scale._fit(films, train, kind)
        f = films[test]
        m = f["y"] >= 0
        P = f["pose"] if "pose" in f else np.zeros((len(f["y"]), 0))
        pred = np.full(len(f["y"]), -1)
        pred[m] = clf.predict(scale._features(pca, f["X"][m], P[m]))
        c = cuts[test]
        starts = [t["at"] for t in c["transitions"]]
        human = shot_labels(f["y"], starts, c["frames"], c["fps"])
        predicted = shot_labels(pred, starts, c["frames"], c["fps"])
        out[test] = check(human, predicted, draws, boots, seed)
    return out


def check(human: list[int], predicted: list[int], draws: int = 100, boots: int = 200, seed: int = 0) -> dict:
    """Per measured rule: both verdicts, the paired interval of (predicted - human) effect, and whether the
    labeller is fit: the same verdict against the null, and an interval that contains zero."""
    hs, ps = grammar.scale_segments(np.array(human)), grammar.scale_segments(np.array(predicted))
    out = {}
    for rule, stat in grammar.MEASURES.items():
        h, p = grammar.compare(hs, stat, draws, seed), grammar.compare(ps, stat, draws, seed)
        lo, mid, hi = difference_interval(human, predicted, stat, draws, boots, seed)
        out[rule] = {"human": h, "predicted": p, "difference": [lo, mid, hi],
                     "fit": bool(h["above_null"] == p["above_null"] and lo <= 0 <= hi)}
    return out
