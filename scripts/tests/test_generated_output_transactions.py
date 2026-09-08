from pathlib import Path

import pytest
from scripts.publish import image_archive_set
from scripts.replace_generated_directory import replace_directory


def archive_set(path: Path) -> None:
    path.mkdir()
    for name in image_archive_set.ARCHIVES:
        (path / name).write_bytes(name.encode())


def test_sealed_image_archive_set_detects_changed_archive(tmp_path: Path) -> None:
    directory = tmp_path / "images"
    archive_set(directory)
    image_archive_set.seal(directory, "revision-1")

    assert image_archive_set.verify(directory) == "revision-1"

    (directory / image_archive_set.ARCHIVES[0]).write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        image_archive_set.verify(directory)


def test_generated_directory_replacement_removes_stale_outputs(tmp_path: Path) -> None:
    target = tmp_path / "journals"
    target.mkdir()
    (target / "stale.html").write_text("stale")
    staging = tmp_path / ".journals.pending"
    staging.mkdir()
    (staging / "current.html").write_text("current")

    replace_directory(staging, target)

    assert not (target / "stale.html").exists()
    assert (target / "current.html").read_text() == "current"
    assert not staging.exists()
