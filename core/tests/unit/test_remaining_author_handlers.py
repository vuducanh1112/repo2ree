from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.hbom import HBOM, CPUDefinition
from repo2ree_core.domain.primitives import ArtifactPath, ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_core.domain.ree.model import (
    TestActivationDefinition as ActivationDefinition,
)
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    BuildRuntimeReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    ReceiptEnvelopeFields,
    WorkspaceDrift,
)
from repo2ree_core.domain.ree.transitions import commit_receipt, revision_of
from repo2ree_core.operations.handlers.author import cross_check_sbom, generate_hbom
from repo2ree_core.operations.handlers.author.delete_file import handle_delete_file
from repo2ree_core.operations.handlers.author.patch_ree_definition import handle_patch_ree_definition
from repo2ree_core.operations.handlers.author.write_file import handle_write_file
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
)
from repo2ree_protocol.command import DeleteFileArgs, PatchReeDefinitionArgs, WriteFileArgs

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_BUILD = b"#!/bin/sh\nexit 0\n"
_ACTIVATION = b"#!/bin/sh\nexit 0\n"
_RUNTIME = b"runtime"
_SNAPSHOT = digest_bytes(b"snapshot")
_REPORT = {
    "dependency_level": 3,
    "environment_level": 1,
    "machine_level": 0,
    "dependency_summary": {"manifests": 1, "total": 1, "locked": 1},
    "dependencies": [
        {
            "ecosystem": "pypi",
            "name": "requests",
            "declared_constraint": "==2.31.0",
            "declared_in": "requirements.txt",
            "locked_version": "2.31.0",
            "status": "locked",
        }
    ],
    "threats": [],
}
_SBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "components": [{"name": "requests", "purl": "pkg:pypi/requests@2.31.0"}],
}


def _envelope(run_id: str) -> ReceiptEnvelopeFields:
    return ReceiptEnvelopeFields(
        run_id=RunId(run_id),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
    )


def _ree() -> Ree:
    return Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                name="demo",
                build_runtime=BuildRuntimeDefinition(
                    build_runtime_script_digest=digest_bytes(_BUILD),
                    build_runtime_script_size=len(_BUILD),
                ),
                test_activation=ActivationDefinition(
                    run_script_digest=digest_bytes(_ACTIVATION),
                    run_script_size=len(_ACTIVATION),
                ),
            )
        )
    )


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_SCRIPT, _BUILD)
    store.workspace.write_bytes(RESERVED_BUILD_SCRIPT, _BUILD)
    store.overlay.write_bytes(RESERVED_ACTIVATION_SCRIPT, _ACTIVATION)
    store.workspace.write_bytes(RESERVED_ACTIVATION_SCRIPT, _ACTIVATION)
    store.write_ree(ree or _ree())
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout, store


def test_definition_patch_hydrates_experiment_script_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    script_path = experiment_run_script_path("analysis")
    script = b"#!/bin/sh\nprintf result\n"
    store.overlay.write_bytes(script_path, script)
    store.workspace.write_bytes(script_path, script)

    result = handle_patch_ree_definition(
        PatchReeDefinitionArgs(
            patch={
                "build_runtime": {"runtime_path": "runtime.tar"},
                "experiments": [{"name": "analysis", "output_paths": ["result.txt"]}],
            },
            expected_version=str(revision_of(store.read_ree())),
        ),
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    definition = store.read_ree().subject.definition
    assert result.status == "succeeded"
    assert definition.build_runtime is not None
    assert definition.build_runtime.runtime_path == WorkspacePath("runtime.tar")
    experiment = definition.experiments[0]
    assert experiment.run_script_path == script_path
    assert experiment.run_script_digest == digest_bytes(script)
    assert experiment.run_script_size == len(script)
    assert experiment.output_paths == (WorkspacePath("result.txt"),)
    assert result.outputs["revision"] != str(revision_of(_ree()))
    assert layout.manifest.is_file()


def test_recipe_file_write_rehydrates_definition_and_delete_removes_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    changed = "#!/bin/sh\nprintf changed\n"

    write_result = handle_write_file(
        WriteFileArgs(path=RESERVED_BUILD_SCRIPT, content=changed),
        log=lambda *args: None,
        is_canceled=lambda: False,
    )
    updated = store.read_ree().subject.definition.build_runtime

    assert write_result.status == "succeeded"
    assert updated is not None
    assert updated.build_runtime_script_digest == digest_bytes(changed.encode())
    assert updated.build_runtime_script_size == len(changed.encode())

    delete_result = handle_delete_file(
        DeleteFileArgs(path=RESERVED_BUILD_SCRIPT),
        log=lambda *args: None,
        is_canceled=lambda: False,
    )
    assert delete_result.status == "succeeded"
    assert store.read_ree().subject.definition.build_runtime is None


def test_hardware_observation_commits_receipt_without_rewriting_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    observed = HBOM(cpus={"Xeon": CPUDefinition(quantity=2)})
    monkeypatch.setattr(generate_hbom, "generate_hbom", lambda: observed)

    result = generate_hbom.handle_generate_hbom(
        run_id="hardware-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    persisted = store.read_ree()
    assert result.status == "succeeded"
    assert persisted.subject.definition.hardware is None
    assert persisted.subject.receipts.hardware_observation is not None
    assert persisted.subject.receipts.hardware_observation.observation == observed


def test_cross_check_commits_inline_receipt_and_preserves_evaluation_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ree = _cross_check_ree()
    layout, store = _workbench(tmp_path, monkeypatch, ree)
    report_bytes = json.dumps(_REPORT).encode()
    sbom_bytes = json.dumps(_SBOM).encode()
    layout.reproducibility_report.write_bytes(report_bytes)
    layout.sbom.write_bytes(sbom_bytes)
    ree = _cross_check_ree(report_digest=digest_bytes(report_bytes), sbom_digest=digest_bytes(sbom_bytes))
    store.write_ree(ree)

    result = cross_check_sbom.handle_cross_check_sbom(
        run_id="cross-check-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    receipt = store.read_ree().subject.receipts.sbom_cross_check
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.run_id == "cross-check-1"
    assert receipt.observed_matched == 1
    # Both sides of the reconciliation are named, so either moving is detectable.
    assert receipt.sbom_digest == digest_bytes(sbom_bytes)
    assert receipt.report_digest == digest_bytes(report_bytes)
    assert layout.reproducibility_report.read_bytes() == report_bytes


def _cross_check_ree(
    *,
    report_digest=None,
    sbom_digest=None,
) -> Ree:
    report_digest = report_digest or digest_bytes(json.dumps(_REPORT).encode())
    sbom_digest = sbom_digest or digest_bytes(json.dumps(_SBOM).encode())
    definition = ReeDefinition(
        name="demo",
        source=SourceDefinition(origin_url="https://example.test/repo.git", source_type="git"),
        build_runtime=BuildRuntimeDefinition(
            build_runtime_script_digest=digest_bytes(_BUILD),
            build_runtime_script_size=len(_BUILD),
            runtime_path=WorkspacePath("runtime.tar"),
        ),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    ree = commit_receipt(
        ree,
        AcquireSourceReceipt(
            **_envelope("source-1"),
            origin_url="https://example.test/repo.git",
            source_type="git",
            snapshot_digest=_SNAPSHOT,
        ),
    )
    ree = commit_receipt(
        ree,
        BuildRuntimeReceipt(
            **_envelope("build-1"),
            snapshot_digest=_SNAPSHOT,
            build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
            build_runtime_script_digest=digest_bytes(_BUILD),
            workspace_drift=WorkspaceDrift(status="unknown"),
            runtime_path=WorkspacePath("runtime.tar"),
            produced_runtime_digest=digest_bytes(_RUNTIME),
        ),
    )
    ree = commit_receipt(
        ree,
        EvaluateReproducibilityReceipt(
            **_envelope("evaluation-1"),
            snapshot_digest=_SNAPSHOT,
            overlay_digest=digest_bytes(b"overlay"),
            strict=False,
            dependency_level=3,
            environment_level=1,
            machine_level=0,
            dependency_count=1,
            manifest_count=1,
            report_path=ArtifactPath("artifacts/reproducibility-report.json"),
            report_digest=report_digest,
            analyzer_version="1",
        ),
    )
    return commit_receipt(
        ree,
        GenerateSbomReceipt(
            **_envelope("sbom-1"),
            runtime_path=WorkspacePath("runtime.tar"),
            runtime_digest=digest_bytes(_RUNTIME),
            sbom_path=ArtifactPath("artifacts/sbom.json"),
            sbom_digest=sbom_digest,
            sbom_format="cyclonedx-json",
            tool_version="1",
        ),
    )
