"""Local end-to-end coverage for author-side SBOM generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
)
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt, BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_core.domain.ree.transitions import commit_receipt
from repo2ree_core.operations.handlers.author.generate_sbom import handle_generate_sbom
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def test_scanner_process_publishes_sbom_and_commits_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    script = b"#!/bin/sh\nexit 0\n"
    runtime = b"local runtime archive"
    (layout.workspace / "runtime.tar").write_bytes(runtime)

    definition = ReeDefinition(
        build_runtime=BuildRuntimeDefinition(
            build_runtime_script_digest=digest_bytes(script),
            build_runtime_script_size=len(script),
            runtime_path=WorkspacePath("runtime.tar"),
        ),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
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
    ree = commit_receipt(
        ree,
        BuildRuntimeReceipt(
            run_id=RunId("build-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            snapshot_digest=digest_bytes(b"snapshot"),
            build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
            build_runtime_script_digest=digest_bytes(script),
            workspace_drift=WorkspaceDrift(status="unknown"),
            runtime_path=WorkspacePath("runtime.tar"),
            produced_runtime_digest=digest_bytes(runtime),
        ),
    )
    store.write_ree(ree)

    fake_syft = tmp_path / "fake-syft"
    document = '{"bomFormat":"CycloneDX","metadata":{"tools":{"components":[{"name":"syft","version":"test-1"}]}}}'
    fake_syft.write_text(
        f"#!/bin/sh\nset -eu\noutput=${{5#cyclonedx-json=}}\nprintf '%s' '{document}' > \"$output\"\n",
        encoding="utf-8",
    )
    fake_syft.chmod(0o755)
    monkeypatch.setenv("REPO2REE_TOOL_SYFT", str(fake_syft))
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))

    result = handle_generate_sbom(
        run_id="sbom-local",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded", result.model_dump(mode="json")
    assert layout.sbom.is_file()
    receipt = store.read_ree().subject.receipts.sbom
    assert receipt is not None
    assert receipt.run_id == "sbom-local"
    assert receipt.runtime_digest == digest_bytes(runtime)
    assert receipt.sbom_digest == digest_bytes(layout.sbom.read_bytes())
    assert receipt.tool_version == "test-1"
