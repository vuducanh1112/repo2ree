from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from repo2ree_testbed.exercise import BundleCorruption, LoadReeBundle
from repo2ree_testbed.exercise_bundle import corrupted

_IDENTITY = ("-c", "user.name=ree", "-c", "user.email=ree@repo2ree.invalid")


def _git(root: Path, *words: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *_IDENTITY, *words], check=True, capture_output=True, text=True
    ).stdout.strip()


def _bundle(tmp_path: Path) -> tuple[bytes, str]:
    """A bundle as ``ree bundle`` lays one out: export.json naming the REE's head, its history and its files."""
    root = tmp_path / "ree"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "ree.json").write_text("{}\n")
    _git(root, "add", "ree.json")
    _git(root, "commit", "-q", "-m", "ree")
    head = _git(root, "rev-parse", "HEAD")
    written = io.BytesIO()
    with zipfile.ZipFile(written, "w") as bundle:
        bundle.writestr("export.json", json.dumps({"scopes": [{"scope": ".", "head": head}]}))
        for path in sorted(root.rglob("*")):
            if path.is_file():
                bundle.write(path, f"ree/{path.relative_to(root).as_posix()}")
    return written.getvalue(), head


def _read(archive: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        return {name: bundle.read(name) for name in bundle.namelist()}


def _head(entries: dict[str, bytes]) -> str:
    return str(json.loads(entries["export.json"])["scopes"][0]["head"])


def _unpacked(tmp_path: Path, entries: dict[str, bytes]) -> Path:
    git_dir = tmp_path / "unpacked" / ".git"
    for name, content in entries.items():
        if name.startswith("ree/.git/"):
            target = git_dir / name.removeprefix("ree/.git/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return git_dir


def test_an_intact_bundle_is_handed_over_as_it_was_given(tmp_path: Path) -> None:
    archive, _ = _bundle(tmp_path)
    assert corrupted(archive, "intact", 0) == archive


def test_a_truncated_bundle_is_no_archive(tmp_path: Path) -> None:
    archive, _ = _bundle(tmp_path)
    with pytest.raises(zipfile.BadZipFile):
        _read(corrupted(archive, "truncated", 0))


def test_a_bundle_with_an_unknown_head_names_a_commit_its_history_does_not_hold(tmp_path: Path) -> None:
    archive, head = _bundle(tmp_path)
    entries = _read(corrupted(archive, "unknown_head", 3))
    named = _head(entries)
    assert named != head
    git_dir = _unpacked(tmp_path, entries)
    assert subprocess.run(["git", "--git-dir", str(git_dir), "cat-file", "-e", named], check=False).returncode != 0


def test_a_bundle_with_its_objects_removed_keeps_everything_else(tmp_path: Path) -> None:
    archive, head = _bundle(tmp_path)
    given, entries = _read(archive), _read(corrupted(archive, "objects_removed", 0))
    assert not [name for name in entries if name.startswith("ree/.git/objects/")]
    assert {name: content for name, content in given.items() if not name.startswith("ree/.git/objects/")} == entries
    assert _head(entries) == head


def test_a_bundle_with_a_file_changed_beside_its_history_keeps_the_history(tmp_path: Path) -> None:
    archive, head = _bundle(tmp_path)
    given, entries = _read(archive), _read(corrupted(archive, "file_changed", 0))
    assert entries["ree/ree.json"] != given["ree/ree.json"]
    assert {name: content for name, content in entries.items() if name != "ree/ree.json"} == {
        name: content for name, content in given.items() if name != "ree/ree.json"
    }
    assert _head(entries) == head


def test_a_bundle_with_a_foreign_commit_names_it_as_the_head_on_top_of_the_given_one(tmp_path: Path) -> None:
    archive, head = _bundle(tmp_path)
    entries = _read(corrupted(archive, "foreign_commit", 5))
    named = _head(entries)
    git_dir = _unpacked(tmp_path, entries)
    parent = subprocess.run(
        ["git", "--git-dir", str(git_dir), "rev-parse", f"{named}^"], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert parent == head
    files = subprocess.run(
        ["git", "--git-dir", str(git_dir), "ls-tree", "--name-only", named], check=True, capture_output=True, text=True
    ).stdout.split()
    assert files == ["damaged-5.txt", "ree.json"]


@pytest.mark.parametrize("corruption", ["unknown_head", "objects_removed", "file_changed", "foreign_commit"])
def test_a_bundle_that_is_no_archive_is_handed_over_as_it_was(corruption: BundleCorruption) -> None:
    assert corrupted(b"not a bundle", corruption, 0) == b"not a bundle"


def test_an_intact_load_is_written_as_before_bundles_could_be_damaged() -> None:
    assert "corruption" not in LoadReeBundle(ree="reviewer", exported_by="author").model_dump()
    assert LoadReeBundle(ree="reviewer", exported_by="author", corruption="truncated").model_dump()["corruption"] == (
        "truncated"
    )
