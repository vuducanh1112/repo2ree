from __future__ import annotations

import hashlib

from repo2ree_core.digests import (
    digest_bytes,
    digest_file,
    digest_file_if_exists,
    digest_json,
    digest_tree,
)
from repo2ree_core.storage.extract import pack_directory_tar_gz


def test_digest_bytes_is_prefixed_sha256():
    assert digest_bytes(b"hello") == "sha256:" + hashlib.sha256(b"hello").hexdigest()


def test_digest_file_matches_digest_bytes(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"content")
    assert digest_file(path) == digest_bytes(b"content")


def test_digest_file_if_exists_returns_none_for_missing_or_dir(tmp_path):
    assert digest_file_if_exists(tmp_path / "absent") is None
    assert digest_file_if_exists(tmp_path) is None


def test_digest_json_is_canonical_across_key_order_and_whitespace():
    assert digest_json({"a": 1, "b": [2, 3]}) == digest_json({"b": [2, 3], "a": 1})
    assert digest_json({"a": 1}) != digest_json({"a": 2})


def test_digest_tree_depends_on_paths_and_content(tmp_path):
    root = tmp_path / "tree"
    (root / "d").mkdir(parents=True)
    (root / "a.txt").write_text("alpha")
    (root / "d" / "b.txt").write_text("beta")
    before = digest_tree(root)

    (root / "d" / "b.txt").write_text("changed")
    assert digest_tree(root) != before

    (root / "d" / "b.txt").write_text("beta")
    assert digest_tree(root) == before


def test_digest_tree_of_absent_dir_is_stable(tmp_path):
    assert digest_tree(tmp_path / "absent") == digest_tree(tmp_path / "also-absent")


def test_pack_directory_tar_gz_returns_digest_of_written_archive(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")

    archive = tmp_path / "out.tar.gz"
    digest = pack_directory_tar_gz(src, archive)

    assert digest == digest_file(archive)
