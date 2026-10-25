import numpy as np

from kubrick import fitness, grammar


def test_a_shot_takes_the_most_common_label_of_its_seconds():
    per_second = np.array([3, 3, 4, -1, 6, 6, 6, 2])
    # 24 fps; shots start at frames 0, 72 (second 3), 168 (second 7)
    assert fitness.shot_labels(per_second, [72, 168], n_frames=192, fps=24) == [3, 6, 2]


def test_a_shot_with_no_labelled_second_is_unknown():
    assert fitness.shot_labels(np.array([-1, -1, 4]), [48], n_frames=72, fps=24) == [-1, 4]


def test_unlabelled_seconds_do_not_outvote_a_labelled_one():
    assert fitness.shot_labels(np.array([-1, -1, 4]), [], n_frames=72, fps=24) == [4]


def _walk(rng, films=40, length=30):
    out = []
    for _ in range(films):
        w = [4]
        for _ in range(length):
            w.append(int(np.clip(w[-1] + rng.choice([-1, 1]), 1, 7)))
        out += w
    return out


def test_identical_labels_differ_by_exactly_zero_in_every_resample():
    human = _walk(np.random.default_rng(0))
    assert fitness.difference_interval(human, human, grammar.one_step_share, draws=20, boots=30) == (0.0, 0.0, 0.0)


def test_noisier_labels_give_an_interval_below_zero():
    rng = np.random.default_rng(1)
    human = _walk(rng)
    noisy = [v if rng.random() < 0.6 else int(rng.integers(1, 8)) for v in human]
    lo, mid, hi = fitness.difference_interval(human, noisy, grammar.one_step_share, draws=20, boots=40)
    assert hi < 0 and lo <= mid <= hi


def test_a_single_unbroken_film_still_gets_a_real_interval():
    # the first design resampled segments, which does nothing when a film is one segment
    rng = np.random.default_rng(2)
    human = _walk(rng, films=1, length=600)
    noisy = [v if rng.random() < 0.6 else int(rng.integers(1, 8)) for v in human]
    lo, _, hi = fitness.difference_interval(human, noisy, grammar.one_step_share, draws=20, boots=40)
    assert hi < 0 and hi - lo > 0


def test_identical_labels_are_fit_and_scrambled_labels_are_not():
    rng = np.random.default_rng(1)
    human = []
    for _ in range(60):  # films that cut by one step much more than chance
        walk = [4]
        for _ in range(30):
            walk.append(int(np.clip(walk[-1] + rng.choice([-1, 1]), 1, 7)))
        human += walk + [-1]
    same = fitness.check(human, human, draws=40, boots=40)
    assert same["one-step-scale-cuts"]["fit"] is True
    scrambled = [int(v) if v < 0 else int(rng.integers(1, 8)) for v in human]
    assert fitness.check(human, scrambled, draws=40, boots=40)["one-step-scale-cuts"]["fit"] is False


def _films(n_films=4, seconds=600, seed=3):
    rng = np.random.default_rng(seed)
    films, cuts = {}, {}
    for f in range(n_films):
        walk, y = [4], []
        for _ in range(seconds // 4):
            walk.append(int(np.clip(walk[-1] + rng.choice([-1, 1]), 1, 7)))
            y += [walk[-1]] * 4  # a four-second shot
        y = np.array(y[:seconds])
        X = np.eye(9)[y] + rng.normal(0, 0.05, (seconds, 9))  # features that give the label away
        films[f"f{f}"] = {"X": X, "y": y, "features": ("m", 0)}
        cuts[f"f{f}"] = {"fps": 24.0, "frames": seconds * 24, "transitions": [{"at": s * 24} for s in range(4, seconds, 4)]}
    return films, cuts


def test_leave_one_film_out_fitness_with_a_perfect_labeller_is_fit():
    films, cuts = _films()
    r = fitness.leave_one_out(films, cuts, kind="linear", draws=30, boots=30)
    assert set(r) == set(films)
    assert all(r[f]["one-step-scale-cuts"]["fit"] for f in r)


def test_a_labeller_with_the_right_verdict_but_a_much_weaker_effect_is_not_fit():
    rng = np.random.default_rng(2)
    human = []
    for _ in range(60):
        walk = [4]
        for _ in range(30):
            walk.append(int(np.clip(walk[-1] + rng.choice([-1, 1]), 1, 7)))
        human += walk + [-1]
    noisy = [v if v < 0 or rng.random() < 0.6 else int(rng.integers(1, 8)) for v in human]
    r = fitness.check(human, noisy, draws=40, boots=40)["one-step-scale-cuts"]
    assert r["human"]["above_null"] and r["predicted"]["above_null"]  # same verdict
    assert r["fit"] is False  # but the effect falls outside the human interval
