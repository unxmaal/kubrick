import json
import subprocess

import cv2
import numpy as np
import opentimelineio as otio
import pytest

from kubrick import animatic, stages
from test_stages import project, write


@pytest.fixture
def proj(tmp_path):
    docs = project()
    docs["shotlist.json"]["scenes"][0]["shots"][0]["vo"] = "I walked the yard every night."
    # storyboard file lists the panels in the reverse of shot order; the animatic follows the shot list
    docs["storyboard.json"]["panels"].reverse()
    root = write(tmp_path, docs)
    for name, colour in (("1A.png", 60), ("1B.jpg", 200)):
        cv2.imwrite(str(root / "panels" / name), np.full((360, 640, 3), colour, np.uint8))
    return root


def test_timeline_follows_the_shot_list_with_its_durations(proj):
    tl = animatic.timeline(stages.load_project(proj))
    clips = list(tl.find_clips())
    assert [c.name for c in clips] == ["1A", "1B"]
    assert [c.duration().to_seconds() for c in clips] == [4.0, 3.0]
    assert tl.duration().to_seconds() == 7.0


def test_markers_name_shots_and_carry_voiceover_and_source(proj):
    tl = animatic.timeline(stages.load_project(proj))
    clips = list(tl.find_clips())
    assert clips[0].metadata["kubrick"] == {"shot": "1A", "source": "generated", "vo": "I walked the yard every night."}
    assert clips[1].metadata["kubrick"]["source"] == "sketch"
    assert [m.name for c in clips for m in c.markers] == ["1A", "1B"]


def test_timeline_round_trips_through_otio_json(proj, tmp_path):
    tl = animatic.timeline(stages.load_project(proj))
    path = tmp_path / "animatic.otio"
    otio.adapters.write_to_file(tl, str(path))
    back = otio.adapters.read_from_file(str(path))
    assert otio.adapters.write_to_string(back) == otio.adapters.write_to_string(tl)


def test_render_lasts_exactly_as_long_as_the_timeline(proj, tmp_path):
    tl = animatic.timeline(stages.load_project(proj))
    out = tmp_path / "animatic.mp4"
    animatic.render(tl, proj, out)
    frames = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                 "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
                                capture_output=True, text=True, check=True).stdout.strip())
    assert frames == round(tl.duration().to_seconds() * animatic.FPS)


def test_render_shows_each_panel_for_its_own_shot(proj, tmp_path):
    tl = animatic.timeline(stages.load_project(proj))
    out = tmp_path / "animatic.mp4"
    animatic.render(tl, proj, out)
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(out), "-vf", "scale=16:9", "-pix_fmt", "gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    luma = np.frombuffer(raw, np.uint8).reshape(-1, 9, 16).mean(axis=(1, 2))
    assert abs(luma[0] - 60) < 15 and abs(luma[-1] - 200) < 15
    assert abs(luma[4 * animatic.FPS - 1] - 60) < 15 and abs(luma[4 * animatic.FPS + 1] - 200) < 15


def test_an_invalid_project_is_refused_before_building(proj):
    (proj / "floorplan.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="floorplan.json"):
        animatic.build(proj, proj / "out")
