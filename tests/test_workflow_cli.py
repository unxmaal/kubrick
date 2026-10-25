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


def test_cli_scenarios_checks_each_issue_the_pr_body_names(tmp_path, monkeypatch, capsys):
    import json as _json

    from kubrick import scenarios
    from kubrick.cli import main

    bodies = {20: "#### Scenario: an issue with no scenarios passes\n", 5: "#### Scenario: nobody wrote this test\n"}
    asked = []
    monkeypatch.setattr(scenarios, "issue_body", lambda n, repo=None: asked.append(n) or bodies[n])
    (tmp_path / "pr.md").write_text("Part of #20. Closes #5. See #13.", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_an_issue_with_no_scenarios_passes():\n    pass\n", encoding="utf-8")
    assert main(["scenarios", "--pr-body-file", str(tmp_path / "pr.md"), "--tests", str(tmp_path / "tests")]) == 1
    rows = {r["issue"]: r for r in map(_json.loads, capsys.readouterr().out.splitlines())}
    assert sorted(asked) == [5, 20] and rows[20]["ok"] and rows[5]["missing"] == ["nobody wrote this test"]


def test_cli_scenarios_passes_a_pr_that_names_no_issue(tmp_path, capsys):
    from kubrick.cli import main

    (tmp_path / "pr.md").write_text("A typo fix.", encoding="utf-8")
    assert main(["scenarios", "--pr-body-file", str(tmp_path / "pr.md")]) == 0


def test_ci_runs_the_scenario_check_on_pull_requests_with_a_token_that_can_read_issues():
    # the scanner is only a gate if CI invokes it, and gh issue view fails without issues: read
    import yaml
    from pathlib import Path

    wf = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    steps = [s for s in wf["jobs"]["check"]["steps"] if "kubrick scenarios" in s.get("run", "")]
    assert steps and "--pr-body-file" in steps[0]["run"] and "pull_request" in steps[0].get("if", "")
    assert wf["permissions"].get("issues") == "read"


def test_cli_panels_draws_unsketched_shots_with_the_project_style_and_model(tmp_path, monkeypatch, capsys):
    import json as _json

    import numpy as np

    from kubrick import panels
    from kubrick.cli import main

    root = tmp_path / "p"
    root.mkdir()
    shots = [{"id": i, "scale": "LS", "movement": "static", "subjects": ["G"], "duration_s": 2, "description": f"Shot {i}."}
             for i in ("1A", "1B")]
    (root / "shotlist.json").write_text(_json.dumps({"scenes": [{"id": "1", "shots": shots}]}))
    (root / "style.txt").write_text("PENCIL. ", encoding="utf-8")
    seen = {}

    def fake_soh(model=None, **kw):
        seen["model"] = model

        def generate(prompt, seed, out):
            import cv2
            seen.setdefault("prompts", []).append(prompt)
            cv2.imwrite(str(out), np.random.default_rng(seed).integers(0, 255, (36, 64, 3), np.uint8))
            return out
        return generate

    monkeypatch.setattr(panels, "soh_generate", fake_soh)
    monkeypatch.setattr(panels, "vision_count", lambda p: (1, 0))
    assert main(["panels", str(root), "--model", "mflux:z-image-turbo", "--only", "1B"]) == 0
    assert seen["model"] == "mflux:z-image-turbo" and all(p.startswith("PENCIL. Shot 1B") for p in seen["prompts"])
    rows = [_json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert [r["shot"] for r in rows] == ["1B"] and not rows[0]["flagged"]


def test_cli_lora_merge_writes_the_merged_checkpoint_at_the_given_scale(tmp_path, capsys):
    import json as _json

    from test_lora_merge import adapter, checkpoint

    from kubrick.cli import main

    d, _, _ = checkpoint(tmp_path)
    p, _, _ = adapter(tmp_path)
    assert main(["lora-merge", str(p), str(d), str(tmp_path / "out"), "--scale", "0.7"]) == 0
    assert _json.loads(capsys.readouterr().out) == {"layers": 1, "shards_written": 1, "scale": 0.7}
