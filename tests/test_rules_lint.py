from pathlib import Path

import pytest

from kubrick import continuity, rules

GOOD = """# Coverage

## wide-then-closer
- kind: measured
- decision: After a long shot, cut closer, not wider.
- applies when: A scene has placed its action and the next shot follows the same subjects.
- check: The shot after an LS or ELS has a closer scale in the shot list.
- counterexample: A deliberate pull-back to reveal a new element.
- data check: kubrick rules check wide-then-closer
- sources:
  - Smith 2012, Projections 6(1), section 3: continuity rules guide attention across a cut.

## axis-180
- kind: practice
- decision: Keep the camera on one side of the line between two characters who face each other.
- applies when: Two characters share a scene and the cut stays with them.
- check: kubrick continuity reports no axis-180 line for the scene.
- counterexample: A deliberate cross to mark a turn in the scene, shown on screen first.
- enforces: axis-180
- sources:
  - Smith 2012, Projections 6(1), section 4: the 180 degree rule keeps screen positions stable.
  - Kraft 1987, Journal of Memory and Language 26, p. 299: direction changes hurt recall of the action.
"""


def write(tmp_path, text, name="coverage.md"):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def all_enforced(text):
    extra = "".join(f"""
## {rid}-rule
- kind: practice
- decision: d.
- applies when: a.
- check: c.
- counterexample: x.
- enforces: {rid}
- sources:
  - A one, p. 1: s.
  - B two, p. 2: s.
""" for rid in continuity.RULES if rid != "axis-180")
    return text + extra


def test_a_complete_rule_set_passes(tmp_path):
    assert rules.lint(write(tmp_path, all_enforced(GOOD))) == []


@pytest.mark.parametrize("cut,needle", [
    ("- check: The shot after an LS or ELS has a closer scale in the shot list.\n", "check"),
    ("- counterexample: A deliberate pull-back to reveal a new element.\n", "counterexample"),
    ("  - Kraft 1987, Journal of Memory and Language 26, p. 299: direction changes hurt recall of the action.\n",
     "two sources"),
    ("- data check: kubrick rules check wide-then-closer\n", "data check"),
])
def test_a_rule_missing_a_part_fails(tmp_path, cut, needle):
    errors = rules.lint(write(tmp_path, all_enforced(GOOD.replace(cut, "", 1))))
    assert any(needle in e for e in errors), errors


def test_a_long_quotation_fails(tmp_path):
    quoted = GOOD.replace("continuity rules guide attention across a cut.",
                          '"' + " ".join(["word"] * 16) + '"', 1)
    assert any("quotation" in e for e in rules.lint(write(tmp_path, all_enforced(quoted))))


def test_a_checker_rule_no_run_book_cites_fails(tmp_path):
    assert any("not cited" in e for e in rules.lint(write(tmp_path, GOOD)))


def test_citing_a_checker_rule_that_does_not_exist_fails(tmp_path):
    bad = all_enforced(GOOD).replace("- enforces: axis-180", "- enforces: axis-360", 1)
    assert any("axis-360" in e for e in rules.lint(write(tmp_path, bad)))


def test_a_data_check_for_an_unregistered_measure_fails(tmp_path):
    bad = all_enforced(GOOD).replace("kubrick rules check wide-then-closer", "kubrick rules check vibes", 1)
    assert any("vibes" in e for e in rules.lint(write(tmp_path, bad)))


def test_an_unknown_kind_fails(tmp_path):
    bad = all_enforced(GOOD).replace("- kind: measured", "- kind: folklore", 1)
    assert any("folklore" in e for e in rules.lint(write(tmp_path, bad)))


def test_the_real_grammar_run_books_pass_the_lint():
    root = Path(__file__).resolve().parents[1] / "runbooks" / "grammar"
    assert rules.lint(root) == []
