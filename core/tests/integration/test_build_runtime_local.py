"""Local end-to-end coverage for the author runtime build operation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    RuntimeDefinition,
)
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt
from repo2ree_core.domain.ree.transitions import commit_receipt
from repo2ree_core.operations.handlers.author.build_runtime import handle_build_runtime
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def test_build_script_runs_and_commits_the_produced_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    script = b"#!/bin/sh\nset -eu\nprintf 'local runtime' > runtime.tar\n"
    store.overlay.write_bytes(RESERVED_BUILD_SCRIPT, script)
    store.workspace.write_bytes(RESERVED_BUILD_SCRIPT, script)
    ree = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                build_runtime=BuildRuntimeDefinition(
                    build_runtime_script_digest=digest_bytes(script),
                    build_runtime_script_size=len(script),
                ),
                runtime=RuntimeDefinition(runtime_path=WorkspacePath("runtime.tar")),
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

    result = handle_build_runtime(
        run_id="build-local",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert (layout.workspace / "runtime.tar").read_bytes() == b"local runtime"
    receipt = store.read_ree().subject.receipts.build
    assert receipt is not None
    assert receipt.run_id == "build-local"
    assert receipt.produced_runtime_digest == digest_bytes(b"local runtime")
