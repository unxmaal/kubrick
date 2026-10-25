import json

import cv2
import numpy as np

from kubrick import animatic
from kubrick.cli import main
from test_stages import project, write


def test_card_writes_a_readable_panel_for_a_shot(tmp_path):
    out = tmp_path / "1A.png"
    assert main(["card", "1A", "The guard crosses the yard.", str(out)]) == 0
    img = cv2.imread(str(out))
    assert img.shape[:2] == (animatic.H // 2, animatic.W // 2)
    assert img.std() > 5  # text was drawn, not a blank fill


def test_validate_reports_problems_and_exits_nonzero(tmp_path, capsys):
    root = write(tmp_path, project())
    assert main(["validate", str(root)]) == 0
    (root / "breakdown.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    assert main(["validate", str(root)]) == 1
    assert "breakdown.json" in capsys.readouterr().out


def test_continuity_lists_violations_by_rule_and_exits_nonzero(tmp_path, capsys):
    docs = project()
    docs["shotlist.json"]["scenes"][0]["shots"][1]["wardrobe"]["GUARD"]["cap"] = "backwards"
    root = write(tmp_path, docs)
    assert main(["continuity", str(root)]) == 1
    rows = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [r["rule"] for r in rows] == ["wardrobe-state"] and rows[0]["scene"] == "1"


def test_continuity_runs_before_the_storyboard_exists(tmp_path):
    docs = {k: v for k, v in project().items() if k != "storyboard.json"}
    assert main(["continuity", str(write(tmp_path, docs))]) == 0


def test_validate_until_a_stage(tmp_path, capsys):
    docs = {k: v for k, v in project().items() if k in ("script.fountain", "breakdown.json")}
    assert main(["validate", str(write(tmp_path, docs)), "--until", "breakdown"]) == 0
    assert "ok" in capsys.readouterr().out


def test_animatic_build_refuses_a_render_shorter_than_its_timeline(tmp_path, monkeypatch):
    import pytest

    root = write(tmp_path, project())
    for name in ("1A.png", "1B.jpg"):
        cv2.imwrite(str(root / "panels" / name), np.full((360, 640, 3), 90, np.uint8))
    real = animatic.render
    monkeypatch.setattr(animatic, "render", lambda tl, r, out: real(tl, r, out, fps=12))  # half the frames
    with pytest.raises(RuntimeError, match="frames"):
        animatic.build(root, tmp_path / "out")


def test_animatic_command_builds_both_files(tmp_path):
    root = write(tmp_path, project())
    for name in ("1A.png", "1B.jpg"):
        cv2.imwrite(str(root / "panels" / name), np.full((360, 640, 3), 90, np.uint8))
    assert main(["animatic", str(root), str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "animatic.otio").is_file() and (tmp_path / "out" / "animatic.mp4").is_file()
