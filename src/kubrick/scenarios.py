"""An issue's `#### Scenario:` lines mapped to tests named after them, checked both ways (#20)."""

import re
import subprocess
from pathlib import Path

SCENARIO = re.compile(r"^#### Scenario: (.+?)\s*$", re.M)
TEST = re.compile(r"^def (test_\w+)", re.M)
NAMED = re.compile(r"(?<!not )\b(?:part of|close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+((?:#\d+(?:,\s*|\s+and\s+)?)+)", re.I)


def parse(body: str) -> list[str]:
    return SCENARIO.findall(body)


def slug(name: str) -> str:
    return "test_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def check(names: list[str], tests: Path) -> dict:
    """missing: scenarios with no test of their slug. orphans: in a file holding any of these scenarios'
    tests, every test that implements none of them."""
    wanted = {slug(n) for n in names}
    found = {f: TEST.findall(f.read_text(encoding="utf-8")) for f in sorted(Path(tests).rglob("test_*.py"))}
    defined = {t for ts in found.values() for t in ts}
    missing = [n for n in names if slug(n) not in defined]
    orphans = [f"{f.relative_to(tests)}::{t}" for f, ts in found.items() if wanted & set(ts) for t in ts if t not in wanted]
    return {"missing": missing, "orphans": orphans, "ok": not missing and not orphans}


def issues_named(pr_body: str) -> list[int]:
    """Issues a pull request says it is part of or closes; a bare mention or "does not close #N" is not one."""
    return sorted({int(n) for group in NAMED.findall(pr_body) for n in re.findall(r"#(\d+)", group)})


def issue_body(number: int, repo: str | None = None) -> str:
    args = ["gh", "issue", "view", str(number), "--json", "body", "-q", ".body"] + (["--repo", repo] if repo else [])
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout
