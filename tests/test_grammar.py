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


def test_the_null_keeps_each_segments_scales_and_only_reorders_them():
    segs = [[7, 6, 3, 2], [5, 1]]
    draws = grammar.shuffled(segs, np.random.default_rng(0))
    assert [sorted(s) for s in draws] == [sorted(s) for s in segs]


def test_compare_reports_observed_null_and_whether_it_beats_it():
    # after ELS nothing is wider, so ELS alone cannot show the effect; an LS that a reordering can follow
    # with ELS can. Here every wide shot moves in, and shuffles sometimes put ELS after LS.
    segs = [[6, 2, 7, 3]] * 30
    r = grammar.compare(segs, grammar.wide_then_closer, draws=100, seed=0)
    assert r["observed"] == 1.0 and r["null_mean"] < 1.0 and r["above_null"]


def test_measured_rules_are_registered_with_their_statistic():
    assert grammar.MEASURES["wide-then-closer"] is grammar.wide_then_closer
    assert grammar.MEASURES["one-step-scale-cuts"] is grammar.one_step_share
