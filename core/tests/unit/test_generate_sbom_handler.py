from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.analysis.sbom.scan import ScanOutcome
from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import Digest, ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    RuntimeDefinition,
)
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    BuildRuntimeReceipt,
    ReceiptEnvelopeFields,
    WorkspaceDrift,
)
from repo2ree_core.domain.ree.transitions import commit_receipt, record_seal
from repo2ree_core.operations.handlers.author import generate_sbom
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.result import ActionResult

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SNAPSHOT = digest_bytes(b"snapshot")
_SCRIPT = b"#!/bin/sh\nprintf runtime > runtime.tar\n"
_RUNTIME = b"runtime archive"
_SBOM = b'{"bomFormat":"CycloneDX"}'


def _envelope(run_id: str) -> ReceiptEnvelopeFields:
    return ReceiptEnvelopeFields(
        run_id=RunId(run_id),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
    )


def _ree(
    *,
    with_build: bool = True,
    runtime_path: str = "runtime.tar",
    expected_runtime_digest: Digest | None = None,
) -> Ree:
    definition = ReeDefinition(
        build_runtime=BuildRuntimeDefinition(
            build_runtime_script_digest=digest_bytes(_SCRIPT),
            build_runtime_script_size=len(_SCRIPT),
        ),
        runtime=RuntimeDefinition(
            runtime_path=WorkspacePath(runtime_path),
            expected_runtime_digest=expected_runtime_digest,
        ),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    ree = commit_receipt(
        ree,
        AcquireSourceReceipt(
            **_envelope("source-1"),
            origin_url="https://example.test/repo.git",
            source_type="git",
            resolved_revision="abc123",
            snapshot_digest=_SNAPSHOT,
        ),
    )
    if not with_build:
        return ree
    return commit_receipt(
        ree,
        BuildRuntimeReceipt(
            **_envelope("build-1"),
            snapshot_digest=_SNAPSHOT,
            build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
            build_runtime_script_digest=digest_bytes(_SCRIPT),
            workspace_drift=WorkspaceDrift(status="unknown"),
            runtime_path=WorkspacePath(runtime_path),
            produced_runtime_digest=digest_bytes(_RUNTIME),
        ),
    )


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.workspace.write_bytes("runtime.tar", _RUNTIME)
    store.write_ree(ree or _ree())
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout, store


def _successful_scan(_runtime: Path, output: Path, **_kwargs: object) -> ScanOutcome:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_SBOM)
    return ScanOutcome(returncode=0, tool_version="1.2.3")


def _run() -> ActionResult:
    return generate_sbom.handle_generate_sbom(
        GenerateSbomArgs(produced_runtime_path="runtime.tar"),
        run_id="sbom-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )


def test_success_commits_inline_receipt_and_publishes_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(generate_sbom, "scan_runtime_archive", _successful_scan)

    result = _run()

    receipt = store.read_ree().subject.receipts.sbom
    assert result.status == "succeeded"
    assert layout.sbom.read_bytes() == _SBOM
    assert receipt is not None
    assert receipt.run_id == "sbom-1"
    assert receipt.runtime_path == "runtime.tar"
    assert receipt.runtime_digest == digest_bytes(_RUNTIME)
    assert receipt.sbom_path == "artifacts/sbom.json"
    assert receipt.sbom_digest == digest_bytes(_SBOM)
    assert receipt.sbom_format == "cyclonedx-json"
    assert receipt.tool_version == "1.2.3"


@pytest.mark.parametrize(
    ("outcome", "write_output", "message"),
    [
        (ScanOutcome(returncode=7), True, "syft failed"),
        (ScanOutcome(returncode=0, tool_version="1.2.3"), False, "without producing"),
        (ScanOutcome(returncode=0), True, "did not report its tool version"),
    ],
)
def test_invalid_scan_result_preserves_existing_document_and_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: ScanOutcome,
    write_output: bool,
    message: str,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    layout.sbom.parent.mkdir(parents=True, exist_ok=True)
    layout.sbom.write_bytes(b"old sbom")

    def scan(_runtime: Path, output: Path, **_kwargs: object) -> ScanOutcome:
        if write_output:
            output.write_bytes(b"partial")
        return outcome

    monkeypatch.setattr(generate_sbom, "scan_runtime_archive", scan)

    result = _run()

    assert result.status == "failed"
    assert result.failure is not None
    assert message in result.failure.message
    assert layout.sbom.read_bytes() == b"old sbom"
    assert store.read_ree().subject.receipts.sbom is None
    assert not list(layout.artifacts.glob(".sbom.json.*.tmp"))


def test_canceled_scan_preserves_existing_document_and_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    layout.sbom.parent.mkdir(parents=True, exist_ok=True)
    layout.sbom.write_bytes(b"old sbom")

    def scan(_runtime: Path, output: Path, **_kwargs: object) -> ScanOutcome:
        output.write_bytes(b"partial")
        return ScanOutcome(returncode=-15, canceled=True)

    monkeypatch.setattr(generate_sbom, "scan_runtime_archive", scan)

    result = _run()

    assert result.status == "canceled"
    assert layout.sbom.read_bytes() == b"old sbom"
    assert store.read_ree().subject.receipts.sbom is None
    assert not list(layout.artifacts.glob(".sbom.json.*.tmp"))


@pytest.mark.parametrize(
    ("ree", "requested_path", "runtime_bytes", "message", "category"),
    [
        (_ree(with_build=False), "runtime.tar", _RUNTIME, "runtime has not been built", "precondition"),
        (_ree(), "other.tar", _RUNTIME, "does not match the REE definition", "validation"),
        (_ree(runtime_path="runtime.img"), "runtime.img", _RUNTIME, "tarballs only", "validation"),
        (_ree(), "runtime.tar", b"changed", "does not match the selected build", "precondition"),
        (
            _ree(expected_runtime_digest=digest_bytes(b"expected")),
            "runtime.tar",
            _RUNTIME,
            "does not match the expected digest",
            "precondition",
        ),
        (record_seal(_ree(), sealed_at=_NOW), "runtime.tar", _RUNTIME, "sealed REE", "precondition"),
    ],
)
def test_preconditions_reject_invalid_runtime_evidence_before_scanning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree,
    requested_path: str,
    runtime_bytes: bytes,
    message: str,
    category: str,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch, ree)
    (layout.workspace / "runtime.tar").write_bytes(runtime_bytes)
    scanned = False

    def scan(*args: object, **kwargs: object) -> ScanOutcome:
        nonlocal scanned
        scanned = True
        return ScanOutcome(returncode=0, tool_version="1.2.3")

    monkeypatch.setattr(generate_sbom, "scan_runtime_archive", scan)

    result = generate_sbom.handle_generate_sbom(
        GenerateSbomArgs(produced_runtime_path=requested_path),
        run_id="sbom-rejected",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == category
    assert message in result.failure.message
    assert scanned is False
    assert store.read_ree().subject.receipts.sbom is None


def test_revision_conflict_does_not_select_the_new_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(generate_sbom, "scan_runtime_archive", _successful_scan)

    def conflict(*args: object, **kwargs: object) -> None:
        raise ReeRevisionConflictError("REE changed while the scan ran")

    monkeypatch.setattr(generate_sbom, "save_ree", conflict)

    result = _run()

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    assert result.failure.retryable is True
    assert store.read_ree().subject.receipts.sbom is None
    assert layout.sbom.read_bytes() == _SBOM
