"""WorkingEnvironment that runs in the workbench itself — no nested isolation.

Used for the ``native`` runtime entry: the runtime *is* the workbench, plus
an optional environment that has to be sourced first (e.g. a virtualenv). The
host workspace is the environment, so there is no cp-in/out and ``sync_out`` is
a no-op; ``put_file`` writes straight to the workspace on disk.

Implements the same :class:`WorkingEnvironment` protocol as
:class:`~repo2ree_core.working_environment.docker_env.DockerWorkingEnvironment`
so the runner is identical across substrates.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.container.run_script import format_command, run_streaming_process
from repo2ree_core.working_environment.base import (
    CancelCheck,
    LogSink,
    ScriptStep,
    StepOutcome,
    WorkingEnvironmentSpec,
)
from repo2ree_core.working_environment.command_plan import native_exec_argv, native_shell_command


class NativeWorkingEnvironment:
    """WorkingEnvironment backed directly by the workbench filesystem."""

    def __init__(self, spec: WorkingEnvironmentSpec) -> None:
        self._workspace = spec.workspace_path.resolve()
        self._activate = spec.activate.strip()
        self._log = spec.log
        self._is_canceled = spec.is_canceled

    # ================================================
    # Lifecycle
    # ================================================

    def __enter__(self) -> NativeWorkingEnvironment:
        if self._is_canceled and self._is_canceled():
            from repo2ree_core.working_environment.base import ProvisioningCanceledError

            raise ProvisioningCanceledError("Run canceled before provisioning")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        return None

    # ================================================
    # Public API
    # ================================================

    def exec_script(
        self,
        step: ScriptStep,
        *,
        log: LogSink,
        is_canceled: CancelCheck,
    ) -> StepOutcome:
        if is_canceled():
            log("system", "warn", "Run canceled before exec")
            return StepOutcome("canceled")

        script_abs = self._resolve(step.script_rel_path)
        if step.working_dir_rel is None:
            working_dir = script_abs.parent
        elif step.working_dir_rel == "":
            working_dir = self._workspace
        else:
            working_dir = self._resolve(step.working_dir_rel)

        shell_command = native_shell_command(
            activate=self._activate,
            working_dir=str(working_dir),
            script_abs=str(script_abs),
            echo_label=step.echo_label,
            script_rel=step.script_rel_path,
            env=step.env,
        )
        cmd = native_exec_argv(shell_command, login_shell=step.login_shell)
        log("system", "info", format_command(cmd))
        result = run_streaming_process(
            cmd,
            log=log,
            stdin_text=step.stdin_text,
            is_canceled=is_canceled,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.canceled or is_canceled():
            return StepOutcome("canceled", result.returncode, stdout, stderr)
        status = "succeeded" if result.returncode == 0 else "failed"
        return StepOutcome(status, result.returncode, stdout, stderr)

    def put_file(self, rel_path: str, content: str) -> None:
        target = self._resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def sync_out(self, *, log: LogSink) -> bool:
        # The workspace is already on the host — nothing to copy back.
        return True

    # ================================================
    # Internals
    # ================================================

    def _resolve(self, rel_path: str) -> Path:
        candidate = (self._workspace / rel_path).resolve()
        candidate.relative_to(self._workspace)  # raises ValueError on escape
        return candidate
