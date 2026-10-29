"""Sealing is refused when the REE's own receipts contradict what it holds."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.bundle.seal import BundleProgress, BundleSealCanceledError, seal_ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, replace_definition
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import BuildRuntimeDefinition, Ree, ReeDefinition, ReeSubject, SourceDefinition
from repo2ree_ree.primitives import Digest, ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt, BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_ree.reserved_paths import RESERVED_BUILD_SCRIPT

_REE_ID = "ree-1"
_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SCRIPT = b"#!/bin/sh\nexit 0\n"
_SCRIPT_DIGEST = digest_bytes(_SCRIPT)
_OTHER_DIGEST = digest_bytes(b"edited")
_SNAPSHOT_DIGEST = digest_bytes(b"snapshot")
_RUNTIME_DIGEST = digest_bytes(b"runtime")
_SOURCE = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")


def _ree(*, build_script_digest: Digest = _SCRIPT_DIGEST) -> Ree:
    ree = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                name="demo",
                source=_SOURCE,
                build_runtime=BuildRuntimeDefinition(
                    build_runtime_script_digest=build_script_digest,
                    build_runtime_script_size=len(_SCRIPT),
                    runtime_path=WorkspacePath("runtime.tar"),
                ),
            )
        )
    )
    ree = commit_receipt(
        ree,
        AcquireSourceReceipt(
            run_id=RunId("source-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            origin_url=_SOURCE.origin_url,
            source_type=_SOURCE.source_type,
            snapshot_digest=_SNAPSHOT_DIGEST,
        ),
    )
    return commit_receipt(
        ree,
        BuildRuntimeReceipt(
            run_id=RunId("build-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            snapshot_digest=_SNAPSHOT_DIGEST,
            build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
            build_runtime_script_digest=build_script_digest,
            workspace_drift=WorkspaceDrift(status="clean"),
            runtime_path=WorkspacePath("runtime.tar"),
            produced_runtime_digest=_RUNTIME_DIGEST,
        ),
    )


def _store(tmp_path: Path, ree: Ree) -> ReeDirectory:
    store = ReeDirectory(ReeLayout.for_ree(tmp_path, _REE_ID))
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_SCRIPT, _SCRIPT)
    store.write_ree(ree)
    return store


def test_a_consistent_ree_seals_and_carries_its_inventory(tmp_path: Path) -> None:
    store = _store(tmp_path, _ree())

    outputs = seal_ree(
        store.layout,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=_NOW,
    )

    sealed = load_ree(store.layout, store)
    assert sealed.seal is not None
    assert sealed.seal.ree_digest == outputs.ree_digest
    from repo2ree_core.bundle.repository_export import verify_inventory

    verify_inventory(store.layout.root)


def test_sealing_is_refused_while_a_receipt_is_stale(tmp_path: Path) -> None:
    ree = _ree()
    edited = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={
                "build_runtime": BuildRuntimeDefinition(
                    build_runtime_script_digest=_OTHER_DIGEST,
                    build_runtime_script_size=1,
                    runtime_path=WorkspacePath("runtime.tar"),
                )
            }
        ),
    )
    store = _store(tmp_path, edited)

    with pytest.raises(ReePreconditionError, match="runtime: runtime build script changed"):
        seal_ree(
            store.layout,
            source_included=False,
            runtime_included=False,
            results_included=False,
            sealed_at=_NOW,
        )

    assert load_ree(store.layout, store).seal is None


def test_missing_evidence_still_seals(tmp_path: Path) -> None:
    """Incomplete is not self-contradictory: an REE may be sealed with gaps."""
    bare = Ree(subject=ReeSubject(definition=ReeDefinition(name="demo")))
    store = _store(tmp_path, bare)

    outputs = seal_ree(
        store.layout,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=_NOW,
    )

    assert outputs.sealed_at == _NOW


def test_sealing_streams_runtime_without_reading_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path, _ree())
    runtime = store.layout.workspace / "runtime.tar"
    runtime.write_bytes(b"runtime payload")
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == runtime:
            raise AssertionError("runtime must be streamed")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    progress: list[BundleProgress] = []

    outputs = seal_ree(
        store.layout,
        source_included=False,
        runtime_included=True,
        results_included=False,
        sealed_at=_NOW,
        progress=progress.append,
    )

    assert outputs.input_bytes >= runtime.stat().st_size
    assert [update.phase for update in progress][-2:] == ["manifest", "publishing"]
    assert progress[-1].bytes_processed == progress[-1].bytes_total


def test_canceling_a_streamed_seal_does_not_publish_partial_state(tmp_path: Path) -> None:
    store = _store(tmp_path, _ree())
    runtime = store.layout.workspace / "runtime.tar"
    runtime.write_bytes(b"x" * (2 * 1024 * 1024))
    progress: list[BundleProgress] = []

    with pytest.raises(BundleSealCanceledError):
        seal_ree(
            store.layout,
            source_included=False,
            runtime_included=True,
            results_included=False,
            sealed_at=_NOW,
            progress=progress.append,
            is_canceled=lambda: any(update.bytes_processed >= 1024 * 1024 for update in progress),
        )

    assert load_ree(store.layout, store).seal is None


def test_sealing_is_refused_while_a_receipt_outlives_its_declaration(tmp_path: Path) -> None:
    """Dropping the declaration must not launder the receipt that attested it.

    Deleting ``build.sh`` clears ``build_runtime`` but leaves the build receipt
    on the aggregate. Sealing there would publish a runtime attestation for a
    recipe the bundle does not carry — evidence no reader could check.
    """
    orphaned = replace_definition(_ree(), _ree().subject.definition.model_copy(update={"build_runtime": None}))
    store = _store(tmp_path, orphaned)

    with pytest.raises(ReePreconditionError, match="runtime: runtime build definition was removed"):
        seal_ree(
            store.layout,
            source_included=False,
            runtime_included=False,
            results_included=False,
            sealed_at=_NOW,
        )

    assert load_ree(store.layout, store).seal is None


def test_download_refuses_seal_without_published_operation(tmp_path):
    from repo2ree_core.bundle.download import materialized_ree_download
    from repo2ree_core.persistence.history import HistoryCaptureError, open_history

    store = _store(tmp_path, _ree())
    with open_history(store.layout) as history:
        history.capture_initial(existing=True)
    seal_ree(store.layout, source_included=False, runtime_included=False, results_included=False, sealed_at=_NOW)
    with (
        pytest.raises(HistoryCaptureError, match="no published successful seal"),
        materialized_ree_download(store.layout),
    ):
        pass
