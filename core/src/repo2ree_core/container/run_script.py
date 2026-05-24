"""Run a shell script inside a throwaway Docker sidecar container.

Imperative shell: shells out to the Docker CLI. The sidecar runs the
``docker:latest`` image with the host Docker socket mounted, so the
executed script may itself invoke Docker. The caller's workspace tree is
copied in with ``docker cp``; optionally the whole workspace is copied
back out after a successful run.

Web-framework and run-store concerns are kept out of this module:
progress logging and cancellation are injected as callbacks, and the
function returns a plain :class:`ContainerRunOutcome` rather than raising
HTTP errors.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

# (stream, level, message) -> None. Mirrors the run-log signature.
LogSink = Callable[[str, str, str], None]
# Returns True once a cancel has been requested for the current run.
CancelCheck = Callable[[], bool]

DEFAULT_IMAGE = "docker:latest"
CONTAINER_WORKSPACE = Path("/workspace")


@dataclass(frozen=True)
class ContainerScriptRun:
    """Description of a single in-container script execution.

    ``echo_label`` controls whether the script is echoed before it runs:
    when set, a ``--- <label> (path) ---`` banner plus a ``cat`` of the
    script is emitted (the build/activation behaviour). When ``None`` the
    script runs without being printed.
    """

    workspace_path: Path
    script_rel_path: str
    container_name: str
    image: str = DEFAULT_IMAGE
    echo_label: str | None = None
    sync_workspace_back: bool = False


@dataclass(frozen=True)
class ContainerRunOutcome:
    """Result of a container run.

    ``status`` is one of ``"succeeded"``, ``"failed"`` or ``"canceled"``.
    ``exit_code`` is the return code of the step that determined the
    outcome, or ``None`` when no command was run (e.g. canceled upfront).
    """

    status: str
    exit_code: int | None = None


def build_exec_command(
    script_in_container: Path,
    script_rel_path: str,
    echo_label: str | None,
) -> str:
    """Build the ``sh -lc`` payload that runs the script in the container.

    Pure and side-effect free so it can be unit tested without Docker.
    """
    segments = ["set -e", f"cd {shlex.quote(str(script_in_container.parent))}"]
    if echo_label is not None:
        segments.append(f"echo '--- {echo_label} ({shlex.quote(script_rel_path)}) ---'")
        segments.append(f"cat {shlex.quote(str(script_in_container))}")
        segments.append(f"echo '--- end {echo_label} ---'")
    segments.append(f"sh {shlex.quote(str(script_in_container))}")
    return "; ".join(segments)


def _format_command(command: Sequence[str]) -> str:
    return "$ " + " ".join(shlex.quote(token) for token in command)


def _stream_output(log: LogSink, result: subprocess.CompletedProcess[str]) -> None:
    for line in (result.stdout or "").splitlines():
        if line.strip():
            log("stdout", "info", line)
    for line in (result.stderr or "").splitlines():
        if line.strip():
            log("stderr", "warn", line)


def run_script_in_container(
    spec: ContainerScriptRun,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ContainerRunOutcome:
    """Create a sidecar, run the script against the workspace, clean up.

    Raises ``FileNotFoundError`` if the script does not exist and
    ``ValueError`` if ``script_rel_path`` escapes the workspace.
    """
    workspace_path = spec.workspace_path.resolve()
    script_abs = (workspace_path / spec.script_rel_path).resolve()
    try:
        script_abs.relative_to(workspace_path)
    except ValueError as exc:
        raise ValueError("Invalid workspace path") from exc
    if not script_abs.exists() or not script_abs.is_file():
        raise FileNotFoundError(f"Script not found: {spec.script_rel_path}")

    script_in_container = CONTAINER_WORKSPACE / script_abs.relative_to(workspace_path)

    docker_bin = shutil.which("docker") or "docker"
    name = spec.container_name
    create_cmd = [
        docker_bin,
        "create",
        "--name",
        name,
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        spec.image,
        "sleep",
        "infinity",
    ]
    cp_in_cmd = [docker_bin, "cp", f"{workspace_path}/.", f"{name}:/workspace"]
    start_cmd = [docker_bin, "start", name]
    exec_cmd = [
        docker_bin,
        "exec",
        name,
        "sh",
        "-lc",
        build_exec_command(script_in_container, spec.script_rel_path, spec.echo_label),
    ]
    sync_back_cmd = [docker_bin, "cp", f"{name}:/workspace/.", str(workspace_path)]
    rm_cmd = [docker_bin, "rm", "-f", name]

    def cleanup() -> None:
        try:
            subprocess.run(rm_cmd, capture_output=True, text=True)
        except OSError:
            pass

    def canceled() -> ContainerRunOutcome:
        cleanup()
        log("system", "warn", "Run canceled")
        return ContainerRunOutcome("canceled")

    # Provision and start the sidecar.
    for command in (create_cmd, cp_in_cmd, start_cmd):
        if is_canceled():
            return canceled()
        log("system", "info", _format_command(command))
        result = subprocess.run(command, capture_output=True, text=True)
        _stream_output(log, result)
        if result.returncode != 0:
            cleanup()
            log(
                "system",
                "error",
                f"Container step failed (exit code {result.returncode})",
            )
            return ContainerRunOutcome("failed", result.returncode)

    if is_canceled():
        return canceled()

    # Execute the script.
    log("system", "info", _format_command(exec_cmd))
    exec_result = subprocess.run(exec_cmd, capture_output=True, text=True)
    _stream_output(log, exec_result)
    if is_canceled():
        return canceled()

    if exec_result.returncode != 0:
        cleanup()
        return ContainerRunOutcome("failed", exec_result.returncode)

    # Optionally pull the (possibly mutated) workspace back to the host.
    if spec.sync_workspace_back:
        log("system", "info", "Syncing container workspace to host")
        log("system", "info", _format_command(sync_back_cmd))
        sync_result = subprocess.run(sync_back_cmd, capture_output=True, text=True)
        _stream_output(log, sync_result)
        if sync_result.returncode != 0:
            cleanup()
            log("system", "error", "Failed to copy workspace from container")
            return ContainerRunOutcome("failed", exec_result.returncode)
        log("system", "info", "Sync complete")

    cleanup()
    return ContainerRunOutcome("succeeded", exec_result.returncode)
