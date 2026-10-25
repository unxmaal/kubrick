import subprocess

import numpy as np
import pytest
import torch

from kubrick import finetune, fitness


def video(path, levels):
    # one second per level, each second a flat grey of that level
    parts = []
    for i, v in enumerate(levels):
        parts += ["-f", "lavfi", "-i", f"color=c=0x{v:02x}{v:02x}{v:02x}:s=320x180:r=24:d=1"]
    concat = "".join(f"[{i}:v]" for i in range(len(levels))) + f"concat=n={len(levels)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *parts, "-filter_complex", concat, "-map", "[v]",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def test_frames_are_one_per_second_square_and_in_order(tmp_path):
    levels = [20, 90, 160, 230]
    video(tmp_path / "v.mp4", levels)
    frames = finetune.frames_at(str(tmp_path / "v.mp4"), size=32)
    assert frames.shape == (4, 32, 32, 3) and frames.dtype == np.uint8
    assert np.allclose(frames.reshape(4, -1).mean(axis=1), levels, atol=6)


class Tiny(torch.nn.Module):
    """Stands in for DINOv2: a few conv tokens, shaped like last_hidden_state."""

    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(3, 16, 8, stride=8)
        self.hidden = 16

    def forward(self, x):
        return torch.relu(self.conv(x)).flatten(2).transpose(1, 2)


def squares(n, seed):
    # class k is a white square of side 8 + 8k on black: shot scale in miniature
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 3, n)
    X = np.zeros((n, 32, 32, 3), np.uint8)
    for i, k in enumerate(y):
        s = 8 + 8 * k
        r, c = rng.integers(0, 33 - s, 2)
        X[i, r:r + s, c:c + s] = 255
    return X, y


def test_training_learns_a_planted_size_rule_and_shuffled_labels_do_not():
    X, y = squares(300, 0)
    Xt, yt = squares(150, 1)
    kw = dict(backbone=Tiny, epochs=15, lr_backbone=3e-3, lr_head=3e-3, batch=32, size=32, device="cpu", seed=0)
    model = finetune.train(X, y, n_classes=3, **kw)
    assert np.mean(finetune.predict(model, Xt) == yt) > 0.9
    control = finetune.train(X, np.random.default_rng(2).permutation(y), n_classes=3, **kw)
    assert np.mean(finetune.predict(control, Xt) == yt) < 0.6


def test_predict_returns_class_codes_not_indices():
    X, y = squares(60, 0)
    codes = np.array([1, 4, 7])[y]  # sparse codes, as CineScale's are
    model = finetune.train(X, codes, n_classes=None, backbone=Tiny, epochs=1, batch=32, size=32, device="cpu", seed=0)
    assert set(finetune.predict(model, X)) <= {1, 4, 7}


def walk_films(names, unlabelled_every=0):
    # per-second labels from a random walk over scales, one shot every 3 s
    films, cuts = {}, {}
    for k, n in enumerate(names):
        rng, w = np.random.default_rng(k), [4]
        for _ in range(399):
            w.append(int(np.clip(w[-1] + rng.choice([-1, 1]), 1, 7)))
        y = np.repeat(w, 3)
        if unlabelled_every:
            y[::unlabelled_every] = -1
        films[n] = {"y": y}
        cuts[n] = {"transitions": [{"at": 72 * i} for i in range(1, 400)], "frames": 72 * 400, "fps": 24.0}
    return films, cuts


def test_leave_one_out_never_trains_on_the_film_it_judges():
    seen = []

    def fit_predict(train, test):
        seen.append((tuple(train), test))
        return films[test]["y"].copy()  # a perfect labeller

    films, cuts = walk_films(("a", "b", "c"))
    out = fitness.leave_one_out_with(films, cuts, fit_predict, draws=20, boots=20)
    assert set(seen) == {(("b", "c"), "a"), (("a", "c"), "b"), (("a", "b"), "c")}
    assert all(v["fit"] for rules in out.values() for v in rules.values())


def test_an_unlabelled_second_never_gets_a_prediction_counted():
    films, cuts = walk_films(("a", "b"), unlabelled_every=2)
    # a labeller that is right everywhere a human label exists and says 7 elsewhere
    fit = lambda train, test: np.where(films[test]["y"] >= 0, films[test]["y"], 7)
    out = fitness.leave_one_out_with(films, cuts, fit, draws=20, boots=20)
    assert all(v["fit"] for rules in out.values() for v in rules.values())


def test_cli_scale_finetune_reports_kappa_and_fitness_per_film_and_skips_unaligned(tmp_path, monkeypatch, capsys):
    import json

    from kubrick import scale
    from kubrick.cli import main

    films, cuts = walk_films(("a", "b", "c"))
    trained = []
    specs = []
    for n in ("a", "b", "c"):
        np.save(tmp_path / f"{n}.npy", np.zeros((len(films[n]["y"]), 8, 8, 3), np.uint8))
        (tmp_path / f"{n}.json").write_text(json.dumps(cuts[n]))
        specs.append(f"{tmp_path}/{n}.npz:{n}.csv:{tmp_path}/{n}.npy:{tmp_path}/{n}.json")
    loaded = {n: {"y": films[n]["y"], "align": {"accepted": n != "c"}} for n in films}
    monkeypatch.setattr(scale, "load_film", lambda npz, csv: dict(loaded[npz.stem]))
    monkeypatch.setattr(finetune, "train", lambda X, y, **kw: trained.append((len(X), kw)) or {"y": y})
    # the stub "model" predicts the right answer from the test film's own labels
    current = {}
    monkeypatch.setattr(finetune, "predict", lambda model, X: current["y"][:len(X)])
    real = fitness.leave_one_out_with

    def spy(films_, cuts_, fit_predict, **kw):
        def fp(train, test):
            current["y"] = films_[test]["y"][films_[test]["y"] >= 0]
            return fit_predict(train, test)
        return real(films_, cuts_, fp, **kw)

    monkeypatch.setattr(fitness, "leave_one_out_with", spy)
    assert main(["scale-finetune", *specs, "--epochs", "2", "--stride", "3", "--draws", "10", "--boots", "10"]) == 0
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    tests = {r["test"]: r for r in rows if "test" in r}
    assert set(tests) == {"a", "b"} and all(r["kappa_linear"] == 1.0 for r in tests.values())
    assert all(set(r["fitness"]) == {"one-step-scale-cuts", "wide-then-closer"} for r in tests.values())
    assert all(kw["epochs"] == 2 for _, kw in trained)
    assert trained[0][0] == len(np.flatnonzero(films["b"]["y"] >= 0)[::3])  # trained on the other aligned film only


def test_cli_frames_writes_one_square_frame_per_second(tmp_path):
    from kubrick.cli import main

    video(tmp_path / "v.mp4", [20, 200, 90])
    assert main(["frames", str(tmp_path / "v.mp4"), str(tmp_path / "f.npy"), "--size", "16"]) == 0
    assert np.load(tmp_path / "f.npy").shape == (3, 16, 16, 3)


def test_fitness_over_seeds_reports_a_fit_rate_per_rule_and_trains_each_seed(monkeypatch):
    films, cuts = walk_films(("a", "b"))
    frames = {n: np.zeros((len(films[n]["y"]), 8, 8, 3), np.uint8) for n in films}
    seen = []

    def fake_train(X, y, seed=0, **kw):
        seen.append(seed)
        return {"seed": seed}

    def fake_predict(model, X):
        # seed 0 predicts perfectly; any other seed scrambles, so the rate must be exactly 1 of 3
        test = current["test"]
        truth = films[test]["y"][films[test]["y"] >= 0][:len(X)]
        return truth if model["seed"] == 0 else np.random.default_rng(model["seed"]).permutation(truth)

    current = {}
    real = fitness.leave_one_out_with

    def spy(f, c, fit_predict, **kw):
        def fp(train, test):
            current["test"] = test
            return fit_predict(train, test)
        return real(f, c, fp, **kw)

    monkeypatch.setattr(finetune, "train", fake_train)
    monkeypatch.setattr(finetune, "predict", fake_predict)
    monkeypatch.setattr(fitness, "leave_one_out_with", spy)
    r = finetune.over_seeds(films, frames, cuts, seeds=[0, 1, 2], draws=10, boots=10)
    assert sorted(set(seen)) == [0, 1, 2]
    assert set(r) == {"a", "b"} and all(len(v["kappa_linear"]) == 3 for v in r.values())
    assert all(v["fit_rate"]["one-step-scale-cuts"] == pytest.approx(1 / 3) for v in r.values())
