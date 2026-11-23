from __future__ import annotations

from pathlib import Path

import pytest
from recorded_ree import as_recorded
from ree_definitions import LAUNCH, SNAPSHOT_DIGEST, ree_definition

from repo2ree_core.bundle.seal import BundleProgress, BundleSealCanceledError, seal_ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, replace_definition
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentEnvironmentDefinition, Ree, ReeSubject, SourceDefinition
from repo2ree_ree.primitives import (
    Digest,
    ExperimentEnvironmentPath,
    OverlayPath,
    RunId,
    parse_utc_instant,
)
from repo2ree_ree.receipt import AcquireSourceReceipt, BuildExperimentEnvironmentReceipt
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

_REE_ID = "ree-1"
_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SCRIPT = b"#!/bin/sh\nexit 0\n"
_SCRIPT_DIGEST = digest_bytes(_SCRIPT)
_OTHER_DIGEST = digest_bytes(b"edited")
_SNAPSHOT_DIGEST = SNAPSHOT_DIGEST
_EXPERIMENT_ENVIRONMENT_DIGEST = digest_bytes(b"experiment_environment")
_SOURCE = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")


def _ree(*, build_experiment_environment_script_digest: Digest = _SCRIPT_DIGEST) -> Ree:
    ree = Ree(
        subject=ReeSubject(
            definition=ree_definition(
                name="demo",
                source=_SOURCE,
                experiment_environment=ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=build_experiment_environment_script_digest,
                    build_experiment_environment_script_size=len(_SCRIPT),
                    artifact_path=ExperimentEnvironmentPath("runtime.tar"),
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
        BuildExperimentEnvironmentReceipt(
            run_id=RunId("build-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            snapshot_digest=_SNAPSHOT_DIGEST,
            build_experiment_environment_script_path=OverlayPath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
            build_experiment_environment_script_digest=build_experiment_environment_script_digest,
            artifact_path=ExperimentEnvironmentPath("runtime.tar"),
            produced_artifact_digest=_EXPERIMENT_ENVIRONMENT_DIGEST,
            launch_script_digest=LAUNCH,
        ),
    )


def _store(tmp_path: Path, ree: Ree) -> ReeDirectory:
    store = ReeDirectory(ReeLayout.for_ree(tmp_path, _REE_ID))
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, _SCRIPT)
    store.write_ree(ree)
    return store


def test_a_consistent_ree_seals_and_carries_its_inventory(tmp_path: Path) -> None:
    store = _store(tmp_path, _ree())

    outputs = seal_ree(
        store.layout,
        source_included=False,
        experiment_environment_included=False,
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
                "experiment_environment": ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=_OTHER_DIGEST,
                    build_experiment_environment_script_size=1,
                    artifact_path=ExperimentEnvironmentPath("runtime.tar"),
                )
            }
        ),
    )
    store = _store(tmp_path, edited)

    with pytest.raises(
        ReePreconditionError, match="experiment_environment: build experiment environment script changed"
    ):
        seal_ree(
            store.layout,
            source_included=False,
            experiment_environment_included=False,
            results_included=False,
            sealed_at=_NOW,
        )

    assert load_ree(store.layout, store).seal is None


def test_missing_evidence_still_seals(tmp_path: Path) -> None:
    bare = Ree(subject=ReeSubject(definition=ree_definition(name="demo")))
    store = _store(tmp_path, bare)

    outputs = seal_ree(
        store.layout,
        source_included=False,
        experiment_environment_included=False,
        results_included=False,
        sealed_at=_NOW,
    )

    assert outputs.sealed_at == _NOW


def test_sealing_streams_experiment_environment_without_reading_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path, _ree())
    experiment_environment = store.layout.kept_environment("runtime.tar")
    experiment_environment.parent.mkdir(parents=True, exist_ok=True)
    experiment_environment.write_bytes(b"experiment environment payload")
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == experiment_environment:
            raise AssertionError("experiment environment must be streamed")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    progress: list[BundleProgress] = []

    outputs = seal_ree(
        store.layout,
        source_included=False,
        experiment_environment_included=True,
        results_included=False,
        sealed_at=_NOW,
        progress=progress.append,
    )

    assert outputs.input_bytes >= experiment_environment.stat().st_size
    assert [update.phase for update in progress][-2:] == ["manifest", "publishing"]
    assert progress[-1].bytes_processed == progress[-1].bytes_total


def test_canceling_a_streamed_seal_does_not_publish_partial_state(tmp_path: Path) -> None:
    store = _store(tmp_path, _ree())
    experiment_environment = store.layout.kept_environment("runtime.tar")
    experiment_environment.parent.mkdir(parents=True, exist_ok=True)
    experiment_environment.write_bytes(b"x" * (2 * 1024 * 1024))
    progress: list[BundleProgress] = []

    with pytest.raises(BundleSealCanceledError):
        seal_ree(
            store.layout,
            source_included=False,
            experiment_environment_included=True,
            results_included=False,
            sealed_at=_NOW,
            progress=progress.append,
            is_canceled=lambda: any(update.bytes_processed >= 1024 * 1024 for update in progress),
        )

    assert load_ree(store.layout, store).seal is None


def test_sealing_is_refused_while_a_receipt_outlives_its_declaration(tmp_path: Path) -> None:
    definition = _ree().subject.definition
    unplaced = definition.experiment_environment.model_copy(update={"artifact_path": None})
    orphaned = replace_definition(_ree(), definition.model_copy(update={"experiment_environment": unplaced}))
    store = _store(tmp_path, orphaned)

    with pytest.raises(
        ReePreconditionError, match="experiment_environment: experiment environment artifact path changed"
    ):
        seal_ree(
            store.layout,
            source_included=False,
            experiment_environment_included=False,
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
    seal_ree(
        store.layout,
        source_included=False,
        experiment_environment_included=False,
        results_included=False,
        sealed_at=_NOW,
    )
    as_recorded(store.layout)
    with (
        pytest.raises(HistoryCaptureError, match="no published successful seal"),
        materialized_ree_download(store.layout),
    ):
        pass
