from __future__ import annotations

from pathlib import Path

import pytest
from ree_definitions import LAUNCH, SNAPSHOT_DIGEST, ree_definition, with_fixed_scripts, write_snapshot

from repo2ree_core.digests import digest_output_paths
from repo2ree_core.domain.ree.transitions import commit_receipt, record_seal
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, RunnableRunOutputs
from repo2ree_core.operations.handlers.author import activate_experiment_environment, run_experiment, runnable
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError
from repo2ree_protocol.command import ActivateExperimentEnvironmentArgs, RunExperimentArgs
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    ExperimentDefinition,
    ExperimentEnvironmentDefinition,
    Ree,
    ReeSubject,
)
from repo2ree_ree.primitives import (
    ExperimentEnvironmentPath,
    OverlayPath,
    RunId,
    WorkspacePath,
    parse_utc_instant,
)
from repo2ree_ree.receipt import (
    AcquireSourceReceipt,
    ActivateExperimentEnvironmentReceipt,
    BuildExperimentEnvironmentReceipt,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SNAPSHOT = SNAPSHOT_DIGEST
_EXPERIMENT_ENVIRONMENT = b"experiment_environment"
_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT = b"#!/bin/sh\nexit 0\n"
_ACTIVATE_SCRIPT = b'#!/bin/sh\nexec "$@"\n'
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
        build_experiment_environment_script_path=OverlayPath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        build_experiment_environment_script_digest=digest_bytes(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        artifact_path=ExperimentEnvironmentPath("runtime.tar"),
        produced_artifact_digest=digest_bytes(_EXPERIMENT_ENVIRONMENT),
        launch_script_digest=LAUNCH,
    )


def _activation_receipt(
    *, experiment_environment: bool = True, script: bytes = _ACTIVATE_SCRIPT
) -> ActivateExperimentEnvironmentReceipt:
    return ActivateExperimentEnvironmentReceipt(
        run_id=RunId("activation-0"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_SNAPSHOT,
        experiment_environment_path=ExperimentEnvironmentPath("runtime.tar") if experiment_environment else None,
        experiment_environment_digest=digest_bytes(_EXPERIMENT_ENVIRONMENT) if experiment_environment else None,
        activate_experiment_environment_script_digest=digest_bytes(script),
        launch_script_digest=LAUNCH,
    )


def _experiment_definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        name=_EXPERIMENT_NAME,
        run_script_path=OverlayPath(experiment_run_script_path(_EXPERIMENT_NAME)),
        run_script_digest=digest_bytes(_EXPERIMENT_SCRIPT),
        run_script_size=len(_EXPERIMENT_SCRIPT),
        verify_script_path=OverlayPath(experiment_verify_script_path(_EXPERIMENT_NAME)),
        verify_script_digest=digest_bytes(_EXPERIMENT_VERIFY),
        verify_script_size=len(_EXPERIMENT_VERIFY),
        output_paths=(WorkspacePath("outputs/result.txt"),),
    )


def _ree(
    *,
    source: bool = True,
    experiment_environment: bool = True,
    build: bool = True,
    activated: bool = True,
    experiments: bool = True,
) -> Ree:
    definition = ree_definition(
        experiment_environment=ExperimentEnvironmentDefinition(
            build_experiment_environment_script_digest=digest_bytes(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
            build_experiment_environment_script_size=len(_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
            artifact_path=ExperimentEnvironmentPath("runtime.tar") if experiment_environment else None,
        ),
        activate_experiment_environment=ActivateExperimentEnvironmentDefinition(
            activate_experiment_environment_script_digest=digest_bytes(_ACTIVATE_SCRIPT),
            activate_experiment_environment_script_size=len(_ACTIVATE_SCRIPT),
        ),
        experiments=(_experiment_definition(),) if experiments else (),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    if source:
        ree = commit_receipt(ree, _source_receipt())
    if experiment_environment and build:
        ree = commit_receipt(ree, _build_receipt())
    if source and activated:
        ree = commit_receipt(ree, _activation_receipt(experiment_environment=experiment_environment))
    return ree


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, _ACTIVATE_SCRIPT)
    store.overlay.write_bytes(experiment_run_script_path(_EXPERIMENT_NAME), _EXPERIMENT_SCRIPT)
    store.overlay.write_bytes(experiment_verify_script_path(_EXPERIMENT_NAME), _EXPERIMENT_VERIFY)
    kept = layout.kept_environment("runtime.tar")
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_bytes(_EXPERIMENT_ENVIRONMENT)
    write_snapshot(layout)
    store.write_ree(with_fixed_scripts(store.layout, ree or _ree()))
    return layout, store


def _outcome(status: str, *, verified: bool = True) -> ExperimentRunOutcome:
    if status == "succeeded":
        outputs = RunnableRunOutputs(
            subject_name="subject",
            exit_code=0,
            verify_exit_code=0 if verified else None,
            verdict="pass",
        )
    elif status == "canceled":
        outputs = RunnableRunOutputs(subject_name="subject", exit_code=-15)
    else:
        outputs = RunnableRunOutputs(subject_name="subject", exit_code=7, verdict="fail")
    return ExperimentRunOutcome(status=status, run_outputs=outputs)  # type: ignore[arg-type]


def _activate_alone(**kwargs: object) -> ExperimentRunOutcome:
    return _outcome("succeeded", verified=False)


def test_activation_runs_alone_and_commits_exact_input_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    ran: list[object] = []

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        ran.append(kwargs["runnable"])
        return _outcome("succeeded", verified=False)

    monkeypatch.setattr(runnable, "run_runnable", execute)

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    receipt = store.read_ree().subject.receipts.activate_experiment_environment
    assert result.status == "succeeded"
    assert [(spec.activate_script, spec.run_script, spec.verify_script) for spec in ran] == [  # type: ignore[attr-defined]
        (RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, "", "")
    ]
    assert receipt is not None
    assert receipt.run_id == "activation-1"
    assert receipt.snapshot_digest == _SNAPSHOT
    assert receipt.experiment_environment_path == "runtime.tar"
    assert receipt.experiment_environment_digest == digest_bytes(_EXPERIMENT_ENVIRONMENT)
    assert receipt.activate_experiment_environment_script_digest == digest_bytes(_ACTIVATE_SCRIPT)
    assert receipt.exit_code == 0


def test_native_activation_has_no_experiment_environment_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(experiment_environment=False, activated=False))
    monkeypatch.setattr(runnable, "run_runnable", _activate_alone)

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-native",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    receipt = store.read_ree().subject.receipts.activate_experiment_environment
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.experiment_environment_path is None
    assert receipt.experiment_environment_digest is None


def test_experiment_success_captures_outputs_and_commits_named_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    ran_in: list[Path] = []

    def runs(**kwargs: object) -> ExperimentRunOutcome:
        workspace = kwargs["workspace"]
        assert isinstance(workspace, Path)
        ran_in.append(workspace)
        output = workspace / "outputs/result.txt"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"result")
        return _outcome("succeeded")

    monkeypatch.setattr(runnable, "run_runnable", runs)

    result = run_experiment.handle_run_experiment(
        RunExperimentArgs(experiment_name=_EXPERIMENT_NAME),
        run_id="experiment-1",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    receipt = store.read_ree().subject.receipts.experiments.get(_EXPERIMENT_NAME)
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.run_id == "experiment-1"
    assert receipt.experiment_environment_digest == digest_bytes(_EXPERIMENT_ENVIRONMENT)
    assert receipt.activate_experiment_environment_script_digest == digest_bytes(_ACTIVATE_SCRIPT)
    assert receipt.run_script_digest == digest_bytes(_EXPERIMENT_SCRIPT)
    assert receipt.verify_script_digest == digest_bytes(_EXPERIMENT_VERIFY)
    assert receipt.working_environment is not None
    assert receipt.working_environment.host.arch
    assert (layout.results_dir(_EXPERIMENT_NAME) / "outputs/result.txt").read_bytes() == b"result"
    assert receipt.produced_output_digest == digest_output_paths(
        layout.results_dir(_EXPERIMENT_NAME),
        ["outputs/result.txt"],
    )
    # It ran in a workspace of its own, which went once the run succeeded.
    assert ran_in[0] != layout.workspace
    assert not ran_in[0].exists()


@pytest.mark.parametrize(
    ("ree", "message"),
    [
        (_ree(activated=False), "the activation has not been tested"),
        (
            commit_receipt(_ree(), _activation_receipt(script=b'#!/bin/sh\nexec env "$@"\n')),
            "activate experiment environment script changed",
        ),
    ],
)
def test_an_experiment_runs_only_while_the_activation_is_current(
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

    result = run_experiment.handle_run_experiment(
        RunExperimentArgs(experiment_name=_EXPERIMENT_NAME),
        run_id="experiment-unactivated",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=store.layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"
    assert message in result.failure.message
    assert executed is False
    assert store.read_ree().subject.receipts.experiments == {}


@pytest.mark.parametrize("status", ["failed", "canceled"])
def test_unsuccessful_attempt_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    monkeypatch.setattr(runnable, "run_runnable", lambda **kwargs: _outcome(status))

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-unsuccessful",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == status
    assert store.read_ree().subject.receipts.activate_experiment_environment is None


@pytest.mark.parametrize(
    ("ree", "message"),
    [
        (_ree(source=False), "source has not been acquired"),
        (_ree(build=False, activated=False), "experiment environment has not been built"),
        (record_seal(_ree(activated=False), sealed_at=_NOW), "sealed REE"),
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

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-rejected",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=store.layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"
    assert message in result.failure.message
    assert executed is False
    assert store.read_ree().subject.receipts.activate_experiment_environment is None


def test_changed_script_is_rejected_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    store.overlay.write_bytes(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, b"changed")
    executed = False

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        nonlocal executed
        executed = True
        return _outcome("succeeded")

    monkeypatch.setattr(runnable, "run_runnable", execute)

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-stale-script",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "activate experiment environment script does not match its definition" in result.failure.message
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
        layout=_layout,
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
    _layout, store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    monkeypatch.setattr(runnable, "run_runnable", _activate_alone)

    def conflict(*args: object, **kwargs: object) -> None:
        raise ReeRevisionConflictError("REE changed while activation ran")

    monkeypatch.setattr(runnable, "save_ree", conflict)

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-conflict",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    assert result.failure.retryable is True
    assert store.read_ree().subject.receipts.activate_experiment_environment is None


def test_a_step_runs_on_what_the_ree_records_and_nothing_a_view_or_an_earlier_step_left(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, _store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    (layout.workspace / "left-by-a-build.so").write_bytes(b"by-product")
    layout.upstream.mkdir(exist_ok=True)
    (layout.upstream / "edited-by-hand.txt").write_text("not acquired")
    seen: list[set[str]] = []

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        workspace = kwargs["workspace"]
        assert isinstance(workspace, Path)
        seen.append({path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file()})
        return _outcome("succeeded", verified=False)

    monkeypatch.setattr(runnable, "run_runnable", execute)
    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-1", log=lambda *args: None, is_canceled=lambda: False, layout=layout
    )

    assert result.status == "succeeded"
    assert "runtime.tar" in seen[0]
    assert RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT in seen[0]
    assert not {"left-by-a-build.so", "edited-by-hand.txt"} & seen[0]


def test_a_source_snapshot_other_than_the_one_acquired_stops_the_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch, _ree(activated=False))
    layout.snapshot_archive.write_bytes(b"another source")
    monkeypatch.setattr(runnable, "run_runnable", _activate_alone)

    result = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-1", log=lambda *args: None, is_canceled=lambda: False, layout=layout
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "not the one this REE acquired" in result.failure.message
    assert store.read_ree().subject.receipts.activate_experiment_environment is None


def test_a_current_step_runs_nothing_unless_asked_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    before = store.read_ree().subject.receipts.activate_experiment_environment
    ran: list[object] = []

    def execute(**kwargs: object) -> ExperimentRunOutcome:
        ran.append(kwargs)
        return _outcome("succeeded", verified=False)

    monkeypatch.setattr(runnable, "run_runnable", execute)

    current = activate_experiment_environment.handle_activate_experiment_environment(
        run_id="activation-1", log=lambda *args: None, is_canceled=lambda: False, layout=layout
    )
    assert current.status == "succeeded"
    assert ran == []
    assert store.read_ree().subject.receipts.activate_experiment_environment == before

    again = activate_experiment_environment.handle_activate_experiment_environment(
        ActivateExperimentEnvironmentArgs(again=True),
        run_id="activation-2",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )
    assert again.status == "succeeded"
    assert len(ran) == 1
    receipt = store.read_ree().subject.receipts.activate_experiment_environment
    assert receipt is not None
    assert receipt.run_id == "activation-2"
