import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def ffmpeg_calls_without_nostdin(root: Path) -> list[str]:
    """Every list literal starting with "ffmpeg" must contain "-nostdin": without it, ffmpeg run
    inside a `while read` loop eats the loop's input as interactive commands."""
    bad = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant) \
                    and node.elts[0].value == "ffmpeg":
                if not any(isinstance(e, ast.Constant) and e.value == "-nostdin" for e in node.elts):
                    bad.append(f"{path.name}:{node.lineno}")
    return bad


def test_every_ffmpeg_call_has_nostdin():
    assert ffmpeg_calls_without_nostdin(SRC) == []


def test_scanner_fires_on_a_bare_ffmpeg_call(tmp_path):
    (tmp_path / "bad.py").write_text('cmd = ["ffmpeg", "-i", "x.mp4"]\n', encoding="utf-8")
    (tmp_path / "good.py").write_text('cmd = ["ffmpeg", "-nostdin", "-i", "x.mp4"]\n', encoding="utf-8")
    assert ffmpeg_calls_without_nostdin(tmp_path) == ["bad.py:1"]
