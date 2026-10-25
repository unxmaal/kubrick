import json
import subprocess

import pytest

from kubrick import cuts, synth, taxonomy
from kubrick.score import score

A = "lavfi:testsrc2=size=640x360:rate=24"
B = "lavfi:smptebars=size=640x360:rate=24"
C = "lavfi:mandelbrot=size=640x360:rate=24"


def spec(joins, **seg_extra):
    segs = [{"source": s, "frames": 48} for s in (A, B, C)]
    segs[0].update(seg_extra)
    return synth.Spec.from_dict({"segments": segs, "joins": joins})


def test_truth_frames_for_cut_and_dissolve():
    t = synth.truth(spec([{"kind": "cut"}, {"kind": "dissolve", "frames": 12}]))
    assert t["transitions"] == [
        {"kind": "cut", "first": 48, "last": 48},
        {"kind": "dissolve", "first": 84, "last": 95},
    ]
    assert t["frames"] == 48 + 48 - 12 + 48


def test_spec_refuses_mismatched_joins():
    with pytest.raises(ValueError):
        synth.Spec.from_dict({"segments": [{"source": A, "frames": 10}] * 2, "joins": []})
    with pytest.raises(ValueError):
        synth.Spec.from_dict({"segments": [{"source": A, "frames": 10}] * 2,
                              "joins": [{"kind": "wipe", "frames": 4}]})


def test_built_clip_has_the_frames_truth_claims(tmp_path):
    s = spec([{"kind": "cut"}, {"kind": "fade", "frames": 12}], flash=[20, 21])
    out = tmp_path / "k.mp4"
    t = synth.build(s, out)
    n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True, check=True).stdout.strip()
    assert int(n) == t["frames"]
    assert json.loads(out.with_suffix(".truth.json").read_text()) == t


def test_framejump_finds_the_hard_cut_on_its_frame(tmp_path):
    out = tmp_path / "k.mp4"
    t = synth.build(spec([{"kind": "cut"}, {"kind": "cut"}]), out)
    assert cuts.detect(str(out), "framejump") == [x["first"] for x in t["transitions"]]


def test_flash_is_a_planted_negative_in_output_frames():
    t = synth.truth(spec([{"kind": "cut"}, {"kind": "cut"}], flash=[20, 21]))
    assert t["negatives"] == [{"kind": "flash", "first": 20, "last": 21}]


TRUTH = {"fps": 24, "frames": 2400, "negatives": [{"kind": "flash", "first": 500, "last": 501}],
         "transitions": [{"kind": "cut", "first": 100, "last": 100},
                         {"kind": "dissolve", "first": 300, "last": 311}]}


def test_score_counts_a_detected_dissolve():
    r = score(TRUTH, [100, 305])
    assert r["per_kind"]["dissolve"] == {"tp": 1, "fn": 0, "recall": 1.0}
    assert r["false"] == 0 and r["cut_f1"] == 1.0


def test_score_counts_a_missed_dissolve():
    r = score(TRUTH, [100])
    assert r["per_kind"]["dissolve"]["fn"] == 1


def test_score_charges_a_flash_detection_to_negatives():
    r = score(TRUTH, [100, 305, 500])
    assert r["false"] == 1 and r["false_on_negatives"] == 1
    assert r["negatives_triggered"] == 1.0
    assert r["false_elsewhere_per_10min"] == 0


def test_score_rates_false_cuts_away_from_negatives():
    r = score(TRUTH, [100, 305, 1200])
    assert r["negatives_triggered"] == 0.0
    assert r["false_elsewhere_per_10min"] == pytest.approx(6.0)


def test_flash_guard_drops_a_planted_flash_and_keeps_the_cut_after_it(tmp_path):
    segs = [{"source": A, "frames": 48, "flash": [38, 39]}, {"source": B, "frames": 48}]
    s = synth.Spec.from_dict({"segments": segs, "joins": [{"kind": "cut"}]})
    out = tmp_path / "f.mp4"
    synth.build(s, out)
    assert 38 in cuts.detect(str(out), "framejump", 20, flash_guard=0, min_len=1)
    assert cuts.detect(str(out), "framejump", 20, flash_guard=10) == [48]


def test_one_prediction_matches_one_transition():
    t = {**TRUTH, "transitions": [{"kind": "cut", "first": 100, "last": 100},
                                  {"kind": "cut", "first": 102, "last": 102}]}
    assert score(t, [101])["recall"] == 0.5


def test_cli_cuts_applies_the_flash_guard_and_min_len_it_is_given(tmp_path, capsys):
    from kubrick.cli import main

    segs = [{"source": A, "frames": 48, "flash": [38, 39]}, {"source": B, "frames": 48}]
    out = tmp_path / "f.mp4"
    synth.build(synth.Spec.from_dict({"segments": segs, "joins": [{"kind": "cut"}]}), out)
    base = ["cuts", str(out), "--detector", "framejump", "--threshold", "20"]
    main(base + ["--min-len", "1", "--flash-guard", "0"])
    unguarded = json.loads(capsys.readouterr().out)
    main(base + ["--flash-guard", "10"])
    guarded = json.loads(capsys.readouterr().out)
    assert 38 in unguarded and guarded == [48]


def test_unknown_label_is_kept_not_mapped():
    assert taxonomy.normalise("scale", "mcu") == "MCU"
    assert taxonomy.normalise("scale", "cowboy shot") == "unknown:cowboy shot"
