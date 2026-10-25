import json

import pytest

from kubrick import breakdown, cuts, synth, taxonomy

A = "lavfi:testsrc2=size=640x360:rate=24"
B = "lavfi:smptebars=size=640x360:rate=24"
C = "lavfi:mandelbrot=size=640x360:rate=24"


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    out = tmp_path_factory.mktemp("clip") / "k.mp4"
    spec = synth.Spec.from_dict({"segments": [{"source": s, "frames": 48} for s in (A, B, C)],
                                 "joins": [{"kind": "cut"}, {"kind": "dissolve", "frames": 24}]})
    return out, synth.build(spec, out)


def test_transitions_carry_their_kind_and_span(clip):
    path, truth = clip
    found = cuts.transitions(str(path))
    assert [t["kind"] for t in found] == ["cut", "gradual"]
    dissolve = truth["transitions"][1]
    assert found[1]["first"] <= dissolve["last"] and found[1]["last"] >= dissolve["first"]


def test_shots_tile_the_film_and_name_the_transition_into_each():
    shots = breakdown.shots_from_transitions(
        [{"at": 48, "kind": "cut", "first": 47, "last": 47}, {"at": 90, "kind": "gradual", "first": 80, "last": 100}],
        n_frames=150)
    assert [(s["in"], s["out"], s["into"]) for s in shots] == [(0, 47, "start"), (48, 89, "cut"), (90, 149, "gradual")]


def test_breakdown_rows_for_a_known_clip(clip, tmp_path):
    path, _ = clip
    rows = breakdown.breakdown(str(path), tmp_path)
    assert [r["into"] for r in rows] == ["start", "cut", "gradual"]
    for r in rows:
        assert r["digest"] == rows[0]["digest"] and len(r["digest"]) == 64
        assert r["duration_s"] == pytest.approx((r["out"] - r["in"] + 1) / r["fps"])
        assert len(r["grabs"]) == 3 and all((tmp_path / g).is_file() for g in r["grabs"])
        assert r["movement"] in taxonomy.labels("movement") or r["movement"].startswith("unknown:")
        assert r["scale"] == "unknown:no-model" and r["scale_estimate"] is True
        assert {"kubrick", "transnetv2-pytorch", "opencv"} <= set(r["versions"])
        assert r["settings"]["transnet"] == cuts.DETECTORS["transnet"].default


def test_breakdown_writes_jsonl_that_reads_back(clip, tmp_path):
    path, _ = clip
    rows = breakdown.breakdown(str(path), tmp_path)
    breakdown.write_jsonl(rows, tmp_path / "rows.jsonl")
    back = [json.loads(line) for line in (tmp_path / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert back == rows


def _fake_films(dims, seed=0):
    import numpy as np

    rng = np.random.default_rng(seed)
    films = {}
    for i in range(2):
        y = rng.integers(0, 9, 300)
        films[f"f{i}"] = {"X": rng.normal(size=(300, dims)), "pose": rng.normal(size=(300, 17)), "y": y,
                          "features": ("facebook/dinov2-small", 0)}
    return films


def test_a_saved_scale_model_labels_every_shot_from_the_taxonomy(clip, tmp_path):
    from kubrick import scale

    path, _ = clip
    model = scale.train_model(_fake_films(768))
    scale.save_model(model, tmp_path / "scale.joblib")
    rows = breakdown.breakdown(str(path), tmp_path / "grabs", scale_model=tmp_path / "scale.joblib")
    for r in rows:
        assert r["scale"] in taxonomy.labels("scale")
        assert r["scale_estimate"] is True
        assert r["scale_model"]["trained_on"] == ["f0", "f1"]


def test_the_scale_model_sees_frames_shaped_like_its_training_frames(tmp_path, monkeypatch):
    # training frames come from scale.sample_frames, which keeps the film's display aspect;
    # a scope film must not reach the model squeezed to 16:9
    from kubrick import scale

    wide = tmp_path / "scope.mp4"
    spec = synth.Spec.from_dict({"segments": [{"source": A, "frames": 30}], "joins": [], "width": 860, "height": 360})
    synth.build(spec, wide)
    trained_shape = next(scale.sample_frames(str(wide)))[1].shape
    seen = []
    monkeypatch.setattr(scale, "predict_frame", lambda model, frame: seen.append(frame.shape) or "MS")
    monkeypatch.setattr(scale, "load_model", lambda p: {"features": ("m", 0), "kind": "boost", "trained_on": []})
    breakdown.breakdown(str(wide), tmp_path / "g", scale_model=tmp_path / "unused")
    assert seen and all(s == trained_shape for s in seen)


def test_cli_breakdown_writes_rows_and_grabs(clip, tmp_path):
    from kubrick.cli import main

    path, _ = clip
    assert main(["breakdown", str(path), str(tmp_path / "out")]) == 0
    rows = [json.loads(x) for x in (tmp_path / "out" / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3 and all((tmp_path / "out" / g).is_file() for r in rows for g in r["grabs"])


def test_cli_scale_train_saves_a_model_from_aligned_films_only(tmp_path, monkeypatch):
    from kubrick import scale
    from kubrick.cli import main

    films = _fake_films(768)
    films["f0"]["align"] = {"accepted": True}
    films["f1"]["align"] = {"accepted": False}
    by_path = {"a.npz": films["f0"], "b.npz": films["f1"]}
    monkeypatch.setattr(scale, "load_film", lambda npz, csv: dict(by_path[npz.name]))
    out = tmp_path / "m.joblib"
    assert main(["scale-train", "a.npz:a.csv", "b.npz:b.csv", "--out", str(out)]) == 0
    assert scale.load_model(out)["trained_on"] == ["a"]


def test_train_model_refuses_mixed_feature_configurations():
    from kubrick import scale

    films = _fake_films(768)
    films["f1"]["features"] = ("facebook/dinov2-base", 0)
    with pytest.raises(ValueError, match="feature configurations"):
        scale.train_model(films)


def test_digest_reads_the_file_not_its_name(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    a.write_bytes(b"x" * 1000)
    b.write_bytes(b"x" * 1000)
    assert breakdown.digest(a) == breakdown.digest(b)
    b.write_bytes(b"x" * 999 + b"y")
    assert breakdown.digest(a) != breakdown.digest(b)
