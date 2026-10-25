import copy
import json

import pytest

from kubrick import continuity, stages

SCRIPT = """Title: Fixture

EXT. SERVICE YARD - NIGHT

A GUARD walks to a black door and stops.

INT. BOILER ROOM - NIGHT

The GUARD looks at the furnace.

.FLASHBACK CORRIDOR
"""


def project():
    return {
        "script.fountain": SCRIPT,
        "breakdown.json": {"scenes": [{"id": "1", "heading": "EXT. SERVICE YARD - NIGHT", "characters": ["GUARD"],
                                       "sets": ["service yard"], "props": {"door": {"place": "north wall"}},
                                       "wardrobe": {"GUARD": {"cap": "forward"}}, "wardrobe_changes": []}]},
        "shotlist.json": {"scenes": [{"id": "1", "shots": [
            {"id": "1A", "scale": "LS", "movement": "static", "subjects": ["GUARD"], "duration_s": 4.0,
             "description": "The guard crosses the yard.", "wardrobe": {"GUARD": {"cap": "forward"}}},
            {"id": "1B", "scale": "MS", "movement": "pan", "subjects": ["GUARD"], "duration_s": 3.0,
             "description": "He reaches the door.", "wardrobe": {"GUARD": {"cap": "forward"}}}]}]},
        "floorplan.json": {"scenes": [{"id": "1", "characters": {"GUARD": {"pos": [0, 0]}}, "shots": {
            "1A": {"camera": {"pos": [0, -8], "heading": 90, "lens_mm": 24}, "moving": {"GUARD": [1, 0]}},
            "1B": {"camera": {"pos": [3, -3], "heading": 90, "lens_mm": 50}, "moving": {"GUARD": [1, 0]}}}}]},
        "storyboard.json": {"panels": [{"shot": "1A", "image": "panels/1A.png", "source": "generated"},
                                       {"shot": "1B", "image": "panels/1B.jpg", "source": "sketch"}]},
    }


def write(tmp_path, docs):
    for name, body in docs.items():
        (tmp_path / name).write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    (tmp_path / "panels").mkdir(exist_ok=True)
    for p in ("1A.png", "1B.jpg"):
        (tmp_path / "panels" / p).write_bytes(b"x")
    return tmp_path


def test_fountain_scene_headings_including_forced_ones():
    assert stages.scene_headings(SCRIPT) == ["EXT. SERVICE YARD - NIGHT", "INT. BOILER ROOM - NIGHT", "FLASHBACK CORRIDOR"]


def test_a_consistent_project_validates(tmp_path):
    assert stages.validate_project(write(tmp_path, project())) == []


@pytest.mark.parametrize("empty", [{}, {"scenes": []}])
def test_a_present_but_empty_document_is_rejected(tmp_path, empty):
    docs = project()
    docs["breakdown.json"] = empty
    errors = stages.validate_project(write(tmp_path, docs))
    assert any("breakdown.json" in e for e in errors)


def test_a_scale_outside_the_taxonomy_is_rejected(tmp_path):
    docs = project()
    docs["shotlist.json"]["scenes"][0]["shots"][0]["scale"] = "cowboy"
    assert any("cowboy" in e for e in stages.validate_project(write(tmp_path, docs)))


def test_a_shot_missing_from_the_floor_plan_is_rejected(tmp_path):
    docs = project()
    del docs["floorplan.json"]["scenes"][0]["shots"]["1B"]
    assert any("1B" in e and "floorplan" in e for e in stages.validate_project(write(tmp_path, docs)))


def test_a_breakdown_scene_whose_heading_is_not_in_the_script_is_rejected(tmp_path):
    docs = project()
    docs["breakdown.json"]["scenes"][0]["heading"] = "INT. NOWHERE - DAY"
    assert any("INT. NOWHERE - DAY" in e for e in stages.validate_project(write(tmp_path, docs)))


def test_a_storyboard_panel_must_exist_and_say_where_it_came_from(tmp_path):
    docs = project()
    docs["storyboard.json"]["panels"][1]["source"] = "unknown"
    docs["storyboard.json"]["panels"][0]["image"] = "panels/missing.png"
    errors = stages.validate_project(write(tmp_path, docs))
    assert any("missing.png" in e for e in errors) and any("unknown" in e for e in errors)


def test_assembled_scene_carries_the_breakdowns_wardrobe_and_passes_the_checker(tmp_path):
    p = stages.load_project(write(tmp_path, project()))
    scene = stages.assemble(p, "1")
    assert scene["wardrobe"] == {"GUARD": {"cap": "forward"}}
    assert continuity.check(scene) == []


def test_a_wardrobe_change_in_the_shot_list_alone_is_caught_through_assembly(tmp_path):
    docs = project()
    docs["shotlist.json"]["scenes"][0]["shots"][1]["wardrobe"]["GUARD"]["cap"] = "backwards"
    scene = stages.assemble(stages.load_project(write(tmp_path, docs)), "1")
    assert [v["rule"] for v in continuity.check(scene)] == ["wardrobe-state"]


def test_screen_direction_set_in_the_floor_plan_reaches_the_prompt_fields(tmp_path):
    docs = project()
    p = stages.load_project(write(tmp_path, docs))
    assert stages.prompt_fields(p, "1", "1A")["screen_direction"] == {"GUARD": "right"}
    flipped = copy.deepcopy(docs)
    flipped["floorplan.json"]["scenes"][0]["shots"]["1A"]["camera"] = {"pos": [0, 8], "heading": -90, "lens_mm": 24}
    p2 = stages.load_project(write(tmp_path, flipped))
    assert stages.prompt_fields(p2, "1", "1A")["screen_direction"] == {"GUARD": "left"}


def test_prompt_fields_carry_the_breakdown_wardrobe_not_a_restatement(tmp_path):
    # the shot list says nothing about the cap here; the prompt must still carry the breakdown's state
    docs = project()
    docs["breakdown.json"]["scenes"][0]["wardrobe"]["GUARD"]["cap"] = "backwards"
    del docs["shotlist.json"]["scenes"][0]["shots"][0]["wardrobe"]
    p = stages.load_project(write(tmp_path, docs))
    assert stages.prompt_fields(p, "1", "1A")["wardrobe"] == {"GUARD": {"cap": "backwards"}}
