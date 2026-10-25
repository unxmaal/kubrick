import tomllib
from functools import cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "taxonomy.toml"


@cache
def load(path: Path = TAXONOMY_PATH) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def labels(axis: str) -> list[str]:
    return list(load()[axis]["labels"])


def normalise(axis: str, value: str) -> str:
    """Return the label if the taxonomy knows it, else `unknown:<value>`; never the nearest label."""
    known = {label.lower(): label for label in labels(axis)}
    return known.get(value.strip().lower(), f"unknown:{value.strip()}")
