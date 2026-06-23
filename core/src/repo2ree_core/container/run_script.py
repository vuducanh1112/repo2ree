"""Low-level Docker CLI helpers for in-container script execution.

Only the command-builder and workspace constant are kept here; the full
container lifecycle is now owned by the working_environment package.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from repo2ree_protocol.log import LogSink  # noqa: F401

CONTAINER_WORKSPACE = Path("/workspace")

# The Docker socket is mounted so a runtime may itself drive Docker.
DOCKER_SOCK_MOUNT = "/var/run/docker.sock:/var/run/docker.sock"


# ================================================
# Naming conventions (run-scoped)
# ================================================


def container_name(run_id: str) -> str:
    """Name of the per-run working-environment container."""
    return f"repo2ree-we-{run_id}"


def runtime_image_tag(run_id: str) -> str:
    """Run-scoped tag applied to the loaded runtime image."""
    return f"repo2ree-runtime-{run_id}"


def experiment_script_rel(run_id: str) -> str:
    """Workspace-relative path of the command script a run executes."""
    return f".workspace/exp_{run_id}.sh"


# ================================================
# Canonical Docker argv builders
# ================================================
# These are the single source of truth for the exact Docker commands the
# working_environment executes; the lifecycle projection (command_plan) renders
# the very same argv so display cannot drift from execution.


def docker_load_argv(docker: str, artifact: str) -> list[str]:
    return [docker, "load", "-i", artifact]


def docker_tag_argv(docker: str, loaded_ref: str, image: str) -> list[str]:
    return [docker, "tag", loaded_ref, image]


def docker_create_argv(docker: str, *, container: str, image: str, sock_mount: bool = True) -> list[str]:
    sock = ["-v", DOCKER_SOCK_MOUNT] if sock_mount else []
    return [docker, "create", "--name", container, *sock, image, "sleep", "infinity"]


def docker_cp_in_argv(docker: str, *, workspace: str, container: str) -> list[str]:
    return [docker, "cp", f"{workspace}/.", f"{container}:{CONTAINER_WORKSPACE}"]


def docker_start_argv(docker: str, container: str) -> list[str]:
    return [docker, "start", container]


def docker_exec_argv(
    docker: str,
    *,
    container: str,
    exec_command: str,
    login_shell: bool,
    interactive: bool = False,
) -> list[str]:
    sh_flag = "-lc" if login_shell else "-c"
    return [docker, "exec", *(["-i"] if interactive else []), container, "sh", sh_flag, exec_command]


def docker_cp_out_argv(docker: str, *, container: str, workspace: str) -> list[str]:
    return [docker, "cp", f"{container}:{CONTAINER_WORKSPACE}/.", workspace]


def docker_rm_argv(docker: str, container: str) -> list[str]:
    return [docker, "rm", "-f", container]


def docker_rmi_argv(docker: str, *, image: str, loaded_ref: str) -> list[str]:
    return [docker, "rmi", "-f", image, loaded_ref]


def format_argv(argv: list[str]) -> str:
    """Render an argv list as a single, copy-pasteable shell line."""
    return " ".join(shlex.quote(t) for t in argv)


def format_command(command: list[str]) -> str:
    return "$ " + format_argv(command)


def stream_output(log: LogSink, result: subprocess.CompletedProcess[str]) -> None:
    for line in (result.stdout or "").splitlines():
        if line.strip():
            log("stdout", "info", line)
    for line in (result.stderr or "").splitlines():
        if line.strip():
            log("stderr", "warn", line)


def build_exec_command(
    script_in_container: Path,
    script_rel_path: str,
    echo_label: str | None,
    working_dir: Path | None = None,
) -> str:
    command_working_dir = working_dir or script_in_container.parent
    segments = ["set -e", f"cd {shlex.quote(str(command_working_dir))}"]
    if echo_label is not None:
        segments.append(f"echo '--- {echo_label} ({shlex.quote(script_rel_path)}) ---'")
        segments.append(f"cat {shlex.quote(str(script_in_container))}")
        segments.append(f"echo '--- end {echo_label} ---'")
    segments.append(f"sh {shlex.quote(str(script_in_container))}")

    result = "; ".join(segments)

    return result
