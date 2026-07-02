"""Orchestrate a single experiment run.

Each runnable (an experiment or the REE's activation) owns its run script: a
workspace-relative shell script that fully defines how it executes — including
entering its runtime (e.g. its own ``docker run …``). The runner simply executes
that script from the workspace root and captures stdout/stderr, then evaluates
the declared outputs against the workspace on the host.

Because the script owns the runtime, declared file outputs must be surfaced into
the workspace (e.g. via a bind mount) so they can be read back here; their paths
are workspace-relative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from repo2ree_core.container.run_script import (
    CancelCheck,
    LogSink,
    StepOutcome,
    run_streaming_process,
    run_workspace_script,
)
from repo2ree_core.experiment.evaluate import (
    CaptureBundle,
    ExperimentRunResult,
    OutputResult,
    evaluate_output,
    make_run_result,
    snapshot_outputs,
    source_key,
)
from repo2ree_core.experiment.experiment import (
    CustomMatch,
    ExpectedOutput,
    FileSource,
    Runnable,
    validate_runnable_script_path,
)
from repo2ree_core.path_safety import resolve_within
from repo2ree_protocol.result import ActionStatus
from repo2ree_protocol.tracing import get_tracer

tracer = get_tracer(__name__)


# ================================================
# Result type
# ================================================


@dataclass
class ExperimentRunOutcome:
    """Result of an experiment run.

    ``run_outputs`` is the serialized payload for the run store.
    ``snapshot_to_persist`` is non-None only for a successful snapshot run,
    and holds the baselines the caller must write back into the REE draft.
    """

    status: ActionStatus
    run_outputs: dict[str, Any]
    snapshot_to_persist: list[ExpectedOutput] | None = field(default=None)


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
# Capture bundle
# ================================================


def build_capture_bundle(
    stdout: str,
    stderr: str,
    *,
    workspace: Path,
    outputs: list[ExpectedOutput],
) -> CaptureBundle:
    """Capture stdout/stderr plus any declared file outputs read from disk.

    File outputs are read from the workspace on the host: the run script is
    responsible for surfacing them there (e.g. through a bind mount). Missing
    files are simply absent from the bundle and surface as failures during
    evaluation.
    """
    files: dict[str, bytes] = {}
    for expected in outputs:
        src = expected.source
        if not isinstance(src, FileSource):
            continue
        candidate = resolve_within(workspace, src.path)
        if candidate is not None and candidate.is_file():
            files[src.path] = candidate.read_bytes()
    return CaptureBundle(stdout=stdout, stderr=stderr, files=files)


# ================================================
# Custom match evaluation (host subprocess)
# ================================================


def _evaluate_custom_match_text(
    *,
    match: CustomMatch,
    text: str,
    workspace: Path,
    log: LogSink,
    is_canceled: CancelCheck,
) -> tuple[bool, str]:
    """Run a custom validator on the host with the captured text as stdin."""
    try:
        with NamedTemporaryFile("w", suffix=".sh", dir=workspace, delete=False, encoding="utf-8") as handle:
            handle.write(match.value)
            validator_abs = Path(handle.name)
    except Exception as exc:
        return False, f"custom script setup error: {exc}"

    try:
        result = run_streaming_process(
            ["sh", validator_abs.name],
            log=log,
            stdin_text=text,
            cwd=workspace,
            is_canceled=is_canceled,
        )
    except Exception as exc:
        return False, f"custom script error: {exc}"
    finally:
        validator_abs.unlink(missing_ok=True)

    if result.canceled or is_canceled():
        return False, "custom script canceled"
    if result.returncode == 0:
        return True, "custom script exited 0"
    return False, f"custom script exited {result.returncode}"


# ================================================
# Output evaluation dispatch
# ================================================


def _evaluate_all_outputs(
    outputs: list[ExpectedOutput],
    exit_code: int | None,
    captures: CaptureBundle,
    *,
    workspace: Path,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunResult:
    output_results: list[OutputResult] = []
    for expected in outputs:
        if isinstance(expected.match, CustomMatch):
            key = source_key(expected.source)
            text = captures.text_for(expected.source)
            if text is None:
                output_results.append(
                    OutputResult(source_key=key, mode="custom", passed=False, detail="source not found")
                )
                continue
            passed, detail = _evaluate_custom_match_text(
                match=expected.match,
                text=text,
                workspace=workspace,
                log=log,
                is_canceled=is_canceled,
            )
            output_results.append(OutputResult(source_key=key, mode="custom", passed=passed, detail=detail))
        else:
            output_results.append(evaluate_output(expected, captures))

    return make_run_result(exit_code, output_results)


# ================================================
# Public entrypoint
# ================================================


def run_runnable(
    *,
    workspace: Path,
    runnable: Runnable,
    label: str,
    mode: Literal["verify", "snapshot"],
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    """Run *runnable*'s script and compute the outcome.

    Shared by experiments and activation — both are :class:`Runnable`.
    """
    workspace = workspace.resolve()

    base_outputs: dict[str, Any] = {
        "subjectName": label,
        "mode": mode,
    }

    log("system", "info", f"Starting run {run_id}")
    log("system", "info", f"Subject: {label!r}")
    log("system", "info", f"Mode: {mode}")
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

    captures = build_capture_bundle(
        run_outcome.captured_stdout,
        run_outcome.captured_stderr,
        workspace=workspace,
        outputs=runnable.outputs,
    )

    if mode == "verify":
        with tracer.start_as_current_span("runnable.evaluate"):
            result = _evaluate_all_outputs(
                runnable.outputs,
                run_outcome.exit_code,
                captures,
                workspace=workspace,
                log=log,
                is_canceled=is_canceled,
            )
        run_outputs["verdict"] = result.verdict
        run_outputs["outputResults"] = [
            {"sourceKey": r.source_key, "mode": r.mode, "passed": r.passed, "detail": r.detail}
            for r in result.output_results
        ]
        log(
            "system",
            "info" if result.verdict == "pass" else "error",
            f"Verdict: {result.verdict.upper()}",
        )
        status = run_outcome.status
        if status == "succeeded" and result.verdict == "fail":
            status = "failed"
        return ExperimentRunOutcome(status=status, run_outputs=run_outputs)

    # snapshot mode
    if run_outcome.status != "succeeded":
        run_outputs["snapshotApplied"] = False
        log("system", "warn", "Snapshot skipped — command did not exit 0")
        return ExperimentRunOutcome(status=run_outcome.status, run_outputs=run_outputs)

    new_outputs = snapshot_outputs(runnable.outputs, captures)
    run_outputs["snapshotCount"] = len(new_outputs)
    log("system", "info", f"Snapshot captured: {len(new_outputs)} baseline(s) ready")
    return ExperimentRunOutcome(
        status=run_outcome.status,
        run_outputs=run_outputs,
        snapshot_to_persist=new_outputs,
    )
