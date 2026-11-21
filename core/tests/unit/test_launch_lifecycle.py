"""An author's step runs through the REE's launch, its receipt says so, and a changed launch leaves it stale."""

from __future__ import annotations

from pathlib import Path

import pytest
from ree_definitions import SNAPSHOT_DIGEST, ree_definition, write_snapshot

from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.transitions import commit_receipt, replace_definition
from repo2ree_core.operations.handlers.author import build_experiment_environment
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import (
    ExperimentEnvironmentDefinition,
    LaunchDefinition,
    Ree,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_ree.primitives import ExperimentEnvironmentPath, RunId, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, RESERVED_LAUNCH_SCRIPT

_NOW = parse_utc_instant("2026-11-13T00:00:00Z")
_BUILD = b"#!/bin/sh\nprintf '%s' \"${SLURM_JOB_ID:-direct}\" > runtime.tar\n"
_LAUNCH = b'#!/bin/sh\nSLURM_JOB_ID=4711\nexport SLURM_JOB_ID\nexec "$@"\n'


def _launch(body: bytes = _LAUNCH) -> LaunchDefinition:
    return LaunchDefinition(launch_script_digest=digest_bytes(body), launch_script_size=len(body))


def _ree(launch: LaunchDefinition) -> Ree:
    definition = ree_definition(
        source=SourceDefinition(origin_url="https://example.test/repo.git", source_type="git"),
        experiment_environment=ExperimentEnvironmentDefinition(
            build_experiment_environment_script_digest=digest_bytes(_BUILD),
            build_experiment_environment_script_size=len(_BUILD),
            artifact_path=ExperimentEnvironmentPath("runtime.tar"),
        ),
        launch=launch,
    )
    source = AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url="https://example.test/repo.git",
        source_type="git",
        snapshot_digest=SNAPSHOT_DIGEST,
    )
    return commit_receipt(Ree(subject=ReeSubject(definition=definition)), source)


def _workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch: LaunchDefinition) -> ReeDirectory:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, _BUILD)
    store.overlay.write_bytes(RESERVED_LAUNCH_SCRIPT, _LAUNCH)
    write_snapshot(layout)
    store.write_ree(_ree(launch))
    return store


def _build(layout: ReeLayout) -> str:
    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-1", log=lambda *_args: None, is_canceled=lambda: False, layout=layout
    )
    return result.status


def test_a_build_runs_through_the_declared_launch_and_its_receipt_says_where(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _workbench(tmp_path, monkeypatch, _launch())
    assert _build(store.layout) == "succeeded"
    assert store.layout.kept_environment("runtime.tar").read_bytes() == b"4711"
    receipt = store.read_ree().subject.receipts.build_experiment_environment
    assert receipt is not None
    assert receipt.launch_script_digest == digest_bytes(_LAUNCH)
    assert receipt.launched is not None
    assert receipt.launched.slurm_job_id == "4711"


def test_a_launch_script_edited_since_it_was_declared_stops_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _workbench(tmp_path, monkeypatch, _launch())
    store.overlay.write_bytes(RESERVED_LAUNCH_SCRIPT, _LAUNCH + b"# edited\n")
    assert _build(store.layout) == "failed"
    assert store.read_ree().subject.receipts.build_experiment_environment is None


def test_a_step_that_ran_under_another_launch_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _workbench(tmp_path, monkeypatch, _launch())
    after = _launch(_LAUNCH + b"# another launcher\n")
    assert _build(store.layout) == "succeeded"
    ree = store.read_ree()
    assert audit(ree).build_experiment_environment.evidence == "current"
    relaunched = replace_definition(ree, ree.subject.definition.model_copy(update={"launch": after}))
    step = audit(relaunched).build_experiment_environment
    assert step.evidence != "current"
    assert "launch script changed" in step.reasons
