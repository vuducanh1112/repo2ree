"""Build the declared runtime and atomically commit its successful receipt."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.ree.model import BuildRuntimeDefinition, Ree, RuntimeDefinition
from repo2ree_core.domain.ree.receipt import BuildRuntimeReceipt, receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck, run_workspace_script
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_core.workspace.drift import check_workspace_drift
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class BuildRuntimeOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int
    receipt: BuildRuntimeReceipt


def handle_build_runtime(
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
        build, runtime = _check_preconditions(ree, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot build runtime: {exc}")
        return ActionResult.failed("precondition", f"cannot build runtime: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load build inputs: {exc}")

    before_revision = revision_of(ree)
    excluded_paths = {str(runtime.runtime_path)}
    for experiment in ree.subject.definition.experiments:
        excluded_paths.update(str(path) for path in experiment.output_paths)
    workspace_drift = check_workspace_drift(layout, excluded_paths=excluded_paths)

    timer = OperationTimer.start()
    log("system", "info", f"Starting build run {run_id}")
    log("system", "info", f"REE revision: {before_revision}")
    log("system", "info", f"Build script: {build.build_runtime_script_path}")
    outcome = run_workspace_script(
        layout.workspace.resolve(),
        str(build.build_runtime_script_path),
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled":
        log("system", "warn", "build_runtime canceled")
        return ActionResult(status="canceled")
    if outcome.status != "succeeded":
        log("system", "error", f"build_runtime failed with exit code {outcome.exit_code}")
        return ActionResult.failed(
            "execution",
            "build_runtime failed",
            exit_code=outcome.exit_code or 1,
            outputs={
                "build_runtime_script_path": str(build.build_runtime_script_path),
                "container_exit_code": outcome.exit_code,
            },
        )

    produced_runtime_digest = digest_file_if_exists(layout.workspace / str(runtime.runtime_path))
    if produced_runtime_digest is None:
        message = f"build script succeeded but did not produce {runtime.runtime_path}"
        log("system", "error", message)
        return ActionResult.failed("execution", message)

    timing = timer.finish()
    source = ree.subject.receipts.source
    if source is None:  # guarded by _check_preconditions
        raise AssertionError("build preconditions admitted a REE without source evidence")
    receipt = BuildRuntimeReceipt(
        **receipt_envelope(run_id, timing),
        snapshot_digest=source.snapshot_digest,
        build_runtime_script_path=build.build_runtime_script_path,
        build_runtime_script_digest=build.build_runtime_script_digest,
        workspace_drift=workspace_drift,
        runtime_path=runtime.runtime_path,
        produced_runtime_digest=produced_runtime_digest,
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
        f"build_runtime succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    outputs = BuildRuntimeOutputs(
        build_runtime_script_path=str(build.build_runtime_script_path),
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
) -> tuple[BuildRuntimeDefinition, RuntimeDefinition]:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot build a runtime")
    if ree.subject.receipts.source is None:
        raise ReePreconditionError("source has not been acquired")
    build = ree.subject.definition.build_runtime
    if build is None:
        raise ReePreconditionError("no runtime build definition is present")
    runtime = ree.subject.definition.runtime
    if runtime is None:
        raise ReePreconditionError("no runtime artifact path is declared")
    script = layout.workspace / str(build.build_runtime_script_path)
    if not script.is_file():
        raise ReePreconditionError("the runtime build script is missing")
    actual_digest = digest_file_if_exists(script)
    if actual_digest != build.build_runtime_script_digest or script.stat().st_size != build.build_runtime_script_size:
        raise ReePreconditionError("the runtime build script does not match its definition")
    return build, runtime
