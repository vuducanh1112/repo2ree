"""Orchestrate a single experiment run from a REE workspace.

Logical core: owns the full run logic — writing the command script, running
it in a Docker sidecar, collecting captured outputs, and computing the verify
verdict or snapshot baselines. Storage concerns (resolving the experiment from
the draft, persisting snapshots) stay in the API layer; run-store logging and
cancellation are injected as callbacks, mirroring ``run_script_in_container``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from repo2ree_core.container.run_script import (
    CancelCheck,
    CONTAINER_WORKSPACE,
    ContainerScriptRun,
    LogSink,
    run_script_in_container,
)
from repo2ree_core.container.runtime_image import loaded_runtime_image
from repo2ree_core.experiment.experiment import (
    CustomMatch,
    ExpectedOutput,
    Experiment,
    FileSource,
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


# ================================================
# Result type
# ================================================


@dataclass
class ExperimentRunOutcome:
    """Result of an experiment run.

    ``run_outputs`` is the serialized payload for the run store.
    ``snapshot_to_persist`` is non-None only for a successful snapshot run, and
    holds the baselines the caller must write back into the REE draft.
    """

    status: str
    run_outputs: dict[str, Any]
    snapshot_to_persist: list[ExpectedOutput] | None = field(default=None)


# ================================================
# Capture bundle
# ================================================


def build_capture_bundle(
    captured_stdout: str,
    captured_stderr: str,
    outputs: list[ExpectedOutput],
    workspace: Path,
) -> CaptureBundle:
    """Collect stdout, stderr, and any declared file outputs into a bundle.

    File sources whose resolved path escapes *workspace* (absolute paths,
    ``..`` traversal) are refused — only files inside the workspace are read.
    """
    workspace = workspace.resolve()
    files: dict[str, bytes] = {}
    for exp_output in outputs:
        src = exp_output.source
        if not isinstance(src, FileSource):
            continue
        candidate = (workspace / src.path).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError:
            continue  # path escapes the workspace — refuse to read
        if candidate.is_file():
            try:
                files[src.path] = candidate.read_bytes()
            except OSError:
                pass

    return CaptureBundle(stdout=captured_stdout, stderr=captured_stderr, files=files)


# ================================================
# Custom match evaluation
# ================================================


def _evaluate_custom_match(
    *,
    match: CustomMatch,
    text: str,
    workspace: Path,
    runtime_image: str,
    run_id: str,
    output_index: int,
    log: LogSink,
    is_canceled: CancelCheck,
) -> tuple[bool, str]:
    """Run the custom validator command inside the experiment runtime image."""
    script_name = f"validator_{run_id}_{output_index}.sh"
    control_dir = workspace / ".workspace"
    control_dir.mkdir(exist_ok=True)
    script_path = control_dir / script_name
    script_rel = f".workspace/{script_name}"
    script_path.write_text(match.value, encoding="utf-8")

    try:
        outcome = run_script_in_container(
            ContainerScriptRun(
                workspace_path=workspace,
                script_rel_path=script_rel,
                container_name=f"repo2ree-experiment-validator-{run_id}-{output_index}",
                image=runtime_image,
                working_dir=CONTAINER_WORKSPACE,
                stdin_text=text,
                login_shell=False,
            ),
            log=log,
            is_canceled=is_canceled,
        )
    except Exception as exc:
        return False, f"custom script error: {exc}"
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass

    if outcome.status == "succeeded":
        return True, "custom script exited 0"
    if outcome.status == "canceled":
        return False, "custom script canceled"
    return False, f"custom script exited {outcome.exit_code}"


def _evaluate_all_outputs(
    outputs: list[ExpectedOutput],
    exit_code: int | None,
    captures: CaptureBundle,
    *,
    workspace: Path,
    runtime_image: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunResult:
    """Evaluate all declared outputs, dispatching custom matches to the shell."""
    output_results: list[OutputResult] = []
    for output_index, expected in enumerate(outputs):
        if isinstance(expected.match, CustomMatch):
            key = source_key(expected.source)
            text = captures.text_for(expected.source)
            if text is None:
                path = (
                    expected.source.path
                    if isinstance(expected.source, FileSource)
                    else "?"
                )
                output_results.append(
                    OutputResult(
                        source_key=key,
                        mode="custom",
                        passed=False,
                        detail=f"file not found: {path!r}",
                    )
                )
            else:
                passed, detail = _evaluate_custom_match(
                    match=expected.match,
                    text=text,
                    workspace=workspace,
                    runtime_image=runtime_image,
                    run_id=run_id,
                    output_index=output_index,
                    log=log,
                    is_canceled=is_canceled,
                )
                output_results.append(
                    OutputResult(
                        source_key=key,
                        mode="custom",
                        passed=passed,
                        detail=detail,
                    )
                )
        else:
            output_results.append(evaluate_output(expected, captures))

    return make_run_result(exit_code, output_results)


# ================================================
# Run orchestration
# ================================================


def run_experiment(
    *,
    workspace: Path,
    experiment: Experiment,
    mode: Literal["verify", "snapshot"],
    runtime_archive_path: Path,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    """Run *experiment*'s command in a sidecar and compute its outcome."""
    workspace = workspace.resolve()

    # Write the experiment command to a temp script inside the control dir.
    control_dir = workspace / ".workspace"
    control_dir.mkdir(exist_ok=True)
    script_name = f"exp_{run_id}.sh"
    script_path = control_dir / script_name
    script_path.write_text(experiment.command, encoding="utf-8")
    script_rel = f".workspace/{script_name}"

    has_file_outputs = any(isinstance(o.source, FileSource) for o in experiment.outputs)

    log("system", "info", f"Starting experiment run {run_id}")
    log("system", "info", f"Experiment: {experiment.name!r}")
    log("system", "info", f"Mode: {mode}")
    log("system", "info", f"Command: {experiment.command}")
    try:
        with loaded_runtime_image(
            runtime_archive_path, run_id=run_id, log=log
        ) as runtime_image:
            spec = ContainerScriptRun(
                workspace_path=workspace,
                script_rel_path=script_rel,
                container_name=f"repo2ree-experiment-{run_id}",
                image=runtime_image,
                working_dir=CONTAINER_WORKSPACE,
                sync_workspace_back=has_file_outputs,
                login_shell=False,
            )

            outcome = run_script_in_container(spec, log=log, is_canceled=is_canceled)

            log(
                "system",
                "info" if outcome.status == "succeeded" else "error",
                f"Container {outcome.status} (exit code {outcome.exit_code})",
            )

            captures = build_capture_bundle(
                outcome.captured_stdout,
                outcome.captured_stderr,
                experiment.outputs,
                workspace,
            )

            run_outputs: dict[str, Any] = {
                "experimentName": experiment.name,
                "mode": mode,
                "exitCode": outcome.exit_code,
                "runtimeImage": runtime_image,
            }

            if mode == "verify":
                if outcome.status == "canceled":
                    return ExperimentRunOutcome(
                        status="canceled", run_outputs=run_outputs
                    )
                result = _evaluate_all_outputs(
                    experiment.outputs,
                    outcome.exit_code,
                    captures,
                    workspace=workspace,
                    runtime_image=runtime_image,
                    run_id=run_id,
                    log=log,
                    is_canceled=is_canceled,
                )
                run_outputs["verdict"] = result.verdict
                run_outputs["outputResults"] = [
                    {
                        "sourceKey": r.source_key,
                        "mode": r.mode,
                        "passed": r.passed,
                        "detail": r.detail,
                    }
                    for r in result.output_results
                ]
                log(
                    "system",
                    "info" if result.verdict == "pass" else "error",
                    f"Experiment verdict: {result.verdict.upper()}",
                )
                status = outcome.status
                if status == "succeeded" and result.verdict == "fail":
                    status = "failed"
                return ExperimentRunOutcome(status=status, run_outputs=run_outputs)

            # snapshot: only record baselines when the command actually succeeded.
            if outcome.status != "succeeded":
                run_outputs["snapshotApplied"] = False
                log("system", "warn", "Snapshot skipped — command did not exit 0")
                return ExperimentRunOutcome(
                    status=outcome.status, run_outputs=run_outputs
                )

            new_outputs = snapshot_outputs(experiment.outputs, captures)
            run_outputs["snapshotCount"] = len(new_outputs)
            log(
                "system",
                "info",
                f"Snapshot captured: {len(new_outputs)} baseline(s) ready",
            )

            return ExperimentRunOutcome(
                status=outcome.status,
                run_outputs=run_outputs,
                snapshot_to_persist=new_outputs,
            )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass
