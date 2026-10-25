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
    """Each segment's shots in a random order, seen the way the labels see a film: two same-scale shots in
    a row merge into one run. Without the merge the null holds sequences the data can never show."""
    out = []
    for s in segs:
        merged = []
        for v in rng.permutation(s).tolist():
            if not merged or merged[-1] != v:
                merged.append(v)
        if len(merged) > 1:
            out.append(merged)
    return out


MIN_OTHER_DIRECTORS = 2  # a rule derived on one director must replicate on at least this many others


def replicate(rule_id: str, labels_root, derive: str = "Scorsese", draws: int = 200, seed: int = 0) -> dict:
    """Run a measured rule's statistic on every film under labels_root/<director>/*.csv against its own
    reordering null. A director replicates when most of its films beat their null. The rule holds when the
    deriving director and at least MIN_OTHER_DIRECTORS others replicate."""
    from pathlib import Path

    stat = MEASURES[rule_id]
    directors = {}
    for d in sorted(p for p in Path(labels_root).iterdir() if p.is_dir()):
        results = [compare(scale_segments(scale.read_cinescale(f)), stat, draws, seed)
                   for f in sorted(d.glob("*.csv"))]
        judged = [r for r in results if r["above_null"] is not None]
        above = sum(r["above_null"] for r in judged)
        directors[d.name] = {
            "films": len(judged), "above_null": above, "replicates": bool(judged) and above > len(judged) / 2,
            "observed_mean": float(np.nanmean([r["observed"] for r in judged])) if judged else float("nan"),
            "null_mean": float(np.nanmean([r["null_mean"] for r in judged])) if judged else float("nan")}
    others = sum(v["replicates"] for k, v in directors.items() if k != derive)
    holds = derive in directors and directors[derive]["replicates"] and others >= MIN_OTHER_DIRECTORS
    return {"rule": rule_id, "derive": derive, "directors": directors, "other_directors_replicating": others,
            "verdict": "holds" if holds else "does not hold"}


def compare(segs: list[list[int]], stat, draws: int = 200, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    observed = stat(segs)
    null = np.array([stat(shuffled(segs, rng)) for _ in range(draws)])
    null = null[~np.isnan(null)]
    mean = float(null.mean()) if len(null) else float("nan")
    return {"observed": observed, "null_mean": mean, "null_sd": float(null.std()) if len(null) else float("nan"),
            "above_null": bool(observed > mean) if not np.isnan(observed) and not np.isnan(mean) else None}
