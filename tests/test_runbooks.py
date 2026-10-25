import re
from pathlib import Path

from kubrick import continuity, taxonomy


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "runbooks" / "workflow.md"


def test_every_command_the_workflow_names_exists():
    from kubrick import cli

    named = set(re.findall(r"uv run kubrick ([a-z-]+)", WORKFLOW.read_text(encoding="utf-8")))
    assert named and named <= cli.commands(), named - cli.commands()


def test_the_workflow_names_every_continuity_rule():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert all(f"`{r}`" in text for r in continuity.RULES), [r for r in continuity.RULES if f"`{r}`" not in text]


def test_the_workflow_says_taxonomy_labels_come_from_taxonomy_toml():
    assert "taxonomy.toml" in WORKFLOW.read_text(encoding="utf-8")
    assert taxonomy.labels("scale") and taxonomy.labels("movement")


def test_the_workflow_has_no_long_dashes():
    assert "—" not in WORKFLOW.read_text(encoding="utf-8")


def grammar_ids():
    return {m for p in (ROOT / "runbooks" / "grammar").glob("*.md")
            for m in re.findall(r"^## ([a-z0-9-]+)$", p.read_text(encoding="utf-8"), re.M)}


def test_every_rule_the_workflow_cites_exists_in_a_grammar_run_book():
    # a rule renamed or dropped in runbooks/grammar must not leave the workflow pointing at nothing
    cited = {c for c in re.findall(r"\(`([a-z0-9]+(?:-[a-z0-9]+)+)`\)", WORKFLOW.read_text(encoding="utf-8"))}
    assert len(cited) >= 7 and cited <= grammar_ids(), cited - grammar_ids()
