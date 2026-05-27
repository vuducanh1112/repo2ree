"""Helpers for loading a runtime image from a Docker archive for one run."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .run_script import LogSink


def _format_command(command: list[str]) -> str:
    return "$ " + " ".join(shlex.quote(token) for token in command)


def _stream_output(log: LogSink, result: subprocess.CompletedProcess[str]) -> None:
    for line in (result.stdout or "").splitlines():
        if line.strip():
            log("stdout", "info", line)
    for line in (result.stderr or "").splitlines():
        if line.strip():
            log("stderr", "warn", line)


def _loaded_image_ref(load_result: subprocess.CompletedProcess[str]) -> str | None:
    for line in (load_result.stdout or "").splitlines():
        text = line.strip()
        for prefix in ("Loaded image: ", "Loaded image ID: "):
            if text.startswith(prefix):
                return text.removeprefix(prefix).strip()
    return None


@contextmanager
def loaded_runtime_image(
    runtime_archive_path: Path,
    *,
    run_id: str,
    log: LogSink,
) -> Iterator[str]:
    """Load a runtime tarball and expose a run-scoped image tag."""
    docker_bin = shutil.which("docker") or "docker"
    run_image = f"repo2ree-runtime-{run_id}"

    load_cmd = [docker_bin, "load", "-i", str(runtime_archive_path)]
    log("system", "info", _format_command(load_cmd))
    load_result = subprocess.run(load_cmd, capture_output=True, text=True)
    _stream_output(log, load_result)
    if load_result.returncode != 0:
        raise RuntimeError(
            f"Failed to load runtime image from {runtime_archive_path.name}"
        )

    loaded_ref = _loaded_image_ref(load_result)
    if not loaded_ref:
        raise RuntimeError("Docker did not report a loaded runtime image")

    tag_cmd = [docker_bin, "tag", loaded_ref, run_image]
    log("system", "info", _format_command(tag_cmd))
    tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
    _stream_output(log, tag_result)
    if tag_result.returncode != 0:
        raise RuntimeError(f"Failed to tag loaded runtime image {loaded_ref}")

    try:
        yield run_image
    finally:
        try:
            subprocess.run(
                [docker_bin, "rmi", "-f", run_image, loaded_ref],
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
