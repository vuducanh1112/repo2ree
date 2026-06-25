"""Orchestrate a single experiment run from a REE workspace.

Logical core: owns the full run logic — writing the command script, running
it in a Working Environment, collecting captured outputs, and computing the
verify verdict or snapshot baselines.  Storage concerns (resolving the
experiment from the draft, persisting snapshots) stay in the API layer;
run-store logging and cancellation are injected as callbacks.

One WorkingEnvironment is provisioned per run and shared across the command
execution and all custom-validator steps.  This means a single docker cp in
and out rather than one container per script invocation.

File outputs are asserted and snapshotted inside the running environment via
``exec_script`` (``sha256sum`` / ``cat``), so the container filesystem is never
synced back to the host solely for verification.  Absolute paths (e.g.
``/results/foo.png``) and workspace-relative paths both work because the shell
changes to the workspace directory before each script is sourced.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from repo2ree_core.container.runtime_image import loaded_runtime_image
from repo2ree_core.domain.env_entry import ContainerEntry, EnvEntry, LocalEntry
from repo2ree_core.experiment.evaluate import (
    CaptureBundle,
    ExperimentRunResult,
    OutputResult,
    evaluate_match,
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
    Sha256Match,
)
from repo2ree_core.working_environment import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    WorkingEnvironment,
    acquire,
)
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

    status: str
    run_outputs: dict[str, Any]
    snapshot_to_persist: list[ExpectedOutput] | None = field(default=None)


# ================================================
# Capture bundle
# ================================================


def build_capture_bundle(
    captured_stdout: str,
    captured_stderr: str,
) -> CaptureBundle:
    """Collect stdout and stderr into a bundle.

    File outputs are evaluated directly inside the running environment via
    ``exec_script``, so no host filesystem read is needed here.
    """
    return CaptureBundle(stdout=captured_stdout, stderr=captured_stderr)


# ================================================
# In-runtime file evaluation
# ================================================


def _file_check_script(path: str, mode: str) -> str:
    """Shell one-liner that projects *path* inside the running environment.

    sha256 mode: emits ``<hex>  <path>`` via ``sha256sum``.
    All other modes: emits the raw file bytes via ``cat``.

    The scripts run from the workspace directory (WorkingEnvironment sets
    ``working_dir_rel=""``), so relative paths resolve against the workspace;
    absolute paths like ``/results/foo.png`` are used as-is.
    """
    quoted = shlex.quote(path)
    if mode == "sha256":
        return f"sha256sum {quoted}"
    return f"cat {quoted}"


def _evaluate_file_output_in_container(
    expected: ExpectedOutput,
    *,
    we: WorkingEnvironment,
    run_id: str,
    output_index: int,
    log: LogSink,
    is_canceled: CancelCheck,
) -> OutputResult:
    """Evaluate *expected* (a FileSource output) inside the running environment.

    The file is read at its declared path — workspace-relative or absolute
    container path — without syncing the container filesystem to the host.
    For ``sha256`` mode only ``sha256sum`` output (64 hex chars) is captured,
    so large binary files are never transferred through the capture pipe.
    """
    src = expected.source
    if not isinstance(src, FileSource):
        return OutputResult(
            source_key=source_key(src), mode=expected.match.mode, passed=False, detail="not a file source"
        )
    key = source_key(src)
    mode = expected.match.mode
    script_rel = f".workspace/chk_{run_id}_{output_index}.sh"

    try:
        we.put_file(script_rel, _file_check_script(src.path, mode))
    except Exception as exc:
        return OutputResult(source_key=key, mode=mode, passed=False, detail=f"setup error: {exc}")

    outcome = we.exec_script(
        ScriptStep(script_rel_path=script_rel, working_dir_rel="", login_shell=False),
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status != "succeeded":
        return OutputResult(source_key=key, mode=mode, passed=False, detail=f"file not found: {src.path!r}")

    if mode == "sha256":
        # sha256sum output: "<hex>  <filename>" — take just the digest.
        actual_hash = outcome.captured_stdout.split()[0] if outcome.captured_stdout.strip() else ""
        expected_hash = expected.match.value  # type: ignore[union-attr]
        if actual_hash == expected_hash:
            return OutputResult(source_key=key, mode=mode, passed=True, detail=f"sha256 matched ({actual_hash[:12]}…)")
        return OutputResult(
            source_key=key,
            mode=mode,
            passed=False,
            detail=f"sha256 mismatch: got {actual_hash[:12]}…, expected {expected_hash[:12]}…",
        )

    text = outcome.captured_stdout

    if isinstance(expected.match, CustomMatch):
        passed, detail = _evaluate_custom_match(
            match=expected.match,
            text=text,
            we=we,
            run_id=run_id,
            output_index=output_index,
            log=log,
            is_canceled=is_canceled,
        )
        return OutputResult(source_key=key, mode=mode, passed=passed, detail=detail)

    passed, detail = evaluate_match(expected.match, text, None)
    return OutputResult(source_key=key, mode=mode, passed=passed, detail=detail)


def _snapshot_file_outputs_in_container(
    file_outputs: list[ExpectedOutput],
    *,
    we: WorkingEnvironment,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> list[ExpectedOutput]:
    """Record sha256 baselines for file outputs by hashing inside the running environment.

    Non-sha256 file outputs are preserved unchanged.  File outputs whose source
    cannot be read (exec fails) are dropped — cannot snapshot what isn't there.
    """
    result: list[ExpectedOutput] = []
    for idx, expected in enumerate(file_outputs):
        if expected.match.mode != "sha256":
            result.append(expected)
            continue
        src = expected.source
        if not isinstance(src, FileSource):
            continue
        script_rel = f".workspace/snap_{run_id}_{idx}.sh"
        try:
            we.put_file(script_rel, _file_check_script(src.path, "sha256"))
        except Exception as exc:
            log("system", "warn", f"snapshot: could not inject check script for {src.path!r}: {exc}")
            continue
        outcome = we.exec_script(
            ScriptStep(script_rel_path=script_rel, working_dir_rel="", login_shell=False),
            log=log,
            is_canceled=is_canceled,
        )
        if outcome.status != "succeeded":
            continue
        actual_hash = outcome.captured_stdout.split()[0] if outcome.captured_stdout.strip() else ""
        if not actual_hash:
            continue
        result.append(ExpectedOutput(source=src, match=Sha256Match(mode="sha256", value=actual_hash)))
    return result


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
        if isinstance(expected.source, FileSource):
            # File outputs are evaluated inside the running environment so they
            # work for both workspace-relative and absolute container paths
            # (e.g. /results/foo.png) without a sync_out round-trip.
            output_results.append(
                _evaluate_file_output_in_container(
                    expected,
                    we=we,
                    run_id=run_id,
                    output_index=output_index,
                    log=log,
                    is_canceled=is_canceled,
                )
            )
        elif isinstance(expected.match, CustomMatch):
            key = source_key(expected.source)
            text = captures.text_for(expected.source)
            if text is None:
                output_results.append(
                    OutputResult(
                        source_key=key,
                        mode="custom",
                        passed=False,
                        detail="source not found",
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


def _workbench_shares_image_cache() -> bool:
    """True when the workbench talks to a Docker daemon whose image cache is
    shared across runs (host-socket mode), so a loaded base image should be
    preserved for reuse rather than removed after the run.

    The workbench's substrate mode is propagated into the container as an env
    var by the supervisor; this is the boundary where it is read.
    """
    return os.environ.get("WORKBENCH_DOCKER_MODE") == "host-socket"


@contextmanager
def _entered_environment(
    entry: EnvEntry,
    *,
    workspace: Path,
    runtime_archive_path: Path | None,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> Iterator[tuple[WorkingEnvironment, str]]:
    """Provision the WorkingEnvironment for *entry* and yield ``(we, descriptor)``.

    ``descriptor`` names the substrate that hosted the run (the loaded image tag
    for Docker, or the entry kind otherwise) for the run record.

    Docker is the only substrate that materializes the runtime artifact (loading
    the image tarball); the others enter the runtime in place.
    """
    if isinstance(entry, ContainerEntry):
        if runtime_archive_path is None:
            raise ValueError("Container entry requires a built runtime artifact")
        with loaded_runtime_image(
            runtime_archive_path,
            run_id=run_id,
            log=log,
            preserve_base_image=_workbench_shares_image_cache(),
        ) as runtime_image:
            with acquire(
                workspace,
                run_id,
                log=log,
                is_canceled=is_canceled,
                image=runtime_image,
                entry=entry,
            ) as we:
                yield we, runtime_image
    else:
        with acquire(
            workspace,
            run_id,
            log=log,
            is_canceled=is_canceled,
            entry=entry,
        ) as we:
            yield we, entry.kind


def _builtin_overrides(entry: EnvEntry) -> tuple[str, str, str]:
    """``(provision, exec, teardown)`` override script paths for a built-in preset.

    Only ``container``/``local`` presets layer overrides onto preset-provided
    infrastructure (create/start/rm, native shell). ``custom`` expresses its
    phases through its own driver (``ScriptedWorkingEnvironment``); ``vm`` is not
    implemented. For those, no overrides apply here.
    """
    if not isinstance(entry, ContainerEntry | LocalEntry):
        return "", "", ""
    ov = entry.overrides
    return ov.provision.strip(), ov.exec.strip(), ov.teardown.strip()


def _run_in_environment(
    we: WorkingEnvironment,
    runtime_image: str,
    *,
    runnable: Runnable,
    label: str,
    mode: Literal["verify", "snapshot"],
    script_rel: str,
    run_id: str,
    overrides: tuple[str, str, str],
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    """Run provision-hook → command → evaluate/snapshot inside a live environment.

    ``overrides`` is ``(provision, exec, teardown)``. The provision hook runs
    in-substrate before the command; the exec override dispatches the per-run
    command (handed the ``R2R_COMMAND`` / ``R2R_RUN_ID`` ABI) in place of the
    default invocation; the teardown hook runs in-substrate in a ``finally`` so
    it executes before the environment is torn down, even on early return.
    """
    provision_override, exec_override, teardown_override = overrides
    base_outputs: dict[str, Any] = {
        "subjectName": label,
        "mode": mode,
        "substrate": runtime_image,
    }
    try:
        # Provision override: in-substrate setup after the runtime is up. A
        # failure aborts the run (the command would run against a half-set-up
        # substrate); teardown still runs via the finally below.
        if provision_override:
            with tracer.start_as_current_span("experiment.provision_override"):
                prov = we.exec_script(
                    ScriptStep(script_rel_path=provision_override, working_dir_rel="", login_shell=False),
                    log=log,
                    is_canceled=is_canceled,
                )
            if prov.status != "succeeded":
                log("system", "error", f"Provision override {prov.status} (exit {prov.exit_code})")
                status = "canceled" if prov.status == "canceled" else "failed"
                return ExperimentRunOutcome(status=status, run_outputs={**base_outputs, "exitCode": prov.exit_code})

        if exec_override:
            # The override is a dispatcher: it runs $R2R_COMMAND its own way.
            command_step = ScriptStep(
                script_rel_path=exec_override,
                working_dir_rel="",
                login_shell=False,
                env={"R2R_COMMAND": script_rel, "R2R_RUN_ID": run_id},
            )
        else:
            command_step = ScriptStep(script_rel_path=script_rel, working_dir_rel="", login_shell=False)

        with tracer.start_as_current_span("experiment.exec_command"):
            cmd_outcome = we.exec_script(command_step, log=log, is_canceled=is_canceled)

        log(
            "system",
            "info" if cmd_outcome.status == "succeeded" else "error",
            f"Environment {cmd_outcome.status} (exit code {cmd_outcome.exit_code})",
        )

        captures = build_capture_bundle(cmd_outcome.captured_stdout, cmd_outcome.captured_stderr)
        run_outputs: dict[str, Any] = {**base_outputs, "exitCode": cmd_outcome.exit_code}

        if mode == "verify":
            if cmd_outcome.status == "canceled":
                return ExperimentRunOutcome(status="canceled", run_outputs=run_outputs)
            with tracer.start_as_current_span("experiment.evaluate"):
                result = _evaluate_all_outputs(
                    runnable.outputs,
                    cmd_outcome.exit_code,
                    captures,
                    we=we,
                    run_id=run_id,
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
            status = cmd_outcome.status
            if status == "succeeded" and result.verdict == "fail":
                status = "failed"
            return ExperimentRunOutcome(status=status, run_outputs=run_outputs)

        # snapshot: only record baselines when the command succeeded.
        if cmd_outcome.status != "succeeded":
            run_outputs["snapshotApplied"] = False
            log("system", "warn", "Snapshot skipped — command did not exit 0")
            return ExperimentRunOutcome(status=cmd_outcome.status, run_outputs=run_outputs)

        # Snapshot stream outputs (stdout/stderr) via the pure function; snapshot
        # file outputs via in-runtime sha256sum so absolute container paths
        # (e.g. /results/*.png) are captured correctly.
        stream_outputs = [o for o in runnable.outputs if not isinstance(o.source, FileSource)]
        file_outputs = [o for o in runnable.outputs if isinstance(o.source, FileSource)]
        new_outputs = snapshot_outputs(stream_outputs, captures)
        new_outputs.extend(
            _snapshot_file_outputs_in_container(file_outputs, we=we, run_id=run_id, log=log, is_canceled=is_canceled)
        )
        run_outputs["snapshotCount"] = len(new_outputs)
        log("system", "info", f"Snapshot captured: {len(new_outputs)} baseline(s) ready")
        return ExperimentRunOutcome(
            status=cmd_outcome.status,
            run_outputs=run_outputs,
            snapshot_to_persist=new_outputs,
        )
    finally:
        # Teardown override: in-substrate cleanup before the environment is torn
        # down. Best-effort and uncancelable so it runs even on failure/cancel.
        if teardown_override:
            with tracer.start_as_current_span("experiment.teardown_override"):
                td = we.exec_script(
                    ScriptStep(script_rel_path=teardown_override, working_dir_rel="", login_shell=False),
                    log=log,
                    is_canceled=lambda: False,
                )
            if td.status != "succeeded":
                log("system", "warn", f"Teardown override exited {td.exit_code}")


def run_runnable(
    *,
    workspace: Path,
    runnable: Runnable,
    label: str,
    mode: Literal["verify", "snapshot"],
    entry: EnvEntry,
    runtime_archive_path: Path | None,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentRunOutcome:
    """Run *runnable*'s command through *entry* and compute its outcome.

    Shared by experiments and activation — both are :class:`Runnable`, both
    enter the runtime through the same :class:`EnvEntry`. One environment is
    provisioned for the full run: workspace is copied in once, the command
    executes, all declared outputs are verified or snapshotted inside the
    running environment, and the environment is torn down.

    File outputs (including those at absolute container paths such as
    ``/results/foo.png``) are asserted via in-runtime ``exec_script`` calls;
    no ``sync_out`` is needed for verification or snapshotting.
    """
    workspace = workspace.resolve()

    # Write the command script to the host workspace so it is included in the
    # initial cp-in when the WorkingEnvironment is provisioned.
    control_dir = workspace / ".workspace"
    control_dir_created = not control_dir.exists()
    control_dir.mkdir(exist_ok=True)
    script_name = f"exp_{run_id}.sh"
    script_path = control_dir / script_name
    script_path.write_text(runnable.command, encoding="utf-8")
    script_rel = f".workspace/{script_name}"

    log("system", "info", f"Starting run {run_id}")
    log("system", "info", f"Subject: {label!r}")
    log("system", "info", f"Substrate: {entry.kind}")
    log("system", "info", f"Mode: {mode}")
    log("system", "info", f"Command: {runnable.command}")

    try:
        try:
            with _entered_environment(
                entry,
                workspace=workspace,
                runtime_archive_path=runtime_archive_path,
                run_id=run_id,
                log=log,
                is_canceled=is_canceled,
            ) as (we, runtime_image):
                return _run_in_environment(
                    we,
                    runtime_image,
                    runnable=runnable,
                    label=label,
                    mode=mode,
                    script_rel=script_rel,
                    run_id=run_id,
                    overrides=_builtin_overrides(entry),
                    log=log,
                    is_canceled=is_canceled,
                )
        except ProvisioningCanceledError:
            return ExperimentRunOutcome(
                status="canceled",
                run_outputs={
                    "subjectName": label,
                    "mode": mode,
                    "exitCode": None,
                    "substrate": None,
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
