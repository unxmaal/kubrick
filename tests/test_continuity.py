"""The continuity checker on planted errors. A scene is two people at a table, A at (0, 0) and B at (4, 0),
filmed from the south side of the line between them (y < 0)."""

import copy
import math

import pytest

from kubrick import continuity as c


def camera(x, y, look_at):
    return {"pos": [x, y], "heading": math.degrees(math.atan2(look_at[1] - y, look_at[0] - x)), "lens_mm": 35}


def clean():
    return {
        "id": "sc1",
        "characters": {"A": {"pos": [0, 0]}, "B": {"pos": [4, 0]}},
        "wardrobe": {"A": {"cap": "backwards"}},
        "shots": [
            {"id": "1", "camera": camera(2, -6, (2, 0)), "subjects": ["A", "B"],
             "moving": {}, "action": {}, "wardrobe": {"A": {"cap": "backwards"}}},
            {"id": "2", "camera": camera(5, -2, (0, 0)), "subjects": ["A", "B"], "looks": {"A": "B"},
             "gaze": {"A": "right"}, "action": {"stand": [0.0, 0.5]}, "wardrobe": {"A": {"cap": "backwards"}}},
            {"id": "3", "camera": camera(-1, -2, (4, 0)), "subjects": ["A", "B"], "looks": {"B": "A"},
             "gaze": {"B": "left"}, "action": {"stand": [0.5, 1.0]}, "wardrobe": {"A": {"cap": "backwards"}}},
        ],
    }


def ids(scene):
    return sorted({v["rule"] for v in c.check(scene)})


def test_a_clean_scene_passes():
    assert c.check(clean()) == []


def test_crossing_the_line_is_caught():
    s = clean()
    s["shots"][2]["camera"] = camera(-1, 2, (4, 0))  # north side
    assert "axis-180" in ids(s)


def test_an_eyeline_that_disagrees_with_the_floor_plan_is_caught():
    s = clean()
    s["shots"][2]["gaze"]["B"] = "right"
    assert "eyeline-match" in ids(s)


def test_a_screen_direction_flip_across_a_cut_is_caught():
    s = clean()
    for shot in s["shots"][1:]:
        shot["moving"] = {"A": [1, 0]}  # A walks east
    s["shots"][2]["camera"] = camera(2, 6, (2, 0))  # same walk seen from the north reads leftward
    assert "screen-direction" in ids(s)


def test_a_neutral_shot_between_permits_a_direction_change():
    s = clean()
    for shot in s["shots"]:
        shot["moving"] = {"A": [1, 0]}
    s["shots"][1]["camera"] = camera(-6, 0.01, (0, 0))  # looking straight along the walk
    s["shots"][1]["subjects"] = ["A"]
    s["shots"][2]["camera"] = camera(2, 6, (2, 0))
    s["shots"][2]["subjects"] = ["A"]
    assert "screen-direction" not in ids(s)


def test_an_action_running_backwards_across_a_cut_is_caught():
    s = clean()
    s["shots"][2]["action"]["stand"] = [0.2, 1.0]  # stands up again from a lower point
    assert "action-phase" in ids(s)


def test_the_cap_turned_round_between_shots_is_caught():
    s = clean()
    s["shots"][2]["wardrobe"]["A"]["cap"] = "forward"
    found = [v for v in c.check(s) if v["rule"] == "wardrobe-state"]
    assert found and found[0]["shot"] == "3" and "cap" in found[0]["detail"]


def test_mirroring_one_camera_across_the_line_flips_only_the_axis_verdict():
    for i in range(1, 3):
        s = clean()
        x, y = s["shots"][i]["camera"]["pos"]
        target = (0, 0) if i == 1 else (4, 0)
        s["shots"][i]["camera"] = camera(x, -y, target)
        s["shots"][i].pop("gaze", None)  # declared gaze would follow the camera; geometry alone is under test
        assert ids(s) == ["axis-180"], i


def test_every_rule_has_a_stable_id_and_a_description():
    assert set(c.RULES) == {"axis-180", "eyeline-match", "screen-direction", "action-phase", "wardrobe-state"}
    assert all(c.RULES[r] for r in c.RULES)


def test_a_violation_names_the_shots_and_the_rule():
    s = clean()
    s["shots"][2]["camera"] = camera(-1, 2, (4, 0))
    v = next(v for v in c.check(s) if v["rule"] == "axis-180")
    assert v["shot"] == "3" and v["previous"] == "2"


def test_a_gaze_at_an_unplaced_character_is_a_violation_not_a_crash():
    s = clean()
    s["shots"][1]["looks"] = {"A": "C"}
    s["shots"][1]["gaze"] = {"A": "right"}
    found = [v for v in c.check(s) if v["rule"] == "eyeline-match"]
    assert found and "C" in found[0]["detail"] and found[0]["shot"] == "2"


def test_check_does_not_modify_the_scene():
    s = clean()
    before = copy.deepcopy(s)
    c.check(s)
    assert s == before
