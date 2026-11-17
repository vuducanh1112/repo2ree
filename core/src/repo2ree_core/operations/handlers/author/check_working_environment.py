"""Run the author's check of the working environment there, launched as every script is, and record that it passed."""

from __future__ import annotations

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.launch import declared_launch
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_core.execution.working_environment import observe_working_environment
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import RunnableOperationOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import CheckWorkingEnvironmentDefinition, Ree
from repo2ree_ree.receipt import CheckWorkingEnvironmentReceipt

_LABEL = "check_working_environment"


def declared_check(ree: Ree, layout: ReeLayout) -> CheckWorkingEnvironmentDefinition:
    """The check the REE declares, once its script in the workspace is the one it declares."""
    declared = ree.subject.definition.check_working_environment
    path = layout.workspace / str(declared.check_working_environment_script_path)
    if not path.is_file():
        raise ReePreconditionError(f"the check script is missing: {declared.check_working_environment_script_path}")
    if digest_file(path) != declared.check_working_environment_script_digest:
        raise ReePreconditionError("the check script does not match its definition")
    return declared


def handle_check_working_environment(
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
        if ree.seal is not None:
            raise ReePreconditionError("a sealed REE cannot run author operations")
        declared = declared_check(ree, layout)
        launch = declared_launch(ree.subject.definition.launch, layout.workspace)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot {_LABEL}: {exc}")
        return ActionResult.failed("precondition", f"cannot {_LABEL}: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load {_LABEL} inputs: {exc}")

    before_revision = revision_of(ree)
    script = str(declared.check_working_environment_script_path)
    timer = OperationTimer.start()
    outcome = run_workspace_script(layout.workspace, script, log=log, is_canceled=is_canceled, launch=launch)
    outputs = RunnableOperationOutputs(subject_name="working environment", exit_code=outcome.exit_code)
    if outcome.status == "canceled":
        log("system", "warn", f"{_LABEL} canceled")
        return ActionResult(status="canceled", outputs=outputs.model_dump(mode="json", exclude_none=True))
    if outcome.status != "succeeded":
        exit_code = outcome.exit_code or 1
        log("system", "error", f"the working environment does not pass its check (exit code {exit_code})")
        return ActionResult.failed(
            "execution",
            f"{_LABEL} failed",
            exit_code=exit_code,
            outputs=outputs.model_dump(mode="json", exclude_none=True),
        )
    observed = observe_working_environment()
    timing = timer.finish()
    receipt = CheckWorkingEnvironmentReceipt(
        **receipt_envelope(run_id, timing),
        check_working_environment_script_digest=declared.check_working_environment_script_digest,
        exit_code=0,
        working_environment=observed,
        launch_script_digest=ree.subject.definition.launch.launch_script_digest,
        launched=outcome.launched,
    )
    try:
        save_ree(layout, store, commit_receipt(ree, receipt), expected_revision=before_revision)
    except ReeRevisionConflictError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        log("system", "error", f"failed to commit {_LABEL} receipt: {exc}")
        return failed_from_exception(exc, f"failed to commit {_LABEL} receipt: {exc}")
    outputs.receipt = receipt
    log("system", "info", "the working environment passes its check")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json", exclude_none=True))
