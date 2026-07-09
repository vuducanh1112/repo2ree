"""Orchestrate a single runnable run: run script, then optional verify script.

Each runnable (an experiment or the REE's activation) owns its run script: a
workspace-relative shell script that fully defines how it executes — including
entering its runtime (e.g. its own ``docker run …``). The runner executes that
script from the workspace root and captures stdout/stderr.

Verification is a second author-owned script, not a matcher engine and with no
magic contract: when the runnable declares a ``verify_script``, the runner
executes it from the workspace root after a completed run, exactly like the run
script, and its exit code is the verdict (0 = pass). Nothing is injected into
its environment. The verify script reads whatever it needs straight from the
workspace — so an author who wants to check the run's stdout has the run script
materialize it to a workspace file (e.g. ``… | tee results/run.log``) and the
verify script reads that file, just like any other output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_core.experiment.experiment import Runnable, validate_runnable_script_path
from repo2ree_core.run_script import (
    CancelCheck,
    StepOutcome,
    run_workspace_script,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_protocol.tracing import get_tracer

tracer = get_tracer(__name__)


# ================================================
# Result type
# ================================================


@dataclass
class ExperimentRunOutcome:
    """Result of a runnable run.

    ``run_outputs`` is the serialized payload for the run store.
    """

    status: ActionStatus
    run_outputs: dict[str, Any]


# ================================================
# Script execution
# ================================================


def _run_script(
    workspace: Path,
    script_rel: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> StepOutcome:
    """Validate a runnable's script path, then run it via the shared runner."""
    script_rel = validate_runnable_script_path(script_rel)
    return run_workspace_script(workspace, script_rel, log=log, is_canceled=is_canceled)


# ================================================
# Public entrypoint
# ================================================


def run_runnable(
    *,
    workspace: Path,
    runnable: Runnable,
    label: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    """Run *runnable*'s run script, then its verify script when declared.

    Shared by experiments and activation — both are :class:`Runnable`.
    """
    workspace = workspace.resolve()

    base_outputs: dict[str, Any] = {"subjectName": label}

    log("system", "info", f"Starting run {run_id}")
    log("system", "info", f"Subject: {label!r}")
    log("system", "info", f"Run script: {runnable.run_script}")

    try:
        with tracer.start_as_current_span("runnable.run"):
            run_outcome = _run_script(workspace, runnable.run_script, log, is_canceled)
    except Exception as exc:
        log("system", "error", f"Run failed: {exc}")
        return ExperimentRunOutcome(
            status="failed",
            run_outputs={**base_outputs, "exitCode": None},
        )

    log(
        "system",
        "info" if run_outcome.status == "succeeded" else "error",
        f"Run {run_outcome.status} (exit code {run_outcome.exit_code})",
    )

    run_outputs: dict[str, Any] = {**base_outputs, "exitCode": run_outcome.exit_code}

    if run_outcome.status == "canceled":
        return ExperimentRunOutcome(status="canceled", run_outputs=run_outputs)

    if not runnable.verify_script:
        # No verify script declared: the run's exit code is the verdict.
        verdict = "pass" if run_outcome.status == "succeeded" else "fail"
        run_outputs["verdict"] = verdict
        log("system", "info" if verdict == "pass" else "error", f"Verdict: {verdict.upper()}")
        return ExperimentRunOutcome(status=run_outcome.status, run_outputs=run_outputs)

    log("system", "info", f"Verify script: {runnable.verify_script}")
    try:
        with tracer.start_as_current_span("runnable.verify"):
            verify_outcome = _run_script(workspace, runnable.verify_script, log, is_canceled)
    except Exception as exc:
        log("system", "error", f"Verify failed: {exc}")
        run_outputs["verifyExitCode"] = None
        run_outputs["verdict"] = "fail"
        return ExperimentRunOutcome(status="failed", run_outputs=run_outputs)

    run_outputs["verifyExitCode"] = verify_outcome.exit_code
    if verify_outcome.status == "canceled":
        return ExperimentRunOutcome(status="canceled", run_outputs=run_outputs)

    verdict = "pass" if (run_outcome.status == "succeeded" and verify_outcome.exit_code == 0) else "fail"
    run_outputs["verdict"] = verdict
    log("system", "info" if verdict == "pass" else "error", f"Verdict: {verdict.upper()}")

    status: ActionStatus = "succeeded" if verdict == "pass" else "failed"
    return ExperimentRunOutcome(status=status, run_outputs=run_outputs)
