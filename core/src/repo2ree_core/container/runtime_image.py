"""Helpers for loading a runtime image from a Docker archive for one run."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from repo2ree_core.container.run_script import LogSink, format_command, stream_output


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
    log("system", "info", format_command(load_cmd))
    load_result = subprocess.run(load_cmd, capture_output=True, text=True)
    stream_output(log, load_result)
    if load_result.returncode != 0:
        raise RuntimeError(f"Failed to load runtime image from {runtime_archive_path.name}")

    loaded_ref = _loaded_image_ref(load_result)
    if not loaded_ref:
        raise RuntimeError("Docker did not report a loaded runtime image")

    tag_cmd = [docker_bin, "tag", loaded_ref, run_image]
    log("system", "info", format_command(tag_cmd))
    tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
    stream_output(log, tag_result)
    if tag_result.returncode != 0:
        raise RuntimeError(f"Failed to tag loaded runtime image {loaded_ref}")

    try:
        yield run_image
    finally:
        with suppress(Exception):
            subprocess.run(
                [docker_bin, "rmi", "-f", run_image, loaded_ref],
                capture_output=True,
                text=True,
            )
