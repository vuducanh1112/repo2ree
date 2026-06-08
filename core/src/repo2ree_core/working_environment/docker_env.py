"""Docker-container implementation of WorkingEnvironment.

The container is created and started in ``__enter__``; the host workspace is
copied in at that point.  ``exec_script`` runs scripts via ``docker exec``
against the already-running container — no create/rm per call.  ``put_file``
injects a file directly into the container without a full re-sync.
``sync_out`` copies the container workspace back to the host.  ``__exit__``
removes the container unconditionally.

Low-level Docker CLI plumbing (``build_exec_command``, ``CONTAINER_WORKSPACE``)
is imported from ``container.run_script``; this module owns the lifecycle.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from repo2ree_core.container.run_script import (
    CONTAINER_WORKSPACE,
    build_exec_command,
    format_command,
    stream_output,
)
from repo2ree_core.working_environment.base import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    StepOutcome,
    WorkingEnvironmentSpec,
)


# ================================================
# Helpers
# ================================================

_DEFAULT_IMAGE = "docker:latest"


# ================================================
# Implementation
# ================================================


class DockerWorkingEnvironment:
    """WorkingEnvironment backed by a single Docker container.

    Lifecycle:
      __enter__   → docker create + docker cp (in) + docker start
      exec_script → docker exec  (repeated; container stays running)
      put_file    → docker exec cat >  (inject a file without full re-sync)
      sync_out    → docker cp (out)    (explicit; caller decides when)
      __exit__    → docker rm -f       (always, even on error)
    """

    def __init__(self, spec: WorkingEnvironmentSpec) -> None:
        self._workspace = spec.workspace_path.resolve()
        self._image = spec.image or _DEFAULT_IMAGE
        self._name = f"repo2ree-we-{spec.run_id}"
        self._log = spec.log
        self._is_canceled = spec.is_canceled
        self._docker = shutil.which("docker") or "docker"
        self._created = False

    # ================================================
    # Lifecycle
    # ================================================

    def __enter__(self) -> DockerWorkingEnvironment:
        self._check_canceled("Run canceled before provisioning")
        self._create()
        self._check_canceled("Run canceled during provisioning")
        self._cp_in()
        self._check_canceled("Run canceled during provisioning")
        self._start()
        self._check_canceled("Run canceled during provisioning")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self._destroy()

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
        """Run *step* inside the container via ``docker exec``.

        The container must already be running (i.e. called after __enter__).
        The script is located by *step.script_rel_path* relative to the
        workspace root inside the container — it must already exist there,
        either from the initial cp-in or from a prior ``put_file`` call.
        """
        if is_canceled():
            log("system", "warn", "Run canceled before exec")
            return StepOutcome("canceled")

        script_abs = self._resolve_workspace_path(
            step.script_rel_path,
            error_label="Script path",
        )
        script_in_container = CONTAINER_WORKSPACE / script_abs.relative_to(
            self._workspace
        )
        working_dir: Path | None = None
        if step.working_dir_rel is not None:
            working_dir_abs = self._resolve_workspace_path(
                step.working_dir_rel,
                error_label="Working directory path",
            )
            working_dir = CONTAINER_WORKSPACE / working_dir_abs.relative_to(
                self._workspace
            )

        exec_command = build_exec_command(
            script_in_container,
            step.script_rel_path,
            step.echo_label,
            working_dir,
        )
        sh_flag = "-lc" if step.login_shell else "-c"
        cmd = [
            self._docker,
            "exec",
            *([] if step.stdin_text is None else ["-i"]),
            self._name,
            "sh",
            sh_flag,
            exec_command,
        ]
        log("system", "info", format_command(cmd))
        result = subprocess.run(
            cmd, capture_output=True, text=True, input=step.stdin_text
        )
        stream_output(log, result)

        if is_canceled():
            outcome = StepOutcome(
                "canceled", result.returncode, result.stdout or "", result.stderr or ""
            )
        else:
            status: Literal["succeeded", "failed"] = (
                "succeeded" if result.returncode == 0 else "failed"
            )
            outcome = StepOutcome(
                status, result.returncode, result.stdout or "", result.stderr or ""
            )
        return outcome

    def put_file(self, rel_path: str, content: str) -> None:
        """Write *content* directly into the running container at *rel_path*.

        The path is relative to the workspace root inside the container.
        Parent directories are created automatically.  This is the lightweight
        alternative to a full ``sync_out`` + file-edit + ``sync_in`` cycle,
        used for injecting short-lived scripts (e.g. experiment validators).
        """
        target_abs = self._resolve_workspace_path(rel_path, error_label="File path")
        target_rel = target_abs.relative_to(self._workspace)
        container_path = str(CONTAINER_WORKSPACE / target_rel)
        parent = target_rel.parent
        if parent != Path("."):
            mkdir_cmd = [
                self._docker,
                "exec",
                self._name,
                "mkdir",
                "-p",
                str(CONTAINER_WORKSPACE / parent.as_posix()),
            ]
            self._log("system", "info", format_command(mkdir_cmd))
            mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True)
            if mkdir_result.returncode != 0:
                raise RuntimeError(
                    f"put_file mkdir failed for {rel_path!r}: {mkdir_result.stderr.strip()}"
                )
        cmd = [
            self._docker,
            "exec",
            "-i",
            self._name,
            "sh",
            "-c",
            f"cat > {shlex.quote(container_path)}",
        ]
        result = subprocess.run(cmd, input=content, text=True, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"put_file failed for {rel_path!r}: {result.stderr.strip()}"
            )

    def sync_out(self, *, log: LogSink) -> bool:
        """Copy the container workspace back to the host.

        Returns True on success, False on failure (error is logged).
        """
        cmd = [
            self._docker,
            "cp",
            f"{self._name}:{CONTAINER_WORKSPACE}/.",
            str(self._workspace),
        ]
        log("system", "info", "Syncing container workspace to host")
        log("system", "info", format_command(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        stream_output(log, result)
        if result.returncode != 0:
            log("system", "error", "Failed to sync workspace from container")
            ok = False
        else:
            log("system", "info", "Sync complete")
            ok = True
        return ok

    # ================================================
    # Internals
    # ================================================

    def _create(self) -> None:
        cmd = [
            self._docker,
            "create",
            "--name",
            self._name,
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            self._image,
            "sleep",
            "infinity",
        ]
        self._log("system", "info", format_command(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        stream_output(self._log, result)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker create failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        self._created = True

    def _cp_in(self) -> None:
        cmd = [
            self._docker,
            "cp",
            f"{self._workspace}/.",
            f"{self._name}:{CONTAINER_WORKSPACE}",
        ]
        self._log("system", "info", format_command(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        stream_output(self._log, result)
        if result.returncode != 0:
            self._destroy()
            raise RuntimeError(
                f"docker cp (in) failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )

    def _start(self) -> None:
        cmd = [self._docker, "start", self._name]
        self._log("system", "info", format_command(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        stream_output(self._log, result)
        if result.returncode != 0:
            self._destroy()
            raise RuntimeError(
                f"docker start failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )

    def _destroy(self) -> None:
        if not self._created:
            return
        try:
            subprocess.run(
                [self._docker, "rm", "-f", self._name],
                capture_output=True,
                text=True,
            )
        except OSError:
            pass
        self._created = False

    def _resolve_workspace_path(self, rel_path: str, *, error_label: str) -> Path:
        candidate = (self._workspace / rel_path).resolve()
        try:
            candidate.relative_to(self._workspace)
        except ValueError as exc:
            raise ValueError(f"{error_label} escapes workspace: {rel_path!r}") from exc
        return candidate

    def _check_canceled(self, message: str) -> None:
        if self._is_canceled is None or not self._is_canceled():
            return
        self._log("system", "warn", message)
        self._destroy()
        raise ProvisioningCanceledError(message)
