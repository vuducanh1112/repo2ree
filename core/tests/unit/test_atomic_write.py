import json
import os
from unittest.mock import patch

import pytest

from repo2ree_core.ree.files import json_document_bytes, write_atomic, write_json_atomic


def test_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "deep" / "nested" / "file.json"
    write_atomic(target, b"payload")
    assert target.read_bytes() == b"payload"


def test_replaces_existing_content(tmp_path):
    target = tmp_path / "file"
    target.write_bytes(b"old")
    write_atomic(target, b"new")
    assert target.read_bytes() == b"new"


def test_leaves_no_temporary_behind_on_success(tmp_path):
    write_atomic(tmp_path / "file", b"payload")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["file"]


def test_a_failed_write_leaves_the_previous_version_intact(tmp_path):
    """The whole point: an interrupted write must not publish a partial file."""
    target = tmp_path / "file"
    target.write_bytes(b"the version a reader must still see")

    with patch("repo2ree_core.ree.files.os.replace", side_effect=OSError("boom")), pytest.raises(OSError):
        write_atomic(target, b"never published")

    assert target.read_bytes() == b"the version a reader must still see"


def test_a_failed_write_leaves_no_temporary_behind(tmp_path):
    target = tmp_path / "file"
    target.write_bytes(b"original")

    with patch("repo2ree_core.ree.files.os.replace", side_effect=OSError("boom")), pytest.raises(OSError):
        write_atomic(target, b"discarded")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["file"]


def test_cancellation_mid_write_leaves_no_temporary_behind(tmp_path):
    """KeyboardInterrupt is not an ``Exception`` — the cleanup catches it anyway."""
    target = tmp_path / "file"

    with patch("repo2ree_core.ree.files.os.replace", side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
        write_atomic(target, b"discarded")

    assert list(tmp_path.iterdir()) == []


def test_concurrent_writers_do_not_share_a_temporary(tmp_path):
    """Two writes to one path must not be able to publish each other's bytes."""
    target = tmp_path / "file"
    seen = []

    real_replace = os.replace

    def capture(src, dst):
        seen.append(str(src))
        return real_replace(src, dst)

    with patch("repo2ree_core.ree.files.os.replace", side_effect=capture):
        write_atomic(target, b"first")
        write_atomic(target, b"second")

    assert seen[0] != seen[1]


def test_json_document_is_indented_and_key_sorted(tmp_path):
    """The persisted spelling: readable and diffable, so a diff is about values."""
    assert json_document_bytes({"b": 1, "a": 2}) == b'{\n  "a": 2,\n  "b": 1\n}'


def test_write_json_atomic_round_trips(tmp_path):
    target = tmp_path / "doc.json"
    payload = {"nested": {"z": 1, "a": [1, 2]}, "top": "value"}
    write_json_atomic(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload
