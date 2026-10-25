import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# built from parts so this file does not match itself
PATHS = ["/Volumes/" + "Media", "Videos/" + "Movies"]
LIBRARY = re.compile("|".join(map(re.escape, PATHS)), re.IGNORECASE)


def library_leaks(repo: Path) -> list[str]:
    """Tracked files and commit messages that name the film library's location. The repo is public;
    titles are checked by a local scan, since listing them here would publish them."""
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout
    bad = []
    for name in git("ls-files", "-z").split("\0"):
        path = repo / name
        if name and path.is_file() and LIBRARY.search(path.read_text(encoding="utf-8", errors="replace")):
            bad.append(name)
    for line in git("log", "--all", "--format=%H %B%x00").split("\0"):
        if LIBRARY.search(line):
            bad.append(f"commit {line.strip()[:12]}")
    return bad


def repo_with(tmp_path, text, message="add"):
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, check=True)
    git("init", "-q")
    (tmp_path / "notes.md").write_text(text, encoding="utf-8")
    git("add", "notes.md")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)
    return tmp_path


def test_the_repo_never_names_the_film_library():
    assert library_leaks(ROOT) == []


def test_a_tracked_file_naming_the_library_is_caught(tmp_path):
    assert library_leaks(repo_with(tmp_path, f"films are under {PATHS[0].lower()}/x\n")) == ["notes.md"]


def test_a_commit_message_naming_the_library_is_caught(tmp_path):
    found = library_leaks(repo_with(tmp_path, "nothing here\n", f"read from {PATHS[1]}"))
    assert len(found) == 1 and found[0].startswith("commit ")


def test_an_innocent_repo_passes(tmp_path):
    assert library_leaks(repo_with(tmp_path, "models live in /Volumes/Models/hf\n")) == []


def test_ci_checks_out_the_whole_history_the_commit_scan_reads():
    # with the default depth of 1 the commit scan sees one commit and passes without looking
    import yaml

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    checkout = [s for s in wf["jobs"]["check"]["steps"] if s.get("uses", "").startswith("actions/checkout@")]
    assert checkout and all(s.get("with", {}).get("fetch-depth") == 0 for s in checkout)
