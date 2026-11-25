from __future__ import annotations

from pathlib import Path

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.launch import declared_launch
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_core.execution.working_environment import observe_working_environment
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.source_repository import lay_out_run
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_core.workspace.attempt import discard, keep_environment, show_environment
from repo2ree_protocol.command import BuildExperimentEnvironmentArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import BuildExperimentEnvironmentFailureOutputs, BuildExperimentEnvironmentOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import ExperimentEnvironmentDefinition, Ree
from repo2ree_ree.primitives import Digest, ExperimentEnvironmentPath
from repo2ree_ree.receipt import BuildExperimentEnvironmentReceipt


def handle_build_experiment_environment(
    args: BuildExperimentEnvironmentArgs = BuildExperimentEnvironmentArgs(),  # noqa: B008
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "no REE here: run `ree initialize-ree` first")

    try:
        ree = load_ree(layout, store)
        build, experiment_environment_path = _check_preconditions(ree)
        if not args.again and (current := _current_receipt(layout, ree)) is not None:
            log("system", "info", "the experiment environment is current: nothing to do (--again builds it anyway)")
            return ActionResult(
                status="succeeded",
                exit_code=0,
                outputs=BuildExperimentEnvironmentOutputs(
                    build_experiment_environment_script_path=str(build.build_experiment_environment_script_path),
                    container_exit_code=0,
                    receipt=current,
                ).model_dump(mode="json", exclude_none=True),
            )
        workspace = lay_out_run(layout, ree, run_id, environment=False)
        _check_script(workspace, build)
        launch = declared_launch(ree.subject.definition.launch, workspace)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot build the experiment environment: {exc}")
        return ActionResult.failed("precondition", f"cannot build the experiment environment: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load build inputs: {exc}")

    before_revision = revision_of(ree)

    timer = OperationTimer.start()
    log("system", "info", f"Starting build run {run_id}")
    log("system", "info", f"REE revision: {before_revision}")
    log("system", "info", f"Build script: {build.build_experiment_environment_script_path}")
    outcome = run_workspace_script(
        workspace,
        str(build.build_experiment_environment_script_path),
        log=log,
        is_canceled=is_canceled,
        launch=launch,
    )
    if outcome.status == "canceled":
        log("system", "warn", "build_experiment_environment canceled")
        return ActionResult(status="canceled")
    if outcome.status != "succeeded":
        log("system", "error", f"build_experiment_environment failed with exit code {outcome.exit_code}")
        return ActionResult.failed(
            "execution",
            "build_experiment_environment failed",
            exit_code=outcome.exit_code or 1,
            outputs=BuildExperimentEnvironmentFailureOutputs(
                build_experiment_environment_script_path=str(build.build_experiment_environment_script_path),
                container_exit_code=outcome.exit_code,
            ).model_dump(mode="json"),
        )

    kept = keep_environment(layout, workspace, str(experiment_environment_path))
    produced_artifact_digest = digest_file_if_exists(kept) if kept is not None else None
    if produced_artifact_digest is None:
        message = f"build script succeeded but did not produce {experiment_environment_path}"
        log("system", "error", message)
        return ActionResult.failed("execution", message)

    timing = timer.finish()
    source = ree.subject.receipts.acquire_source
    if source is None:
        raise AssertionError("build preconditions admitted a REE without source evidence")
    receipt = BuildExperimentEnvironmentReceipt(
        **receipt_envelope(run_id, timing),
        snapshot_digest=source.snapshot_digest,
        build_experiment_environment_script_path=build.build_experiment_environment_script_path,
        build_experiment_environment_script_digest=build.build_experiment_environment_script_digest,
        artifact_path=experiment_environment_path,
        produced_artifact_digest=produced_artifact_digest,
        working_environment=observe_working_environment(),
        launch_script_digest=_launch_digest(ree),
        launched=outcome.launched,
    )
    try:
        save_ree(
            layout,
            store,
            commit_receipt(ree, receipt),
            expected_revision=before_revision,
        )
    except ReeRevisionConflictError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        log("system", "error", f"failed to commit build receipt: {exc}")
        return failed_from_exception(exc, f"failed to commit build receipt: {exc}")

    discard(layout, run_id)
    show_environment(layout, str(experiment_environment_path))
    log(
        "system",
        "info",
        f"build_experiment_environment succeeded in {format_duration_ms(timing.duration_ms)} "
        f"(duration_ms={timing.duration_ms})",
    )
    outputs = BuildExperimentEnvironmentOutputs(
        build_experiment_environment_script_path=str(build.build_experiment_environment_script_path),
        container_exit_code=outcome.exit_code or 0,
        receipt=receipt,
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=outputs.model_dump(mode="json", exclude_none=True),
    )


def _check_preconditions(ree: Ree) -> tuple[ExperimentEnvironmentDefinition, ExperimentEnvironmentPath]:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot build an experiment environment")
    source_audit = audit(ree).acquire_source
    if source_audit.evidence != "current":
        raise ReePreconditionError("; ".join(source_audit.reasons) or "source has not been acquired")
    build = ree.subject.definition.experiment_environment
    experiment_environment_path = build.artifact_path
    if experiment_environment_path is None:
        raise ReePreconditionError("no experiment environment artifact path is declared")
    return build, experiment_environment_path


def _current_receipt(layout: ReeLayout, ree: Ree) -> BuildExperimentEnvironmentReceipt | None:
    receipt = ree.subject.receipts.build_experiment_environment
    if receipt is None or audit(ree).build_experiment_environment.evidence != "current":
        return None
    kept = layout.kept_environment(str(receipt.artifact_path))
    return receipt if digest_file_if_exists(kept) == receipt.produced_artifact_digest else None


def _check_script(workspace: Path, build: ExperimentEnvironmentDefinition) -> None:
    script = workspace / str(build.build_experiment_environment_script_path)
    if not script.is_file():
        raise ReePreconditionError("the build experiment environment script is missing")
    if (
        digest_file_if_exists(script) != build.build_experiment_environment_script_digest
        or script.stat().st_size != build.build_experiment_environment_script_size
    ):
        raise ReePreconditionError("the build experiment environment script does not match its definition")


def _launch_digest(ree: Ree) -> Digest:
    return ree.subject.definition.launch.launch_script_digest
