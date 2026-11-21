from __future__ import annotations

from pathlib import Path

import pytest
from ree_definitions import SNAPSHOT_DIGEST, ree_definition, with_fixed_scripts, write_snapshot

from repo2ree_core.domain.ree.transitions import commit_receipt, record_seal
from repo2ree_core.execution.process import StepOutcome
from repo2ree_core.operations.handlers.author import build_experiment_environment
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError
from repo2ree_protocol.command import BuildExperimentEnvironmentArgs
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentEnvironmentDefinition, Ree, ReeSubject, SourceDefinition
from repo2ree_ree.primitives import ExperimentEnvironmentPath, RunId, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SNAPSHOT_DIGEST = SNAPSHOT_DIGEST
_SCRIPT = b"#!/bin/sh\nprintf experiment environment > runtime.tar\n"
_ORIGIN_URL = "https://example.test/repo.git"


def _source_receipt() -> AcquireSourceReceipt:
    return AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url=_ORIGIN_URL,
        source_type="git",
        resolved_revision="abc123",
        snapshot_digest=_SNAPSHOT_DIGEST,
    )


def _ree(*, with_source: bool = True, with_experiment_environment: bool = True, origin_url: str = _ORIGIN_URL) -> Ree:
    # Declaration and receipt move together, as ``acquire_source`` commits them:
    # a source receipt with no declaration behind it is an orphan the audit
    # reports as stale, not the ordinary acquired state this fixture stands for.
    definition = ree_definition(
        source=SourceDefinition(origin_url=origin_url, source_type="git") if with_source else None,
        experiment_environment=ExperimentEnvironmentDefinition(
            build_experiment_environment_script_digest=digest_bytes(_SCRIPT),
            build_experiment_environment_script_size=len(_SCRIPT),
            artifact_path=ExperimentEnvironmentPath("runtime.tar") if with_experiment_environment else None,
        ),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    return commit_receipt(ree, _source_receipt()) if with_source else ree


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree | None = None,
) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, _SCRIPT)
    write_snapshot(layout)
    store.write_ree(with_fixed_scripts(store.layout, ree or _ree()))
    return layout, store


def _successful_build(layout: ReeLayout):
    def run(workspace: Path, *args: object, **kwargs: object) -> StepOutcome:
        assert workspace != layout.workspace
        (workspace / "runtime.tar").write_bytes(b"experiment_environment")
        return StepOutcome(status="succeeded", exit_code=0)

    return run


def test_successful_build_commits_one_inline_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", _successful_build(layout))

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-1", log=lambda *args: None, is_canceled=lambda: False, layout=layout
    )

    receipt = store.read_ree().subject.receipts.build_experiment_environment
    assert result.status == "succeeded"
    assert receipt is not None
    assert receipt.run_id == "build-1"
    assert receipt.snapshot_digest == _SNAPSHOT_DIGEST
    assert receipt.build_experiment_environment_script_digest == digest_bytes(_SCRIPT)
    assert receipt.artifact_path == "runtime.tar"
    assert receipt.produced_artifact_digest == digest_bytes(b"experiment_environment")
    # It ran in a workspace laid out fresh from what the REE records, and the environment it made is kept beside it.
    assert receipt.workspace_drift.status == "clean"
    assert layout.kept_environment("runtime.tar").read_bytes() == b"experiment_environment"
    # What the build ran in: the host ree runs on.
    assert receipt.working_environment is not None
    assert receipt.working_environment.host.arch


def test_failed_build_process_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(
        build_experiment_environment,
        "run_workspace_script",
        lambda *args, **kwargs: StepOutcome(status="failed", exit_code=7),
    )

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-failed",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.exit_code == 7
    assert result.failure is not None
    assert result.failure.category == "execution"
    assert store.read_ree().subject.receipts.build_experiment_environment is None


def test_successful_exit_without_declared_artifact_commits_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(
        build_experiment_environment,
        "run_workspace_script",
        lambda *args, **kwargs: StepOutcome(status="succeeded", exit_code=0),
    )

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-no-artifact",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "did not produce runtime.tar" in result.failure.message
    assert store.read_ree().subject.receipts.build_experiment_environment is None


@pytest.mark.parametrize(
    ("ree", "message"),
    [
        (_ree(with_source=False), "source has not been acquired"),
        (_ree(with_experiment_environment=False), "no experiment environment artifact path is declared"),
        (record_seal(_ree(), sealed_at=_NOW), "sealed REE"),
    ],
)
def test_build_preconditions_reject_incomplete_or_sealed_ree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ree: Ree,
    message: str,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch, ree)
    executed = False

    def run(*args: object, **kwargs: object) -> StepOutcome:
        nonlocal executed
        executed = True
        return StepOutcome(status="succeeded", exit_code=0)

    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", run)

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-rejected",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=store.layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert message in result.failure.message
    assert executed is False
    assert store.read_ree().subject.receipts.build_experiment_environment is None


def test_changed_build_experiment_environment_script_is_rejected_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, store = _workbench(tmp_path, monkeypatch)
    store.overlay.write_text(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, "#!/bin/sh\nexit 0\n")
    executed = False

    def run(*args: object, **kwargs: object) -> StepOutcome:
        nonlocal executed
        executed = True
        return StepOutcome(status="succeeded", exit_code=0)

    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", run)

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-stale-script",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "does not match its definition" in result.failure.message
    assert executed is False


def test_revision_conflict_does_not_select_the_new_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", _successful_build(layout))

    def conflict(*args: object, **kwargs: object) -> None:
        raise ReeRevisionConflictError("REE changed while the build ran")

    monkeypatch.setattr(build_experiment_environment, "save_ree", conflict)

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-conflict",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    assert result.failure.retryable is True
    assert store.read_ree().subject.receipts.build_experiment_environment is None


def test_build_is_rejected_when_the_source_receipt_has_gone_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A re-pointed source that was never re-acquired must not reach the build.

    The workspace still holds the previous tree, so building would spend the
    whole run producing an experiment environment the seal gate refuses anyway — for staleness
    already visible before the first byte of work.
    """
    repointed = _ree(origin_url="https://example.test/other.git")
    _layout, store = _workbench(tmp_path, monkeypatch, repointed)
    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", _successful_build(_layout))

    result = build_experiment_environment.handle_build_experiment_environment(
        run_id="build-stale-source",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=_layout,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "source origin changed" in result.failure.message
    assert store.read_ree().subject.receipts.build_experiment_environment is None


def test_a_build_whose_evidence_is_current_runs_nothing_unless_asked_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    calls: list[Path] = []
    built = _successful_build(layout)

    def counted(workspace: Path, *args: object, **kwargs: object) -> StepOutcome:
        calls.append(workspace)
        outcome: StepOutcome = built(workspace, *args, **kwargs)
        return outcome

    monkeypatch.setattr(build_experiment_environment, "run_workspace_script", counted)

    def build(run_id: str, *, again: bool = False) -> str:
        return build_experiment_environment.handle_build_experiment_environment(
            BuildExperimentEnvironmentArgs(again=again),
            run_id=run_id,
            log=lambda *args: None,
            is_canceled=lambda: False,
            layout=layout,
        ).status

    assert build("build-1") == "succeeded"
    assert build("build-2") == "succeeded"
    assert len(calls) == 1
    receipt = store.read_ree().subject.receipts.build_experiment_environment
    assert receipt is not None
    assert receipt.run_id == "build-1"
    # The environment it made is gone, so the build is no longer current.
    layout.kept_environment("runtime.tar").unlink()
    assert build("build-3") == "succeeded"
    assert build("build-4", again=True) == "succeeded"
    assert len(calls) == 3
