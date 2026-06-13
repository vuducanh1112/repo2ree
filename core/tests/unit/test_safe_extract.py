import io
import tarfile
import zipfile
from pathlib import Path

from repo2ree_core.storage.extract import safe_extract_tar, safe_extract_zip


def _write_tar(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with tarfile.open(path, mode="w") as tar:
        for name, content in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))


def _write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, mode="w") as zf:
        for name, content in entries:
            zf.writestr(name, content)


def test_tar_extracts_normal_entries(tmp_path):
    archive = tmp_path / "src.tar"
    _write_tar(archive, [("a.txt", b"a"), ("dir/b.txt", b"b")])

    dest = tmp_path / "out"
    dest.mkdir()
    safe_extract_tar(archive, dest)

    assert (dest / "a.txt").read_bytes() == b"a"
    assert (dest / "dir" / "b.txt").read_bytes() == b"b"


def test_tar_skips_parent_traversal_entry(tmp_path):
    archive = tmp_path / "evil.tar"
    _write_tar(archive, [("../escape.txt", b"x"), ("legit.txt", b"ok")])

    dest = tmp_path / "out"
    dest.mkdir()
    safe_extract_tar(archive, dest)

    assert (dest / "legit.txt").read_bytes() == b"ok"
    assert not (tmp_path / "escape.txt").exists()


def test_tar_skips_absolute_path_entry(tmp_path):
    archive = tmp_path / "abs.tar"
    _write_tar(archive, [("/tmp/escape.txt", b"x"), ("good.txt", b"ok")])  # noqa: S108

    dest = tmp_path / "out"
    dest.mkdir()
    safe_extract_tar(archive, dest)

    assert (dest / "good.txt").read_bytes() == b"ok"


def test_zip_extracts_normal_entries(tmp_path):
    archive = tmp_path / "src.zip"
    _write_zip(archive, [("a.txt", b"a"), ("dir/b.txt", b"b")])

    dest = tmp_path / "out"
    dest.mkdir()
    safe_extract_zip(archive, dest)

    assert (dest / "a.txt").read_bytes() == b"a"
    assert (dest / "dir" / "b.txt").read_bytes() == b"b"


def test_zip_skips_parent_traversal_entry(tmp_path):
    archive = tmp_path / "evil.zip"
    _write_zip(archive, [("../escape.txt", b"x"), ("legit.txt", b"ok")])

    dest = tmp_path / "out"
    dest.mkdir()
    safe_extract_zip(archive, dest)

    assert (dest / "legit.txt").read_bytes() == b"ok"
    assert not (tmp_path / "escape.txt").exists()
