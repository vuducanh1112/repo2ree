from __future__ import annotations

from pathlib import Path

import pytest
from ree_definitions import bare_ree

from repo2ree_core.operations.handlers.author import acquire_source
from repo2ree_core.operations.handlers.author.acquire_source import (
    _acquisition_from,
    _ObservedSource,
    _validate_observation,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import Ree, SourceDefinition
from repo2ree_ree.primitives import GitRevision

_PACKED = GitRevision("c" * 40)
_HISTORY_DIGEST = digest_bytes(b"history")


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_ree(ree or bare_ree())
    return layout, store


def _successful_materialization(*args: object, **kwargs: object) -> ActionResult:
    return ActionResult(status="succeeded", exit_code=0)


def test_download_request_becomes_the_source_definition() -> None:
    acquisition = _acquisition_from(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
            revision="main",
        )
    )

    assert acquisition.definition.origin_url == "https://example.test/repo.git"
    assert acquisition.definition.source_type == "git"
    assert acquisition.definition.requested_ref == "main"
    assert acquisition.definition.history == "full"


def test_a_git_download_may_carry_the_commit_alone() -> None:
    acquisition = _acquisition_from(
        AcquireSourceArgs(mode="download", origin_url="https://example.test/repo.git", source_type="git", history="tip")
    )

    assert acquisition.definition.history == "tip"


def test_only_a_git_source_has_a_history() -> None:
    with pytest.raises(ValueError, match="only a git source"):
        _acquisition_from(
            AcquireSourceArgs(
                mode="download", origin_url="https://example.test/s.tar.gz", source_type="tarball", history="full"
            )
        )
    with pytest.raises(ValueError, match="no history"):
        _acquisition_from(
            AcquireSourceArgs(mode="upload", upload_token="u", archive_name="s.zip", history="tip")  # noqa: S106
        )


def test_upload_format_is_preserved_in_the_source_definition() -> None:
    acquisition = _acquisition_from(
        AcquireSourceArgs(mode="upload", upload_token="upload-1", archive_name="source.zip")  # noqa: S106
    )

    assert acquisition.definition.origin_url is None
    assert acquisition.definition.source_type == "zip"
    assert acquisition.definition.requested_ref is None


def test_acquisition_rejects_a_different_resolved_immutable_revision() -> None:
    definition = SourceDefinition(
        origin_url="https://example.test/repo.git",
        source_type="git",
        requested_ref="a" * 40,
        history="full",
    )

    with pytest.raises(ValueError, match="requested immutable revision"):
        _validate_observation(
            definition,
            _ObservedSource(resolved_revision=GitRevision("b" * 40), swhid=None),
            log=lambda *args: None,
        )


def test_successful_acquisition_commits_definition_and_one_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    snapshot_digest = digest_bytes(b"snapshot")

    monkeypatch.setattr(acquire_source, "_perform", lambda *args, **kwargs: snapshot_digest)
    monkeypatch.setattr(
        acquire_source,
        "_observe_acquired_source",
        lambda *args, **kwargs: _ObservedSource(
            resolved_revision=_PACKED, swhid=None, history="full", history_digest=_HISTORY_DIGEST
        ),
    )
    monkeypatch.setattr(
        acquire_source,
        "materialize_workspace",
        _successful_materialization,
    )

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
            revision="main",
        ),
        run_id="source-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    committed = store.read_ree()
    assert result.status == "succeeded"
    assert committed.subject.definition.source is not None
    assert committed.subject.definition.source.requested_ref == "main"
    assert committed.subject.receipts.acquire_source is not None
    assert committed.subject.receipts.acquire_source.resolved_revision == _PACKED
    assert committed.subject.receipts.acquire_source.history == "full"
    assert committed.subject.receipts.acquire_source.history_digest == _HISTORY_DIGEST
    assert committed.subject.receipts.acquire_source.snapshot_digest == snapshot_digest


def test_failed_execution_commits_neither_definition_nor_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(
        acquire_source,
        "_perform",
        lambda *args, **kwargs: ActionResult.failed("execution", "fetch failed"),
    )

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
        ),
        run_id="source-failed",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    committed = store.read_ree()
    assert result.status == "failed"
    assert committed.subject.definition.source is None
    assert committed.subject.receipts.acquire_source is None


def test_identity_validation_failure_commits_no_source_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(acquire_source, "_perform", lambda *args, **kwargs: digest_bytes(b"snapshot"))
    monkeypatch.setattr(
        acquire_source,
        "_observe_acquired_source",
        lambda *args, **kwargs: _ObservedSource(resolved_revision=GitRevision("b" * 40), swhid=None),
    )

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
            revision="a" * 40,
        ),
        run_id="source-mismatch",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    committed = store.read_ree()
    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "validation"
    assert committed.subject.definition.source is None
    assert committed.subject.receipts.acquire_source is None


def test_materialization_failure_happens_after_source_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    snapshot_digest = digest_bytes(b"snapshot")
    monkeypatch.setattr(acquire_source, "_perform", lambda *args, **kwargs: snapshot_digest)
    monkeypatch.setattr(
        acquire_source,
        "_observe_acquired_source",
        lambda *args, **kwargs: _ObservedSource(
            resolved_revision=_PACKED, swhid=None, history="full", history_digest=_HISTORY_DIGEST
        ),
    )
    monkeypatch.setattr(
        acquire_source,
        "materialize_workspace",
        lambda *args, **kwargs: ActionResult.failed("execution", "materialization failed"),
    )

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
        ),
        run_id="source-materialize-failed",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    committed = store.read_ree()
    assert result.status == "failed"
    assert committed.subject.receipts.acquire_source is not None
    assert committed.subject.receipts.acquire_source.snapshot_digest == snapshot_digest


def test_dirty_source_slot_rejects_acquisition_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    store.upstream.write_text("partial.txt", "partial")
    performed = False

    def perform(*args: object, **kwargs: object) -> ActionResult:
        nonlocal performed
        performed = True
        return ActionResult.failed("execution", "should not run")

    monkeypatch.setattr(acquire_source, "_perform", perform)

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url="https://example.test/repo.git",
            source_type="git",
        ),
        run_id="source-dirty",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"
    assert performed is False
    assert layout.upstream.joinpath("partial.txt").read_text() == "partial"


def test_upload_acquisition_commits_archive_source_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    staged = layout.upload_staging_file("upload-1")
    staged.write_bytes(b"staged archive")
    snapshot_digest = digest_bytes(b"snapshot")
    monkeypatch.setattr(acquire_source, "_perform", lambda *args, **kwargs: snapshot_digest)
    monkeypatch.setattr(
        acquire_source,
        "_observe_acquired_source",
        lambda *args, **kwargs: _ObservedSource(resolved_revision=None, swhid=None),
    )
    monkeypatch.setattr(acquire_source, "materialize_workspace", _successful_materialization)

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(mode="upload", upload_token="upload-1", archive_name="source.zip"),  # noqa: S106
        run_id="source-upload",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    committed = store.read_ree()
    assert result.status == "succeeded"
    assert committed.subject.definition.source == SourceDefinition(source_type="zip")
    assert committed.subject.receipts.acquire_source is not None
    assert committed.subject.receipts.acquire_source.source_type == "zip"
    assert committed.subject.receipts.acquire_source.resolved_revision is None
