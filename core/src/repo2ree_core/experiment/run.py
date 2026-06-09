"""Orchestrate a single experiment run from a REE workspace.

Logical core: owns the full run logic — writing the command script, running
it in a Working Environment, collecting captured outputs, and computing the
verify verdict or snapshot baselines.  Storage concerns (resolving the
experiment from the draft, persisting snapshots) stay in the API layer;
run-store logging and cancellation are injected as callbacks.

One WorkingEnvironment is provisioned per run and shared across the command
execution and all custom-validator steps.  This means a single docker cp in
and out rather than one container per script invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from repo2ree_core.container.runtime_image import loaded_runtime_image
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
    Experiment,
    FileSource,
)
from repo2ree_core.working_environment import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    WorkingEnvironment,
    acquire,
)

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
            continue
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
    we: WorkingEnvironment,
    run_id: str,
    output_index: int,
    log: LogSink,
    is_canceled: CancelCheck,
) -> tuple[bool, str]:
    """Run the custom validator inside the experiment's WorkingEnvironment.

    The validator script is injected directly into the running environment via
    ``put_file``; no new container is created per validator.
    """
    script_rel = f".workspace/validator_{run_id}_{output_index}.sh"
    try:
        we.put_file(script_rel, match.value)
    except Exception as exc:
        return False, f"custom script setup error: {exc}"

    try:
        outcome = we.exec_script(
            ScriptStep(
                script_rel_path=script_rel,
                working_dir_rel="",
                stdin_text=text,
                login_shell=False,
            ),
            log=log,
            is_canceled=is_canceled,
        )
    except Exception as exc:
        return False, f"custom script error: {exc}"

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
    we: WorkingEnvironment,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunResult:
    """Evaluate all declared outputs, dispatching custom matches to the WE."""
    output_results: list[OutputResult] = []
    for output_index, expected in enumerate(outputs):
        if isinstance(expected.match, CustomMatch):
            key = source_key(expected.source)
            text = captures.text_for(expected.source)
            if text is None:
                path = expected.source.path if isinstance(expected.source, FileSource) else "?"
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
                    we=we,
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
    """Run *experiment*'s command in a WorkingEnvironment and compute its outcome.

    One environment is provisioned for the full run: workspace is copied in
    once, the command executes, file outputs are optionally synced back, and
    all custom validators share the same running container before teardown.
    """
    workspace = workspace.resolve()

    # Write the command script to the host workspace so it is included in the
    # initial cp-in when the WorkingEnvironment is provisioned.
    control_dir = workspace / ".workspace"
    control_dir_created = not control_dir.exists()
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
        with loaded_runtime_image(runtime_archive_path, run_id=run_id, log=log) as runtime_image:
            try:
                with acquire(
                    workspace,
                    run_id,
                    log=log,
                    is_canceled=is_canceled,
                    image=runtime_image,
                ) as we:
                    cmd_outcome = we.exec_script(
                        ScriptStep(
                            script_rel_path=script_rel,
                            working_dir_rel="",
                            login_shell=False,
                        ),
                        log=log,
                        is_canceled=is_canceled,
                    )

                    log(
                        "system",
                        "info" if cmd_outcome.status == "succeeded" else "error",
                        f"Container {cmd_outcome.status} (exit code {cmd_outcome.exit_code})",
                    )

                    # Sync file outputs back to host so build_capture_bundle can read them.
                    if has_file_outputs and cmd_outcome.status == "succeeded":
                        if not we.sync_out(log=log):
                            return ExperimentRunOutcome(
                                status="failed",
                                run_outputs={
                                    "experimentName": experiment.name,
                                    "mode": mode,
                                    "exitCode": cmd_outcome.exit_code,
                                    "runtimeImage": runtime_image,
                                },
                            )

                    captures = build_capture_bundle(
                        cmd_outcome.captured_stdout,
                        cmd_outcome.captured_stderr,
                        experiment.outputs,
                        workspace,
                    )

                    run_outputs: dict[str, Any] = {
                        "experimentName": experiment.name,
                        "mode": mode,
                        "exitCode": cmd_outcome.exit_code,
                        "runtimeImage": runtime_image,
                    }

                    if mode == "verify":
                        if cmd_outcome.status == "canceled":
                            return ExperimentRunOutcome(status="canceled", run_outputs=run_outputs)
                        result = _evaluate_all_outputs(
                            experiment.outputs,
                            cmd_outcome.exit_code,
                            captures,
                            we=we,
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
                        status = cmd_outcome.status
                        if status == "succeeded" and result.verdict == "fail":
                            status = "failed"
                        return ExperimentRunOutcome(status=status, run_outputs=run_outputs)

                    # snapshot: only record baselines when the command succeeded.
                    if cmd_outcome.status != "succeeded":
                        run_outputs["snapshotApplied"] = False
                        log(
                            "system",
                            "warn",
                            "Snapshot skipped — command did not exit 0",
                        )
                        return ExperimentRunOutcome(status=cmd_outcome.status, run_outputs=run_outputs)

                    new_outputs = snapshot_outputs(experiment.outputs, captures)
                    run_outputs["snapshotCount"] = len(new_outputs)
                    log(
                        "system",
                        "info",
                        f"Snapshot captured: {len(new_outputs)} baseline(s) ready",
                    )
                    return ExperimentRunOutcome(
                        status=cmd_outcome.status,
                        run_outputs=run_outputs,
                        snapshot_to_persist=new_outputs,
                    )
            except ProvisioningCanceledError:
                return ExperimentRunOutcome(
                    status="canceled",
                    run_outputs={
                        "experimentName": experiment.name,
                        "mode": mode,
                        "exitCode": None,
                        "runtimeImage": runtime_image,
                    },
                )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass
        if control_dir_created:
            try:
                control_dir.rmdir()  # only removes if empty; safe to attempt
            except OSError:
                pass
