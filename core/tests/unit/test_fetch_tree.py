import pytest

from repo2ree_core.storage.fetch import download_or_copy
from repo2ree_core.storage.tree import copy_tree_contents


def test_download_or_copy_local_path(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"\x00\x01\x02data")

    dst = tmp_path / "dst.bin"
    result = download_or_copy(str(src), dst)

    assert result == dst
    assert dst.read_bytes() == b"\x00\x01\x02data"


def test_download_or_copy_preserves_mode(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    src.chmod(0o600)

    dst = tmp_path / "dst.bin"
    download_or_copy(str(src), dst)
    assert (dst.stat().st_mode & 0o777) == 0o600


def test_download_or_copy_missing_local_path_raises(tmp_path):
    dst = tmp_path / "dst.bin"
    with pytest.raises(FileNotFoundError):
        download_or_copy(str(tmp_path / "does-not-exist"), dst)


def test_copy_tree_contents_merges_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "preexisting.txt").write_text("keep")

    copy_tree_contents(src, dst)
    assert (dst / "a.txt").read_text() == "a"
    assert (dst / "b.txt").read_text() == "b"
    assert (dst / "preexisting.txt").read_text() == "keep"


def test_copy_tree_contents_merges_nested_dirs(tmp_path):
    src = tmp_path / "src"
    (src / "dir" / "nested").mkdir(parents=True)
    (src / "dir" / "nested" / "x.txt").write_text("x")

    dst = tmp_path / "dst"
    (dst / "dir").mkdir(parents=True)
    (dst / "dir" / "y.txt").write_text("y")

    copy_tree_contents(src, dst)
    assert (dst / "dir" / "nested" / "x.txt").read_text() == "x"
    assert (dst / "dir" / "y.txt").read_text() == "y"


def test_copy_tree_contents_creates_destination_if_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")

    dst = tmp_path / "new-dest"  # does not exist
    copy_tree_contents(src, dst)
    assert (dst / "a.txt").read_text() == "a"


def test_copy_tree_contents_single_file_placed_under_destination(tmp_path):
    src = tmp_path / "loose.txt"
    src.write_text("loose")

    dst = tmp_path / "dst"
    dst.mkdir()

    copy_tree_contents(src, dst)
    assert (dst / "loose.txt").read_text() == "loose"
