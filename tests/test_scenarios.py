from kubrick import scenarios

ISSUE = """## Acceptance
#### Scenario: a door that does not open
#### Scenario: Keys, to the kingdom!
- Eric approves the animatic.
"""


def make_tests(tmp_path, files):
    d = tmp_path / "tests"
    d.mkdir()
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def test_a_scenario_with_no_test_fails_the_scanner(tmp_path):
    d = make_tests(tmp_path, {"test_a.py": "def test_a_door_that_does_not_open():\n    pass\n"})
    r = scenarios.check(scenarios.parse(ISSUE), d)
    assert r["missing"] == ["Keys, to the kingdom!"] and not r["ok"]


def test_a_test_beside_scenario_tests_that_implements_none_is_reported(tmp_path):
    d = make_tests(tmp_path, {
        "test_a.py": "def test_a_door_that_does_not_open():\n    pass\n\ndef test_keys_to_the_kingdom():\n    pass\n\n"
                     "def test_something_else():\n    pass\n",
        "test_b.py": "def test_unrelated():\n    pass\n",  # a file with no scenario tests is not judged
    })
    r = scenarios.check(scenarios.parse(ISSUE), d)
    assert r["missing"] == [] and r["orphans"] == ["test_a.py::test_something_else"] and not r["ok"]


def test_an_issue_with_no_scenarios_passes(tmp_path):
    d = make_tests(tmp_path, {"test_b.py": "def test_unrelated():\n    pass\n"})
    r = scenarios.check(scenarios.parse("## Acceptance\n- a prose check only\n"), d)
    assert r == {"missing": [], "orphans": [], "ok": True}


def test_the_pull_request_body_s_issue_numbers_are_the_ones_checked():
    body = "Part of #20. Closes #3, fixes #5 and resolves #7.\nSee #13 for background; Does not close #2."
    assert scenarios.issues_named(body) == [3, 5, 7, 20]
