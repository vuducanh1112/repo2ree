from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.digests import Digest, digest_bytes, digest_output_paths
from repo2ree_core.domain.primitives import ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    ExperimentDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    RuntimeDefinition,
)
from repo2ree_core.domain.ree.model import (
    TestActivationDefinition as ActivationDefinition,
)
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt, BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_core.domain.ree.transitions import commit_receipt, record_seal
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, RunnableRunOutputs
from repo2ree_core.operations.handlers.author import activation_test, run_experiment, runnable
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)
from repo2ree_protocol.command import RunExperimentArgs

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SNAPSHOT = digest_bytes(b"snapshot")
_RUNTIME = b"runtime"
_BUILD_SCRIPT = b"#!/bin/sh\nexit 0\n"
_ACTIVATION_SCRIPT = b"#!/bin/sh\nexit 0\n"
_ACTIVATION_VERIFY = b"#!/bin/sh\nexit 0\n"
_EXPERIMENT_SCRIPT = b"#!/bin/sh\nprintf result > outputs/result.txt\n"
_EXPERIMENT_VERIFY = b"#!/bin/sh\ntest -f outputs/result.txt\n"
_EXPERIMENT_NAME = "demo"


def _source_receipt() -> AcquireSourceReceipt:
    return AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url="https://example.test/repo.git",
        source_type="git",
        snapshot_digest=_SNAPSHOT,
    )


def _build_receipt() -> BuildRuntimeReceipt:
    return BuildRuntimeReceipt(
        run_id=RunId("build-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_SNAPSHOT,
        build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
        build_runtime_script_digest=digest_bytes(_BUILD_SCRIPT),
        workspace_drift=WorkspaceDrift(status="unknown"),
        runtime_path=WorkspacePath("runtime.tar"),
        produced_runtime_digest=digest_bytes(_RUNTIME),
    )


def _activation_definition(*, verify: bool = True) -> ActivationDefinition:
    return ActivationDefinition(
        run_script_digest=digest_bytes(_ACTIVATION_SCRIPT),
        run_script_size=len(_ACTIVATION_SCRIPT),
        verify_script_path=ReePath(RESERVED_ACTIVATION_VERIFY_SCRIPT) if verify else None,
        verify_script_digest=digest_bytes(_ACTIVATION_VERIFY) if verify else None,
        verify_script_size=len(_ACTIVATION_VERIFY) if verify else None,
    )


def _experiment_definition(*, verify: bool = True) -> ExperimentDefinition:
    return ExperimentDefinition(
        name=_EXPERIMENT_NAME,
        run_script_path=ReePath(experiment_run_script_path(_EXPERIMENT_NAME)),
        run_script_digest=digest_bytes(_EXPERIMENT_SCRIPT),
        run_script_size=len(_EXPERIMENT_SCRIPT),
        verify_script_path=(ReePath(experiment_verify_script_path(_EXPERIMENT_NAME)) if verify else None),
        verify_script_digest=digest_bytes(_EXPERIMENT_VERIFY) if verify else None,
        verify_script_size=len(_EXPERIMENT_VERIFY) if verify else None,
        output_paths=(WorkspacePath("outputs/result.txt"),),
    )


def _ree(
    *,
    source: bool = True,
    runtime: bool = True,
    build: bool = True,
    activation: bool = True,
    experiments: bool = True,
    expected_runtime_digest: Digest | None = None,
) -> Ree:
    definition = ReeDefinition(
        build_runtime=(
            BuildRuntimeDefinition(
                build_runtime_script_digest=digest_bytes(_BUILD_SCRIPT),
                build_runtime_script_size=len(_BUILD_SCRIPT),
            )
            if runtime
            else None
        ),
        runtime=(
            RuntimeDefinition(
                runtime_path=WorkspacePath("runtime.tar"),
                expected_runtime_digest=expected_runtime_digest,
            )
            if runtime
            else None
        ),
        test_activation=_activation_definition() if activation else None,
        experiments=(_experiment_definition(),) if experiments else (),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    if source:
        ree = commit_receipt(ree, _source_receipt())
    if runtime and build:
        ree = commit_receipt(ree, _build_receipt())
    return ree


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.workspace.write_bytes(RESERVED_ACTIVATION_SCRIPT, _ACTIVATION_SCRIPT)
    store.workspace.write_bytes(RESERVED_ACTIVATION_VERIFY_SCRIPT, _ACTIVATION_VERIFY)
    store.workspace.write_bytes(experiment_run_script_path(_EXPERIMENT_NAME), _EXPERIMENT_SCRIPT)
    store.workspace.write_bytes(experiment_verify_script_path(_EXPERIMENT_NAME), _EXPERIMENT_VERIFY)
    store.workspace.write_bytes("runtime.tar", _RUNTIME)
    store.write_ree(ree or _ree())
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout, store


def _outcome(status: str) -> ExperimentRunOutcome:
    if status == "succeeded":
        outputs = RunnableRunOutputs(
            subject_name="subject",
            exit_code=0,
            verify_exit_code=0,
            verdict="pass",
        )
    elif status == "canceled":
        outputs = RunnableRunOutputs(subject_name="subject", exit_code=-15)
    else:
        outputs = RunnableRunOutputs(subject_name="subject", exit_code=7, verdict="fail")
    return ExperimentRunOutcome(status=status, run_outputs=outputs)  # type: ignore[arg-type]


def test_activation_success_commits_exact_input_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome("succeeded"))

    result = activation_test.handle_activation_test(
        run_id="activation-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    receipt = store.read_ree().subject.receipts.test_activation
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.run_id == "activation-1"
    assert receipt.snapshot_digest == _SNAPSHOT
    assert receipt.runtime_path == "runtime.tar"
    assert receipt.runtime_digest == digest_bytes(_RUNTIME)
    assert receipt.run_script_digest == digest_bytes(_ACTIVATION_SCRIPT)
    assert receipt.verify_script_digest == digest_bytes(_ACTIVATION_VERIFY)
    assert receipt.run_exit_code == 0
    assert receipt.verify_exit_code == 0


def test_native_activation_has_no_runtime_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(runtime=False))
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome("succeeded"))

    result = activation_test.handle_activation_test(
        run_id="activation-native",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    receipt = store.read_ree().subject.receipts.test_activation
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.runtime_path is None
    assert receipt.runtime_digest is None


def test_experiment_success_captures_outputs_and_commits_named_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    output = layout.workspace / "outputs/result.txt"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"result")
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome("succeeded"))

    result = run_experiment.handle_run_experiment(
        RunExperimentArgs(experiment_name=_EXPERIMENT_NAME),
        run_id="experiment-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    receipt = store.read_ree().subject.receipts.experiments.get(_EXPERIMENT_NAME)
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.run_id == "experiment-1"
    assert receipt.runtime_digest == digest_bytes(_RUNTIME)
    assert receipt.run_script_digest == digest_bytes(_EXPERIMENT_SCRIPT)
    assert receipt.verify_script_digest == digest_bytes(_EXPERIMENT_VERIFY)
    assert receipt.produced_output_digest == digest_output_paths(
        layout.workspace,
        ["outputs/result.txt"],
    )
    assert (layout.results_dir(_EXPERIMENT_NAME) / "outputs/result.txt").read_bytes() == b"result"


@pytest.mark.parametrize("status", ["failed", "canceled"])
def test_unsuccessful_attempt_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome(status))

    result = activation_test.handle_activation_test(
        run_id="activation-unsuccessful",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == status
    assert store.read_ree().subject.receipts.test_activation is None


@pytest.mark.parametrize(
    ("ree", "message"),
    [
        (_ree(source=False), "source has not been acquired"),
        (_ree(build=False), "runtime has not been built"),
        (_ree(activation=False), "no activation test is defined"),
        (record_seal(_ree(), sealed_at=_NOW), "sealed REE"),
        (
            _ree(expected_runtime_digest=digest_bytes(b"other")),
            "does not match the expected digest",
        ),
    ],
)
def test_activation_preconditions_reject_invalid_evidence_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree,
    message: str,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, ree)
    executed = False

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        nonlocal executed
        executed = True
        return _outcome("succeeded")

    monkeypatch.setattr(runnable, "run_runnable", execute)

    result = activation_test.handle_activation_test(
        run_id="activation-rejected",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"
    assert message in result.failure.message
    assert executed is False
    assert store.read_ree().subject.receipts.test_activation is None


def test_changed_script_is_rejected_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    store.workspace.write_bytes(RESERVED_ACTIVATION_SCRIPT, b"changed")
    executed = False

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        nonlocal executed
        executed = True
        return _outcome("succeeded")

    monkeypatch.setattr(runnable, "run_runnable", execute)

    result = activation_test.handle_activation_test(
        run_id="activation-stale-script",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "run script does not match its definition" in result.failure.message
    assert executed is False


def test_unknown_experiment_is_rejected_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    executed = False

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        nonlocal executed
        executed = True
        return _outcome("succeeded")

    monkeypatch.setattr(runnable, "run_runnable", execute)

    result = run_experiment.handle_run_experiment(
        RunExperimentArgs(experiment_name="missing"),
        run_id="experiment-missing",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "experiment 'missing' is not defined" in result.failure.message
    assert executed is False
    assert store.read_ree().subject.receipts.experiments == {}


def test_revision_conflict_does_not_select_the_new_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome("succeeded"))

    def conflict(*args: object, **kwargs: object) -> None:
        raise ReeRevisionConflictError("REE changed while activation ran")

    monkeypatch.setattr(runnable, "save_ree", conflict)

    result = activation_test.handle_activation_test(
        run_id="activation-conflict",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    assert result.failure.retryable is True
    assert store.read_ree().subject.receipts.test_activation is None
