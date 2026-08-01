import pytest

from repo2ree_core.persistence.files import download_or_copy


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
