"""Grammar run book rules: parse, lint, and recompute the measured ones."""

import re
from pathlib import Path

from kubrick import continuity, grammar

KINDS = ("measured", "practice", "refuted")
REQUIRED = ("kind", "decision", "applies when", "check", "counterexample")
MAX_QUOTE_WORDS = 15
QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')


def parse(text: str) -> list[dict]:
    """Each `## id` section as {"id", fields..., "sources": [...]}; `- key: value` lines are fields."""
    out, cur, in_sources = [], None, False
    for line in text.splitlines():
        if line.startswith("## "):
            cur = {"id": line[3:].strip(), "sources": []}
            out.append(cur)
            in_sources = False
        elif cur is None:
            continue
        elif line.startswith("  - ") and in_sources:
            cur["sources"].append(line[4:].strip())
        elif line.startswith("- "):
            key, _, value = line[2:].partition(":")
            in_sources = key.strip() == "sources"
            if not in_sources:
                cur[key.strip()] = value.strip()
    return out


def lint(root: Path) -> list[str]:
    errors, enforced = [], set()
    files = sorted(Path(root).glob("*.md"))
    if not files:
        return [f"{root}: no rule files"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for m in QUOTE.finditer(text):
            words = len((m.group(1) or m.group(2)).split())
            if words > MAX_QUOTE_WORDS:
                errors.append(f"{path.name}: quotation of {words} words; paraphrase instead")
        for r in parse(text):
            where = f"{path.name} {r['id']}"
            for field in REQUIRED:
                if not r.get(field):
                    errors.append(f"{where}: no {field}")
            kind = r.get("kind")
            if kind and kind not in KINDS:
                errors.append(f"{where}: kind {kind} is not one of {', '.join(KINDS)}")
            if kind == "practice" and len(r["sources"]) < 2:
                errors.append(f"{where}: a practice rule needs two sources, has {len(r['sources'])}")
            if kind in ("measured", "refuted"):
                if not r["sources"]:
                    errors.append(f"{where}: no sources")
                check = r.get("data check", "")
                m = re.fullmatch(r"kubrick rules check ([a-z0-9-]+)", check)
                if not m:
                    errors.append(f"{where}: a {kind} rule needs a data check `kubrick rules check <id>`")
                elif m.group(1) not in grammar.MEASURES:
                    errors.append(f"{where}: data check names {m.group(1)}, which has no registered measure")
            if r.get("enforces"):
                for rid in (x.strip() for x in r["enforces"].split(",")):
                    if rid not in continuity.RULES:
                        errors.append(f"{where}: enforces {rid}, which the continuity checker does not have")
                    enforced.add(rid)
    for rid in sorted(set(continuity.RULES) - enforced):
        errors.append(f"continuity rule {rid} is not cited by any grammar rule")
    return errors
