from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.digests import digest_output_paths
from repo2ree_core.domain.ree.transitions import commit_receipt, record_seal
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, RunnableRunOutputs
from repo2ree_core.operations.handlers.author import activation_test, run_experiment, runnable
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentDefinition, ExperimentEnvironmentDefinition, Ree, ReeDefinition, ReeSubject
from repo2ree_ree.model import TestActivationDefinition as ActivationDefinition
from repo2ree_ree.primitives import ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt, BuildExperimentEnvironmentReceipt, WorkspaceDrift
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SNAPSHOT = digest_bytes(b"snapshot")
_EXPERIMENT_ENVIRONMENT = b"experiment_environment"
_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT = b"#!/bin/sh\nexit 0\n"
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


def _build_receipt() -> BuildExperimentEnvironmentReceipt:
    return BuildExperimentEnvironmentReceipt(
        run_id=RunId("build-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_SNAPSHOT,
        build_experiment_environment_script_path=ReePath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        build_experiment_environment_script_digest=digest_bytes(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        workspace_drift=WorkspaceDrift(status="unknown"),
        artifact_path=WorkspacePath("runtime.tar"),
        produced_artifact_digest=digest_bytes(_EXPERIMENT_ENVIRONMENT),
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
    experiment_environment: bool = True,
    build: bool = True,
    activation: bool = True,
    experiments: bool = True,
) -> Ree:
    definition = ReeDefinition(
        experiment_environment=(
            ExperimentEnvironmentDefinition(
                build_experiment_environment_script_digest=digest_bytes(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
                build_experiment_environment_script_size=len(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
                artifact_path=WorkspacePath("runtime.tar"),
            )
            if experiment_environment
            else None
        ),
        test_activation=_activation_definition() if activation else None,
        experiments=(_experiment_definition(),) if experiments else (),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    if source:
        ree = commit_receipt(ree, _source_receipt())
    if experiment_environment and build:
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
    store.workspace.write_bytes("runtime.tar", _EXPERIMENT_ENVIRONMENT)
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
    assert receipt.experiment_environment_path == "runtime.tar"
    assert receipt.experiment_environment_digest == digest_bytes(_EXPERIMENT_ENVIRONMENT)
    assert receipt.run_script_digest == digest_bytes(_ACTIVATION_SCRIPT)
    assert receipt.verify_script_digest == digest_bytes(_ACTIVATION_VERIFY)
    assert receipt.run_exit_code == 0
    assert receipt.verify_exit_code == 0


def test_native_activation_has_no_experiment_environment_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(experiment_environment=False))
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome("succeeded"))

    result = activation_test.handle_activation_test(
        run_id="activation-native",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    receipt = store.read_ree().subject.receipts.test_activation
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.experiment_environment_path is None
    assert receipt.experiment_environment_digest is None


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
    assert receipt.experiment_environment_digest == digest_bytes(_EXPERIMENT_ENVIRONMENT)
    assert receipt.run_script_digest == digest_bytes(_EXPERIMENT_SCRIPT)
    assert receipt.verify_script_digest == digest_bytes(_EXPERIMENT_VERIFY)
    assert receipt.workbench_environment is not None
    assert receipt.workbench_environment.declared is None
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
        (_ree(build=False), "experiment environment has not been built"),
        (_ree(activation=False), "no activation test is defined"),
        (record_seal(_ree(), sealed_at=_NOW), "sealed REE"),
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
