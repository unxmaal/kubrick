import json

import numpy as np

from kubrick import panels


def shot(i="1A", scale="MS", subjects=("GUARD", "AL")):
    return {"id": i, "scale": scale, "movement": "static", "subjects": list(subjects), "duration_s": 3.0,
            "description": "Two men at a workbench."}


def test_a_panel_with_more_people_than_the_shot_list_is_flagged():
    v = panels.judge(shot("10A", "LS", ["OFFICER A", "OFFICER B"]), humans=3, faces=0, uniform=False)
    assert v["flagged"] and any("3 people" in r for r in v["hard"])


def test_an_over_the_shoulder_panel_is_not_flagged_for_a_person_seen_from_behind():
    # the foreground man is seen from behind, so the detector finds one of the two
    v = panels.judge(shot("1B", "MS"), humans=1, faces=1, uniform=False)
    assert not v["flagged"] and v["soft"]
    far = panels.judge(shot("8B", "MLS", ["GUARD"]), humans=0, faces=0, uniform=False)
    assert not far["flagged"] and not far["soft"]  # wide enough that a missed figure says nothing


def fake_project(tmp_path, n_tries_flagged=0):
    """A generator that draws one noise image per call (a flat one would fail the blank check)."""
    calls = []

    def generate(prompt, seed, out):
        calls.append((prompt, seed))
        import cv2
        cv2.imwrite(str(out), np.random.default_rng(len(calls)).integers(0, 255, (36, 64, 3), np.uint8))
        return out

    return calls, generate


def test_the_better_scoring_of_two_candidates_is_kept(tmp_path):
    calls, generate = fake_project(tmp_path)
    counts = iter([(3, 0), (2, 2)])  # first candidate over-counts, second is right
    r = panels.make(shot("1A"), "STYLE ", tmp_path, generate, count=lambda p: next(counts), seed=5)
    assert len(calls) == 2 and not r["flagged"] and r["candidate"] == 1
    assert (tmp_path / "1A.png").read_bytes() == (tmp_path / "attempts" / "1A-1.png").read_bytes()


def test_a_shot_that_fails_every_try_keeps_its_best_candidate_marked_flagged(tmp_path):
    calls, generate = fake_project(tmp_path)
    r = panels.make(shot("10A", "LS", ["A", "B"]), "STYLE ", tmp_path, generate, count=lambda p: (3, 0), seed=5)
    assert r["flagged"] and r["hard"] and (tmp_path / "10A.png").exists()
    prompts = [p for p, _ in calls]
    assert len(set(prompts)) == 4  # the first wording, then three rewordings


def test_no_shot_ever_uses_more_than_eight_images(tmp_path):
    calls, generate = fake_project(tmp_path)
    panels.make(shot("10A", "LS", ["A", "B"]), "STYLE ", tmp_path, generate, count=lambda p: (5, 0), seed=5)
    assert len(calls) == 8
    rows = [json.loads(l) for l in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert len(rows) == 8 and all({"shot", "try", "prompt", "seed", "image", "hard", "soft", "score"} <= set(r) for r in rows)


def test_an_eric_sketch_is_never_regenerated(tmp_path):
    root = tmp_path / "proj"
    (root / "panels").mkdir(parents=True)
    (root / "panels" / "1A.png").write_bytes(b"eric's pencil")
    sl = {"scenes": [{"id": "1", "shots": [shot("1A"), shot("1B")]}]}
    (root / "shotlist.json").write_text(json.dumps(sl))
    (root / "storyboard.json").write_text(json.dumps({"panels": [{"shot": "1A", "image": "panels/1A.png", "source": "sketch"}]}))
    calls, generate = fake_project(tmp_path)
    panels.run(root, "STYLE ", generate, count=lambda p: (2, 2))
    assert (root / "panels" / "1A.png").read_bytes() == b"eric's pencil"
    assert {p["shot"]: p["source"] for p in json.loads((root / "storyboard.json").read_text())["panels"]} == \
        {"1A": "sketch", "1B": "generated"}
    assert all("Two men" in p for p, _ in calls) and len(calls) == 2  # only 1B was drawn
