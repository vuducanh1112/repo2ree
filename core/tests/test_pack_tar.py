import tarfile

from repo2ree_core.storage.extract import pack_directory_tar_gz


def test_packs_top_level_entries_under_their_own_names(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    (src / "b.txt").write_text("beta")

    archive = tmp_path / "out.tar.gz"
    pack_directory_tar_gz(src, archive)

    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
    assert names == ["a.txt", "b.txt"]


def test_packs_nested_directories(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "dir").mkdir()
    (src / "dir" / "nested.txt").write_text("x")

    archive = tmp_path / "out.tar.gz"
    pack_directory_tar_gz(src, archive)

    with tarfile.open(archive) as tar:
        names = set(tar.getnames())
    assert "dir" in names
    assert "dir/nested.txt" in names


def test_top_level_entries_added_in_sorted_order(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for name in ("c", "a", "b"):
        (src / name).write_text(name)

    archive = tmp_path / "out.tar.gz"
    pack_directory_tar_gz(src, archive)

    with tarfile.open(archive) as tar:
        top_level = [n for n in tar.getnames() if "/" not in n]
    assert top_level == ["a", "b", "c"]


def test_empty_source_produces_empty_archive(tmp_path):
    src = tmp_path / "src"
    src.mkdir()

    archive = tmp_path / "out.tar.gz"
    pack_directory_tar_gz(src, archive)

    with tarfile.open(archive) as tar:
        assert tar.getnames() == []


def test_creates_parent_directory_if_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a").write_text("a")

    archive = tmp_path / "new" / "dir" / "out.tar.gz"
    pack_directory_tar_gz(src, archive)

    assert archive.is_file()
