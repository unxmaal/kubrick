import sys

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


def test_check_alignment_accepts_a_consistent_film():
    labels, change = planted(1.0, 40)
    assert scale.check_alignment(labels, change)["accepted"]


def test_check_alignment_rejects_halves_that_disagree():
    # a copy whose second half was re-cut: the second half's changes land 90 s later
    labels, change = planted(1.0, 0)
    marks = np.flatnonzero(labels[1:] != labels[:-1]) + 1
    late = marks[marks > len(labels) // 2]
    change[np.rint(late).astype(int)] -= 30
    change[np.rint(late + 90).astype(int)] += 30
    assert not scale.check_alignment(labels, change)["accepted"]


def test_check_alignment_accepts_a_partial_copy_on_the_part_it_holds():
    labels, change = planted(1.0, 12)
    change = change[: len(labels) // 2]  # disc 1 of 2
    assert scale.check_alignment(labels, change)["accepted"]


def test_check_alignment_rejects_a_mismatched_pair():
    labels, _ = planted(1.0, 0, seed=0)
    _, other = planted(1.0, 0, seed=7)
    assert not scale.check_alignment(labels, other)["accepted"]


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


def test_boost_uses_pose_features_when_image_features_are_noise():
    rng = np.random.default_rng(3)
    films = {}
    for i in range(3):
        y = rng.integers(1, 8, 500)
        films[f"f{i}"] = {"X": rng.normal(size=(500, 80)), "pose": np.eye(8)[y] + rng.normal(0, 0.2, (500, 8)), "y": y}
    with_pose = scale.evaluate(films, ["f0", "f1"], ["f2"], kind="boost")["f2"]["kappa_linear"]
    for f in films.values():
        del f["pose"]
    without = scale.evaluate(films, ["f0", "f1"], ["f2"], kind="boost")["f2"]["kappa_linear"]
    assert with_pose > 0.8 and without < 0.2


def test_evaluate_shuffles_training_labels_only():
    films = {f"f{i}": _film(i) for i in range(3)}
    r = scale.evaluate(films, ["f0", "f1"], ["f2"], shuffle=True)["f2"]
    assert r["n"] == 600


def test_evaluate_refuses_an_unknown_classifier():
    films = {f"f{i}": _film(i) for i in range(2)}
    with pytest.raises(ValueError, match="unknown classifier"):
        scale.evaluate(films, ["f0"], ["f1"], kind="svm")


def test_evaluate_ignores_unlabelled_seconds():
    films = {f"f{i}": _film(i) for i in range(2)}
    films["f1"]["y"][:100] = -1
    assert scale.evaluate(films, ["f0"], ["f1"])["f1"]["n"] == 500


def test_evaluate_refuses_films_with_different_feature_configurations():
    films = {f"f{i}": _film(i) for i in range(2)}
    films["f0"]["features"] = ("facebook/dinov2-small", 4)
    films["f1"]["features"] = ("facebook/dinov2-base", 4)
    with pytest.raises(ValueError, match="feature configurations"):
        scale.evaluate(films, ["f0"], ["f1"])


def test_embedder_grid_changes_the_features_it_returns():
    frame = np.random.default_rng(0).integers(0, 255, (224, 398, 3), dtype=np.uint8)
    plain = scale.Embedder(grid=0, device="cpu")([frame])
    gridded = scale.Embedder(grid=4, device="cpu")([frame])
    assert gridded.shape[1] == plain.shape[1] + 16 * plain.shape[1] // 2


def test_featurise_records_its_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(scale, "sample_frames", lambda path: iter([(0.0, np.zeros((224, 398, 3), np.uint8))]))
    out = tmp_path / "f.npz"
    scale.featurise("unused", out, grid=2)
    d = np.load(out)
    assert (str(d["model"]), int(d["grid"])) == (scale.EMBED_MODEL, 2)


macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision is macOS only")


@macos_only
def test_pose_features_on_an_empty_frame_are_zero_and_fixed_length():
    # negative control only: the positive side is checked on real film frames, which cannot ship here
    from kubrick import pose

    v = pose.features(np.full((224, 398, 3), 40, np.uint8))
    assert v.shape == (pose.N_FEATURES,)
    assert not v.any()


@macos_only
def test_pose_raises_when_vision_fails_rather_than_reporting_no_people(monkeypatch):
    from kubrick import pose

    class Failing:
        def performRequests_error_(self, *_):
            return False, "simulated"

    monkeypatch.setattr(pose, "_handler", lambda data: Failing())
    with pytest.raises(RuntimeError, match="Vision request failed"):
        pose.features(np.zeros((224, 398, 3), np.uint8))


def test_read_cinescale_marks_not_available(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text(",time,shotscale\n0,00:00:00,8\n1,00:00:01,9\n2,00:00:02,2\n", encoding="utf-8")
    assert scale.read_cinescale(p).tolist() == [8, -1, 2]
