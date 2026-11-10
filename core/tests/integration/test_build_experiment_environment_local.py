"""Local end-to-end coverage for the author experiment environment build operation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.ree.transitions import commit_receipt
from repo2ree_core.operations.handlers.author.build_experiment_environment import handle_build_experiment_environment
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentEnvironmentDefinition, Ree, ReeDefinition, ReeSubject, SourceDefinition
from repo2ree_ree.primitives import RunId, WorkspacePath, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def test_build_experiment_environment_script_runs_and_commits_the_produced_experiment_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    script = b"#!/bin/sh\nset -eu\nprintf 'local experiment environment' > runtime.tar\n"
    store.overlay.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, script)
    store.workspace.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, script)
    ree = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                # Declared alongside the receipt committed below: acquisition
                # writes both, and a receipt without its declaration is the
                # orphan case the audit reports as stale.
                source=SourceDefinition(origin_url="https://example.test/repo.git", source_type="git"),
                experiment_environment=ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=digest_bytes(script),
                    build_experiment_environment_script_size=len(script),
                    artifact_path=WorkspacePath("runtime.tar"),
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
            origin_url="https://example.test/repo.git",
            source_type="git",
            snapshot_digest=digest_bytes(b"snapshot"),
        ),
    )
    store.write_ree(ree)
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))

    result = handle_build_experiment_environment(
        run_id="build-local",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert (layout.workspace / "runtime.tar").read_bytes() == b"local experiment environment"
    receipt = store.read_ree().subject.receipts.experiment_environment
    assert receipt is not None
    assert receipt.run_id == "build-local"
    assert receipt.produced_artifact_digest == digest_bytes(b"local experiment environment")
