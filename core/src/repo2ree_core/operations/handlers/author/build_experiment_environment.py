"""Build the declared experiment environment and atomically commit its successful receipt."""

from __future__ import annotations

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.runners import current_runner, run_workspace_script
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_core.workspace.drift import check_workspace_drift
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import BuildExperimentEnvironmentFailureOutputs, BuildExperimentEnvironmentOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import ExperimentEnvironmentDefinition, Ree
from repo2ree_ree.primitives import ExperimentEnvironmentPath
from repo2ree_ree.receipt import BuildExperimentEnvironmentReceipt


def handle_build_experiment_environment(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")

    try:
        ree = load_ree(layout, store)
        build, experiment_environment_path = _check_preconditions(ree, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot build the experiment environment: {exc}")
        return ActionResult.failed("precondition", f"cannot build the experiment environment: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load build inputs: {exc}")

    before_revision = revision_of(ree)
    excluded_paths = {str(experiment_environment_path)}
    for experiment in ree.subject.definition.experiments:
        excluded_paths.update(str(path) for path in experiment.output_paths)
    workspace_drift = check_workspace_drift(layout, excluded_paths=excluded_paths)

    timer = OperationTimer.start()
    log("system", "info", f"Starting build run {run_id}")
    log("system", "info", f"REE revision: {before_revision}")
    log("system", "info", f"Build script: {build.build_experiment_environment_script_path}")
    outcome = run_workspace_script(
        layout.workspace.resolve(),
        str(build.build_experiment_environment_script_path),
        log=log,
        is_canceled=is_canceled,
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

    produced_artifact_digest = digest_file_if_exists(layout.workspace / str(experiment_environment_path))
    if produced_artifact_digest is None:
        message = f"build script succeeded but did not produce {experiment_environment_path}"
        log("system", "error", message)
        return ActionResult.failed("execution", message)

    timing = timer.finish()
    source = ree.subject.receipts.source
    if source is None:  # guarded by _check_preconditions
        raise AssertionError("build preconditions admitted a REE without source evidence")
    receipt = BuildExperimentEnvironmentReceipt(
        **receipt_envelope(run_id, timing),
        snapshot_digest=source.snapshot_digest,
        build_experiment_environment_script_path=build.build_experiment_environment_script_path,
        build_experiment_environment_script_digest=build.build_experiment_environment_script_digest,
        workspace_drift=workspace_drift,
        artifact_path=experiment_environment_path,
        produced_artifact_digest=produced_artifact_digest,
        workbench_environment=current_runner().observe(ree.subject.definition.workbench_environment),
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


def _check_preconditions(
    ree: Ree,
    layout: ReeLayout,
) -> tuple[ExperimentEnvironmentDefinition, ExperimentEnvironmentPath]:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot build an experiment environment")
    # Currency, not mere presence. A source that has been re-pointed but not
    # re-acquired leaves the workspace holding the previous tree, so a build on
    # it would spend minutes producing an experiment environment the seal gate then refuses for
    # the staleness that was already visible here. Same check the SBOM and
    # runnable steps make against the build receipt.
    source_audit = audit(ree).source
    if source_audit.evidence != "current":
        # The audit names what moved when a receipt has gone stale. It has
        # nothing to say when no source is declared at all — a fresh REE seeded
        # with a build script before it has a source — so that case keeps the
        # message that tells the author what to do next.
        raise ReePreconditionError("; ".join(source_audit.reasons) or "source has not been acquired")
    build = ree.subject.definition.experiment_environment
    if build is None:
        raise ReePreconditionError("no experiment environment build definition is present")
    experiment_environment_path = build.artifact_path
    if experiment_environment_path is None:
        raise ReePreconditionError("no experiment environment artifact path is declared")
    script = layout.workspace / str(build.build_experiment_environment_script_path)
    if not script.is_file():
        raise ReePreconditionError("the build experiment environment script is missing")
    actual_digest = digest_file_if_exists(script)
    if (
        actual_digest != build.build_experiment_environment_script_digest
        or script.stat().st_size != build.build_experiment_environment_script_size
    ):
        raise ReePreconditionError("the build experiment environment script does not match its definition")
    return build, experiment_environment_path
