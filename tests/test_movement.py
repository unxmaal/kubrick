import numpy as np
import pytest

from kubrick import movement as mv

KINDS = ("static", "pan", "tilt", "push", "pull", "handheld")


def texture(seed=0):
    """A still with detail at several scales, standing in for a film frame."""
    rng = np.random.default_rng(seed)
    import cv2

    img = np.zeros((720, 1280, 3), np.float32)
    for size in (8, 32, 128):
        n = rng.random((720 // size + 1, 1280 // size + 1, 3)).astype(np.float32)
        img += cv2.resize(n, (1280, 720), interpolation=cv2.INTER_CUBIC)
    return (255 * (img - img.min()) / np.ptp(img)).astype(np.uint8)


@pytest.mark.parametrize("kind", KINDS)
def test_each_known_movement_is_classified_as_itself(kind):
    m = mv.motion(mv.render(texture(), kind, seed=3))
    assert mv.classify(m) == kind


def test_handheld_jitter_is_not_static():
    for seed in range(4):
        m = mv.motion(mv.render(texture(seed), "handheld", seed=seed))
        assert mv.classify(m) == "handheld", m


def test_static_with_sensor_noise_stays_static():
    clip = mv.render(texture(), "static").astype(np.int16)
    clip += np.random.default_rng(0).integers(-3, 4, clip.shape, dtype=np.int16)
    assert mv.classify(mv.motion(np.clip(clip, 0, 255).astype(np.uint8))) == "static"


@pytest.mark.parametrize("kind", ["pan", "tilt"])
def test_direction_is_the_cameras_not_the_contents(kind):
    for seed in range(4):
        rng = np.random.default_rng(seed)
        sign = rng.choice([-1, 1])  # render draws the same sign first from the same seed
        m = mv.motion(mv.render(texture(), kind, seed=seed))
        want = {("pan", 1): "right", ("pan", -1): "left", ("tilt", 1): "down", ("tilt", -1): "up"}[(kind, sign)]
        assert mv.direction(m) == want


def test_known_set_has_every_kind_at_every_amount_and_scores_per_class():
    stills = [texture(s) for s in range(2)]
    cases = mv.known_set(stills, seed=0, amounts=(0.5, 1.0))
    assert {(c["kind"], c["amount"]) for c in cases} == {(k, a) for k in KINDS for a in (0.5, 1.0)}
    assert len(cases) == len(KINDS) * 2 * len(stills)
    acc = mv.score(cases)
    assert set(acc) == set(KINDS) and all(0 <= v <= 1 for v in acc.values())


def test_score_uses_the_thresholds_it_is_given():
    cases = mv.known_set([texture()], seed=0, amounts=(1.0,))
    assert mv.score(cases)["pan"] == 1.0
    assert mv.score(cases, shift=1e6)["pan"] == 0.0


def test_a_large_pan_with_spurious_zoom_from_entering_edges_is_a_pan():
    # measured on a film still: 3.9 px/frame pan read a zoom of -0.0035 from the new edge
    m = {"tx": -3.88, "ty": -0.03, "zoom": -0.0035, "jitter": 0.45}
    assert mv.classify(m, zoom=0.001, shift=0.3, jitter=0.4) == "pan"


def test_a_push_with_slight_drift_is_still_a_push():
    m = {"tx": 0.11, "ty": 0.06, "zoom": 0.0054, "jitter": 0.04}
    assert mv.classify(m, zoom=0.001, shift=0.3, jitter=0.4) == "push"


def test_known_set_skips_stills_with_no_texture():
    # a camera move over a black frame has no visible motion, so it is no test of a classifier
    black = np.full((720, 1280, 3), 5, np.uint8)
    cases = mv.known_set([black, texture()], seed=0, amounts=(1.0,))
    assert len(cases) == len(KINDS)
    assert mv.known_set.skipped == 1


def test_a_clip_with_no_texture_is_unknown_not_static():
    clip = mv.render(np.full((720, 1280, 3), 5, np.uint8), "pan")
    assert mv.classify(mv.motion(clip)) == "unknown:no-texture"


def test_unknown_movement_is_refused():
    with pytest.raises(ValueError, match="unknown movement"):
        mv.render(texture(), "dolly-zoom")
