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


def tone(path, seconds, freq=440):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}", "-ar", "48000", str(path)], check=True)


def loudness(path, start, end):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-t", str(end - start), "-i", str(path),
                          "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return float(np.abs(np.frombuffer(raw, np.int16)).mean()) if raw else 0.0


def with_vo(proj):
    tone(proj / "vo1.wav", 2.5)
    shots = json.loads((proj / "shotlist.json").read_text())
    shots["scenes"][0]["shots"][0]["vo_audio"] = "vo1.wav"
    (proj / "shotlist.json").write_text(json.dumps(shots))
    return proj


def test_voiceover_sits_on_its_shot_and_the_render_carries_it(proj, tmp_path):
    with_vo(proj)
    tl = animatic.timeline(stages.load_project(proj))
    audio = [t for t in tl.tracks if t.kind == otio.schema.TrackKind.Audio]
    assert audio and [c.name for c in audio[0].find_clips()] == ["1A vo"]
    video = next(t for t in tl.tracks if t.kind == otio.schema.TrackKind.Video)
    assert audio[0].duration() == video.duration()  # else every later line starts late
    out = tmp_path / "a.mp4"
    animatic.render(tl, proj, out)
    assert loudness(out, 0.2, 2.3) > 1000  # the line plays over 1A
    assert loudness(out, 4.5, 6.8) < 50  # 1B has no line
    dur = lambda kind: float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", f"{kind}:0", "-show_entries", "stream=duration", "-of", "csv=p=0",
         str(out)], capture_output=True, text=True, check=True).stdout)
    assert abs(dur("a") - dur("v")) <= 1 / animatic.FPS


def test_a_line_on_a_later_shot_starts_at_that_shot(proj, tmp_path):
    # a line at time zero cannot show a placement bug; 1B starts at 4 s
    tone(proj / "vo2.wav", 2.0, freq=660)
    shots = json.loads((proj / "shotlist.json").read_text())
    shots["scenes"][0]["shots"][1]["vo_audio"] = "vo2.wav"
    (proj / "shotlist.json").write_text(json.dumps(shots))
    out = tmp_path / "b.mp4"
    animatic.render(animatic.timeline(stages.load_project(proj)), proj, out)
    assert loudness(out, 0.2, 3.8) < 50
    assert loudness(out, 4.2, 5.8) > 1000


def test_a_render_that_runs_past_its_limit_fails_instead_of_hanging(proj, tmp_path, monkeypatch):
    # an audio filter without its trim pads forever; the render must stop, not hang the caller
    monkeypatch.setattr(animatic, "RENDER_TIMEOUT_S", 0.01)
    monkeypatch.setattr(animatic, "RENDER_SECONDS_PER_SECOND", 0)
    with pytest.raises(RuntimeError, match="did not finish"):
        animatic.render(animatic.timeline(stages.load_project(proj)), proj, tmp_path / "c.mp4")


def test_an_unreadable_voiceover_file_is_reported_not_a_crash(proj):
    with_vo(proj)
    (proj / "vo1.wav").write_bytes(b"not audio at all")
    assert any("vo1.wav" in e and "cannot be read" in e for e in stages.validate_project(proj))


def test_the_timeline_refuses_a_line_longer_than_its_shot_rather_than_cutting_it(proj):
    with_vo(proj)
    tone(proj / "vo1.wav", 5.0)
    with pytest.raises(ValueError, match="longer than"):
        animatic.timeline(stages.load_project(proj))


def test_a_line_longer_than_its_shot_is_rejected(proj):
    with_vo(proj)
    tone(proj / "vo1.wav", 5.0)  # 1A lasts 4 s
    assert any("vo1.wav" in e and "longer" in e for e in stages.validate_project(proj))


def test_a_missing_voiceover_file_is_rejected(proj):
    with_vo(proj)
    (proj / "vo1.wav").unlink()
    assert any("vo1.wav" in e and "does not exist" in e for e in stages.validate_project(proj))


def test_an_invalid_project_is_refused_before_building(proj):
    (proj / "floorplan.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="floorplan.json"):
        animatic.build(proj, proj / "out")
