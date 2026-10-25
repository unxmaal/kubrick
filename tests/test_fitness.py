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


def test_the_effect_interval_brackets_the_observed_effect():
    rng = np.random.default_rng(0)
    segs = [[int(x) for x in rng.choice([2, 3, 4, 5], 12)] for _ in range(40)]
    segs = [[v for i, v in enumerate(s) if i == 0 or v != s[i - 1]] for s in segs]
    lo, mid, hi = fitness.effect_interval(segs, grammar.one_step_share, draws=40, boots=60, seed=0)
    assert lo <= mid <= hi


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
