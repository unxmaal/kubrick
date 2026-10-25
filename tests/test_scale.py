import numpy as np
import pytest

from kubrick import scale


def planted(speed, offset, n=3000, seed=0):
    """Labels with shot changes, and a picture-change signal with spikes where those changes land."""
    rng = np.random.default_rng(seed)
    labels = np.repeat(rng.integers(1, 8, 400), rng.integers(3, 15, 400))[:n]
    marks = np.flatnonzero(labels[1:] != labels[:-1]) + 1
    change = rng.uniform(0, 5, int(n * 1.1) + 700)
    ours = np.rint(marks * speed + offset).astype(int)
    change[ours[(ours > 0) & (ours < len(change))]] += 30
    return labels, change


@pytest.mark.parametrize("speed,offset", [(1.0, 0), (24 / 25, 0), (1.0, 356), (1.0, -120)])
def test_align_recovers_a_planted_speed_and_offset(speed, offset):
    labels, change = planted(speed, offset)
    a = scale.align(labels, change)
    assert (a["speed"], a["offset"]) == (speed, offset)
    assert a["z"] > 10


def test_align_finds_nothing_in_noise():
    labels, _ = planted(1.0, 0)
    change = np.random.default_rng(1).uniform(0, 5, 4000)
    assert scale.align(labels, change)["z"] < 6


def test_map_labels_applies_speed_and_offset():
    labels = np.array([1, 2, 3, 4])
    assert scale.map_labels(labels, 8, 1.0, 2).tolist() == [-1, -1, 1, 2, 3, 4, -1, -1]
    assert scale.map_labels(labels, 3, 1.0, -1).tolist() == [2, 3, 4]


def _film(seed, n=600, noise=0.3):
    rng = np.random.default_rng(seed)
    y = rng.integers(1, 8, n)
    X = np.eye(8)[y] + rng.normal(0, noise, (n, 8))
    return {"X": X, "y": y}


def test_evaluate_scores_a_learnable_signal_far_above_every_shuffled_control():
    # a probe trained on shuffled labels can learn a consistent wrong class mapping, which weighted
    # kappa scores well below zero, so the control is "real clears every shuffle", not "shuffle is 0"
    films = {f"f{i}": _film(i) for i in range(4)}
    real = scale.evaluate(films, ["f0", "f1"], ["f2", "f3"])
    controls = [scale.evaluate(films, ["f0", "f1"], ["f2", "f3"], shuffle=True, seed=s) for s in range(5)]
    ceiling = max(c[n]["kappa_linear"] for c in controls for n in c)
    assert all(r["kappa_linear"] > 0.9 for r in real.values())
    assert ceiling < 0.5


def test_evaluate_ignores_unlabelled_seconds():
    films = {f"f{i}": _film(i) for i in range(2)}
    films["f1"]["y"][:100] = -1
    assert scale.evaluate(films, ["f0"], ["f1"])["f1"]["n"] == 500


def test_read_cinescale_marks_not_available(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text(",time,shotscale\n0,00:00:00,8\n1,00:00:01,9\n2,00:00:02,2\n", encoding="utf-8")
    assert scale.read_cinescale(p).tolist() == [8, -1, 2]
