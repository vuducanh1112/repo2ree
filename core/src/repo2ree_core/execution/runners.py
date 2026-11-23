from __future__ import annotations

from pathlib import Path

from repo2ree_core.execution.launch import Launch, launched_command, read_launched
from repo2ree_core.execution.process import CancelCheck, StepOutcome, format_argv, run_streaming_process
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.paths import resolve_within
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import ScriptSpanAttrs, record_command_status, record_span_facts

tracer = get_tracer(__name__)


NOTHING = ("true",)


def run_workspace_script(
    workspace: Path,
    script_rel: str | None,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
    activate_rel: str | None = None,
    launch: Launch | None = None,
) -> StepOutcome:
    workspace = workspace.resolve()
    if script_rel is None and activate_rel is None:
        raise ValueError("nothing to run: no script and no activation")
    with tracer.start_as_current_span("script.run") as span:
        ScriptSpanAttrs(path=script_rel or activate_rel or "").apply(span)
        cmd = list(NOTHING)
        if script_rel is not None:
            script_abs = resolve_within(workspace, script_rel)
            if script_abs is None:
                log("system", "error", f"script escapes workspace: {script_rel}")
                record_span_facts(span, {"script.error": "escapes workspace"})
                return StepOutcome("failed", 1)
            if not script_abs.is_file():
                log("system", "error", f"script not found: {script_rel}")
                record_span_facts(span, {"script.error": "not found"})
                return StepOutcome("failed", 1)
            cmd = ["sh", script_rel]
        if activate_rel is not None:
            activate_abs = resolve_within(workspace, activate_rel)
            if activate_abs is None or not activate_abs.is_file():
                log("system", "error", f"activate experiment environment script not found: {activate_rel}")
                record_span_facts(span, {"script.error": "activate script not found"})
                return StepOutcome("failed", 1)
            cmd = ["sh", activate_rel, *cmd]
        record: Path | None = None
        if launch is not None:
            cmd, record = launched_command(workspace, launch, cmd)
        log("system", "info", f"$ {format_argv(cmd)}")

        result = run_streaming_process(cmd, log=log, cwd=workspace, is_canceled=is_canceled)
        launched = read_launched(record) if record is not None else None
        if launched is not None:
            where = f"{launched.node}" + (f", Slurm job {launched.slurm_job_id}" if launched.slurm_job_id else "")
            log("system", "info", f"launched on {where}")

        if result.canceled or is_canceled():
            status: ActionStatus = "canceled"
        else:
            status = "succeeded" if result.returncode == 0 else "failed"
        record_command_status(span, status)
        return StepOutcome(status, result.returncode, result.stdout, result.stderr, launched)
