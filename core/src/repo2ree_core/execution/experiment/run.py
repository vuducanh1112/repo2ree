from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.launch import Launch
from repo2ree_core.execution.process import (
    CancelCheck,
    StepOutcome,
)
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.paths import validate_relative_path
from repo2ree_ree.receipt import Launched
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import ScriptSpanAttrs, record_current_span_facts, record_exit_code

tracer = get_tracer(__name__)


class RunnableRunOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_name: str
    exit_code: int | None = None
    verify_exit_code: int | None = None
    verdict: Literal["pass", "fail"] | None = None


@dataclass
class ExperimentRunOutcome:
    status: ActionStatus
    run_outputs: RunnableRunOutputs
    launched: Launched | None = None


def _run_script(
    workspace: Path,
    script_rel: str | None,
    log: LogSink,
    is_canceled: CancelCheck,
    activate_rel: str | None = None,
    launch: Launch | None = None,
) -> StepOutcome:
    if script_rel is not None:
        validate_relative_path(script_rel)
    return run_workspace_script(
        workspace, script_rel, log=log, is_canceled=is_canceled, activate_rel=activate_rel, launch=launch
    )


def run_runnable(
    *,
    workspace: Path,
    runnable: RunnableSpec,
    label: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    workspace = workspace.resolve()

    outputs = RunnableRunOutputs(subject_name=label)

    log("system", "info", f"Starting run {run_id}")
    log("system", "info", f"Subject: {label!r}")
    log("system", "info", f"Run script: {runnable.run_script or '(none: the activation alone)'}")

    record_current_span_facts({"runnable.subject": label})

    try:
        with tracer.start_as_current_span("runnable.run") as span:
            ScriptSpanAttrs(path=runnable.run_script or runnable.activate_script).apply(span)
            run_outcome = _run_script(
                workspace,
                runnable.run_script or None,
                log,
                is_canceled,
                runnable.activate_script,
                runnable.launch,
            )
            record_exit_code(span, run_outcome.exit_code)
    except Exception as exc:  # noqa: BLE001
        log("system", "error", f"Run failed: {exc}")
        return ExperimentRunOutcome(status="failed", run_outputs=outputs)

    log(
        "system",
        "info" if run_outcome.status == "succeeded" else "error",
        f"Run {run_outcome.status} (exit code {run_outcome.exit_code})",
    )

    outputs.exit_code = run_outcome.exit_code
    launched = run_outcome.launched

    if run_outcome.status == "canceled":
        return ExperimentRunOutcome(status="canceled", run_outputs=outputs, launched=launched)

    if not runnable.verify_script:
        outputs.verdict = "pass" if run_outcome.status == "succeeded" else "fail"
        log("system", "info" if outputs.verdict == "pass" else "error", f"Verdict: {outputs.verdict.upper()}")
        return ExperimentRunOutcome(status=run_outcome.status, run_outputs=outputs, launched=launched)

    log("system", "info", f"Verify script: {runnable.verify_script}")
    try:
        with tracer.start_as_current_span("runnable.verify") as span:
            ScriptSpanAttrs(path=runnable.verify_script).apply(span)
            verify_outcome = _run_script(workspace, runnable.verify_script, log, is_canceled, launch=runnable.launch)
            record_exit_code(span, verify_outcome.exit_code)
    except Exception as exc:  # noqa: BLE001
        log("system", "error", f"Verify failed: {exc}")
        outputs.verdict = "fail"
        return ExperimentRunOutcome(status="failed", run_outputs=outputs, launched=launched)

    outputs.verify_exit_code = verify_outcome.exit_code
    if verify_outcome.status == "canceled":
        return ExperimentRunOutcome(status="canceled", run_outputs=outputs, launched=launched)

    outputs.verdict = "pass" if (run_outcome.status == "succeeded" and verify_outcome.exit_code == 0) else "fail"
    log("system", "info" if outputs.verdict == "pass" else "error", f"Verdict: {outputs.verdict.upper()}")

    status: ActionStatus = "succeeded" if outputs.verdict == "pass" else "failed"
    return ExperimentRunOutcome(status=status, run_outputs=outputs, launched=launched)
