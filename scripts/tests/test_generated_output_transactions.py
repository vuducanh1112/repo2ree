from pathlib import Path

import pytest
from scripts.publish import image_archive_set
from scripts.replace_generated_directory import replace_directory

IMAGE_IDS = {image: "sha256:" + str(index) * 64 for index, image in enumerate(image_archive_set.IMAGES, start=1)}


def archive_set(path: Path) -> None:
    path.mkdir()
    for image in image_archive_set.IMAGES:
        (path / image_archive_set.archive_name(image)).write_bytes(image.encode())


def test_sealed_image_archive_set_names_what_was_certified_and_detects_a_changed_archive(tmp_path: Path) -> None:
    directory = tmp_path / "linux-amd64"
    archive_set(directory)
    image_archive_set.seal(directory, revision="revision-1", tree="tree-1", platform="linux/amd64", images=IMAGE_IDS)

    verified = image_archive_set.verify(directory)
    assert (verified.revision, verified.tree, verified.platform) == ("revision-1", "tree-1", "linux/amd64")
    assert verified.images == IMAGE_IDS
    assert image_archive_set.sets(tmp_path) == [verified]

    (directory / image_archive_set.archive_name(image_archive_set.IMAGES[0])).write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="changed"):
        image_archive_set.verify(directory)


def test_an_archive_set_holds_every_image_by_its_id(tmp_path: Path) -> None:
    directory = tmp_path / "linux-amd64"
    archive_set(directory)
    with pytest.raises(RuntimeError, match="each by its image ID"):
        image_archive_set.seal(
            directory, revision="revision-1", tree="t", platform="linux/amd64", images={"repo2ree-gui": "local"}
        )


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
