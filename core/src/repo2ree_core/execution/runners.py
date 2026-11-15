"""How a step runs one of the REE's scripts: launched, entered into the working environment, and activated.

The command is composed outside in: the REE's launch (a scheduler, or nothing), the recorder of where the launch put
it, the entry into the working environment (``working_environment.Entry``), the activation, and the script. It runs
from the workspace, as a process of this one, so a launch places a job and the job enters the image where it landed.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.execution.launch import Launch, launched_command, read_launched
from repo2ree_core.execution.process import CancelCheck, StepOutcome, format_argv
from repo2ree_core.execution.working_environment import Entry, WorkingEnvironmentUnavailableError, run_in
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.paths import resolve_within
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import ScriptSpanAttrs, record_command_status, record_span_facts

tracer = get_tracer(__name__)


# What the activation runs inside the experiment environment when it is tested alone: a command that does
# nothing, so the run shows only that the activation enters the environment and hands over. It takes no
# options, because an activation may hand its command to a tool that parses on past the command (srun does).
NOTHING = ("true",)


def run_workspace_script(
    workspace: Path,
    script_rel: str | None,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
    entry: Entry,
    activate_rel: str | None = None,
    launch: Launch | None = None,
) -> StepOutcome:
    """Run a workspace-relative script under ``sh`` from the workspace root.

    The single execution path shared by the lifecycle runner
    (``experiment/run.py``) and the build/activation/check handlers: the script
    runs in the REE's working environment, through its launch when it declares
    one. Running from the workspace root lets authors reference
    project files by their workspace-relative paths regardless of where REE keeps
    its own scripts; wrapper scripts are POSIX ``sh`` while project scripts that
    need bash or their own directory (e.g. ``docker build .``) invoke it
    explicitly. Scripts that resolve outside the workspace are rejected.

    With no ``script_rel`` the activation runs alone, around a command that does nothing. With a ``launch``, the
    whole command runs through the REE's launch script, and the outcome says where the launch put it.
    """
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
        try:
            entry.prepare(log)
            cmd = entry.command(workspace, cmd)
        except WorkingEnvironmentUnavailableError as error:
            log("system", "error", str(error))
            record_span_facts(span, {"script.error": "working environment unavailable"})
            return StepOutcome("failed", 1)
        record: Path | None = None
        if launch is not None:
            cmd, record = launched_command(workspace, launch, cmd)
        log("system", "info", f"$ {format_argv(cmd)}")

        result = run_in(entry, workspace, cmd, log=log, is_canceled=is_canceled)
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
