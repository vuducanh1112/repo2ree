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


def format_command(command: list[str]) -> str:
    return "$ " + " ".join(shlex.quote(t) for t in command)


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
