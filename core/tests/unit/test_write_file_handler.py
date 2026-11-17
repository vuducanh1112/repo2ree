"""Unit coverage for the write_file operations handler's optimistic-concurrency guard.

The handler runs for real against an REE in a tmp root.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from repo2ree_core.operations.handlers.author import write_file as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import WriteFileArgs
from repo2ree_ree.model import Ree, ReeDefinition, ReeSubject
from repo2ree_ree.reserved_paths import (
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
    experiment_run_script_path,
)

# A fixed script with no file yet: the launch of an REE from before every REE had one.
UNWRITTEN = RESERVED_LAUNCH_SCRIPT


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


def _etag(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _store_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
    store = ReeDirectory(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    store.write_ree(Ree(subject=ReeSubject(definition=ReeDefinition(name="demo"))))
    return store


def test_matching_etag_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)
    store.workspace.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, b"old body")

    result = handler.handle_write_file(
        WriteFileArgs(
            path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, content="new body", expected_etag=_etag(b"old body")
        ),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=store.layout,
    )

    assert result.status == "succeeded"
    assert store.workspace.read_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT) == b"new body"


def test_stale_etag_conflicts_without_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)
    store.workspace.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, b"current body")

    result = handler.handle_write_file(
        WriteFileArgs(
            path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, content="new body", expected_etag=_etag(b"stale body")
        ),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=store.layout,
    )

    assert result.status == "failed"
    assert result.outputs["error_code"] == "version_conflict"
    assert result.outputs["expected_version"] == _etag(b"stale body")
    assert result.outputs["actual_version"] == _etag(b"current body")
    assert store.workspace.read_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT) == b"current body"


def test_expected_etag_against_missing_file_conflicts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)

    result = handler.handle_write_file(
        WriteFileArgs(path=UNWRITTEN, content="body", expected_etag=_etag(b"anything")),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=ReeLayout(root=tmp_path),
    )

    assert result.status == "failed"
    assert result.outputs["error_code"] == "version_conflict"
    assert result.outputs["actual_version"] is None


def test_no_expected_etag_skips_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)

    result = handler.handle_write_file(
        WriteFileArgs(path=UNWRITTEN, content="body"), log=_silent_log, is_canceled=_never_canceled, layout=store.layout
    )

    assert result.status == "succeeded"
    assert store.workspace.read_bytes(UNWRITTEN) == b"body"


def test_an_undeclared_experiments_script_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)
    path = experiment_run_script_path("hello")

    result = handler.handle_write_file(
        WriteFileArgs(path=path, content="body"), log=_silent_log, is_canceled=_never_canceled, layout=store.layout
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "declare its experiment first" in result.failure.message
    assert not store.overlay.is_file(path)
