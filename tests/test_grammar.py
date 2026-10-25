import numpy as np
import pytest

from kubrick import grammar

# codes: 1 ECU .. 7 ELS on the ordinal ladder; 0 FS and 8 INS are off it; -1 not available


def test_segments_merge_held_scales_and_break_at_off_ladder_or_missing_labels():
    labels = np.array([7, 7, 6, 3, 3, -1, 2, 1, 0, 4, 5, 5])
    assert grammar.scale_segments(labels) == [[7, 6, 3], [2, 1], [4, 5]]


def test_a_segment_of_one_shot_has_no_transition_and_is_dropped():
    assert grammar.scale_segments(np.array([3, 3, -1, 4])) == []


def test_wide_then_closer_counts_moves_in_after_long_shots():
    assert grammar.wide_then_closer([[7, 3], [6, 7], [6, 2]]) == pytest.approx(2 / 3)
    assert np.isnan(grammar.wide_then_closer([[2, 3]]))


def test_one_step_share_counts_adjacent_scale_cuts():
    assert grammar.one_step_share([[3, 4, 6], [2, 1]]) == pytest.approx(2 / 3)


def test_the_null_uses_only_each_segments_own_scales():
    segs = [[7, 6, 3, 2], [5, 1]]
    draws = grammar.shuffled(segs, np.random.default_rng(0))
    assert [sorted(s) for s in draws] == [sorted(s) for s in segs]  # all distinct, so nothing merges
    for s in grammar.shuffled([[3, 4, 3, 2, 3]], np.random.default_rng(1)):
        assert set(s) <= {2, 3, 4}


def test_the_null_never_shows_two_equal_scales_in_a_row():
    # in the labels, two same-scale shots in a row merge into one run, so a reordering must merge them too,
    # or the null holds sequences the data can never show (this biased both measures, in opposite directions)
    rng = np.random.default_rng(0)
    for _ in range(200):
        for s in grammar.shuffled([[3, 4, 3, 2, 3, 6, 3]], rng):
            assert all(a != b for a, b in zip(s, s[1:])), s


def test_a_film_whose_shots_cannot_be_reordered_differently_is_at_its_null():
    # alternating two scales: every reordering merges back to some alternation, so one-step share cannot move
    segs = [[3, 4, 3, 4, 3, 4]]
    r = grammar.compare(segs, grammar.one_step_share, draws=50)
    assert r["observed"] == 1.0 and r["null_mean"] == 1.0 and r["above_null"] is False


def test_compare_reports_observed_null_and_whether_it_beats_it():
    # after ELS nothing is wider, so ELS alone cannot show the effect; an LS that a reordering can follow
    # with ELS can. Here every wide shot moves in, and shuffles sometimes put ELS after LS.
    segs = [[6, 2, 7, 3]] * 30
    r = grammar.compare(segs, grammar.wide_then_closer, draws=100, seed=0)
    assert r["observed"] == 1.0 and r["null_mean"] < 1.0 and r["above_null"]


def _director(tmp_path, name, films):
    d = tmp_path / name
    d.mkdir()
    for i, seq in enumerate(films):
        rows = "".join(f"{t},00:00:{t:02d},{c}\n" for t, c in enumerate(seq))
        (d / f"{i}.csv").write_text(",time,shotscale\n" + rows, encoding="utf-8")


MOVES_IN = [6, 6, 2, 2, 7, 7, 3, 3] * 6  # every wide shot cuts closer; reordered, LS sometimes meets ELS
MIXED = [6, 6, 7, 7, 2, 2, 6, 6, 7, 7, 3, 3] * 4  # LS often cuts wider


def test_replicate_holds_when_the_deriving_director_and_two_others_beat_the_null(tmp_path):
    for name in ("Scorsese", "Bergman", "Fellini", "Tarr"):
        _director(tmp_path, name, [MOVES_IN] * 3 if name != "Tarr" else [MIXED] * 3)
    r = grammar.replicate("wide-then-closer", tmp_path, derive="Scorsese", draws=60)
    assert r["verdict"] == "holds"
    assert r["directors"]["Tarr"]["replicates"] is False and r["directors"]["Bergman"]["replicates"] is True


def test_replicate_fails_when_too_few_directors_replicate(tmp_path):
    for name in ("Scorsese", "Bergman", "Fellini"):
        _director(tmp_path, name, [MOVES_IN] * 3 if name == "Scorsese" else [MIXED] * 3)
    assert grammar.replicate("wide-then-closer", tmp_path, derive="Scorsese", draws=60)["verdict"] == "does not hold"


def test_cli_rules_check_prints_the_verdict(tmp_path, capsys):
    import json

    from kubrick.cli import main

    for name in ("Scorsese", "Bergman", "Fellini"):
        _director(tmp_path, name, [MOVES_IN] * 3)
    assert main(["rules", "check", "wide-then-closer", "--labels", str(tmp_path), "--draws", "40"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["verdict"] == "holds"


def test_measured_rules_are_registered_with_their_statistic():
    assert grammar.MEASURES["wide-then-closer"] is grammar.wide_then_closer
    assert grammar.MEASURES["one-step-scale-cuts"] is grammar.one_step_share
