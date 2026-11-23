from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from repo2ree_core.digests import digest_file, digest_file_if_exists, digest_output_paths, digest_tree
from repo2ree_core.persistence.files import pack_directory_tar_gz
from repo2ree_ree.digest import digest_bytes, digest_json


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


def test_digest_output_paths_none_when_nothing_declared(tmp_path):
    assert digest_output_paths(tmp_path, []) is None


def test_digest_output_paths_tracks_files_and_dirs(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "out.txt").write_text("a")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "plot.png").write_bytes(b"img")

    before = digest_output_paths(tmp_path, ["results/out.txt", "figures"])
    assert before is not None
    assert digest_output_paths(tmp_path, ["figures", "results/out.txt"]) == before
    (tmp_path / "figures" / "plot.png").write_bytes(b"img2")
    assert digest_output_paths(tmp_path, ["results/out.txt", "figures"]) != before


def test_pack_directory_tar_gz_returns_digest_of_written_archive(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")

    archive = tmp_path / "out.tar.gz"
    digest = pack_directory_tar_gz(src, archive)

    assert digest == digest_file(archive)


def _fixture() -> dict[str, list[dict[str, Any]]]:
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "contracts").is_dir())
    fixture: dict[str, list[dict[str, Any]]] = json.loads(
        (root / "contracts" / "ree" / "fixtures" / "digests.json").read_text(encoding="utf-8")
    )
    return fixture


def _written(root: Path, files: dict[str, str]) -> Path:
    for path, content in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8")
    return root


def test_digest_tree_is_the_one_the_format_pins(tmp_path):
    for index, case in enumerate(_fixture()["tree"]):
        assert digest_tree(_written(tmp_path / str(index), case["files"])) == case["digest"], case["name"]


def test_digest_output_paths_is_the_one_the_format_pins(tmp_path):
    for index, case in enumerate(_fixture()["paths"]):
        root = _written(tmp_path / str(index), case["files"])
        assert digest_output_paths(root, case["paths"]) == case["digest"], case["name"]
