"""WorkingEnvironment backed by an author-supplied phased driver script.

Used for the ``custom`` runtime entry.  The driver lives at ``enter_script``
(either a single file = exec-only, or a directory with ``pre``/``exec``/``post``
files).  The runner owns capture, cancellation, output sync, and the per-run
command script; the custom script only needs to run ``$R2R_COMMAND`` in the
substrate (exec phase).

ABI environment variables exposed to every phase:

  R2R_WORKSPACE — host path of the materialized workspace
  R2R_COMMAND   — workspace-relative path of the command script
  R2R_RUN_ID    — unique id of this run

Lifecycle:
  __enter__   → run pre script (if present)
  exec_script → run exec script with R2R_* env
  sync_out    → no-op (driver's post phase copies outputs back)
  __exit__    → run post script (if present), always
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from repo2ree_core.container.run_script import format_command, stream_output
from repo2ree_core.working_environment.base import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    StepOutcome,
    WorkingEnvironmentSpec,
)


class ScriptedWorkingEnvironment:
    """WorkingEnvironment driven by author-supplied pre/exec/post scripts."""

    def __init__(self, spec: WorkingEnvironmentSpec) -> None:
        self._workspace = spec.workspace_path.resolve()
        self._run_id = spec.run_id
        self._log = spec.log
        self._is_canceled = spec.is_canceled
        driver = Path(spec.enter_script)
        if driver.is_dir():
            self._pre: Path | None = driver / "pre"
            self._exec: Path = driver / "exec"
            self._post: Path | None = driver / "post"
        else:
            self._pre = None
            self._exec = driver
            self._post = None
        self._provisioned = False

    # ================================================
    # Lifecycle
    # ================================================

    def __enter__(self) -> ScriptedWorkingEnvironment:
        if self._is_canceled and self._is_canceled():
            raise ProvisioningCanceledError("Run canceled before provisioning")
        if self._pre and self._pre.exists():
            outcome = self._run_phase(self._pre, "pre", log=self._log)
            if outcome.status == "failed":
                raise RuntimeError(f"Custom driver pre-phase failed (exit {outcome.exit_code})")
        self._provisioned = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._post and self._post.exists():
            self._run_phase(self._post, "post", log=self._log)

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
        if not self._exec.exists():
            log("system", "error", f"Custom driver exec script not found: {self._exec}")
            return StepOutcome("failed", 1)
        return self._run_phase(self._exec, "exec", log=log, command_rel=step.script_rel_path)

    def put_file(self, rel_path: str, content: str) -> None:
        target = (self._workspace / rel_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def sync_out(self, *, log: LogSink) -> bool:
        # The post phase is responsible for copying outputs back to R2R_WORKSPACE.
        return True

    # ================================================
    # Internals
    # ================================================

    def _run_phase(
        self,
        script: Path,
        phase: str,
        *,
        log: LogSink,
        command_rel: str = "",
    ) -> StepOutcome:
        cmd = ["sh", str(script)]
        env = {
            **os.environ,
            "R2R_WORKSPACE": str(self._workspace),
            "R2R_RUN_ID": self._run_id,
            "R2R_COMMAND": command_rel,
        }
        log("system", "info", f"[custom/{phase}] {format_command(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        stream_output(log, result)
        status = "succeeded" if result.returncode == 0 else "failed"
        return StepOutcome(status, result.returncode, result.stdout or "", result.stderr or "")
