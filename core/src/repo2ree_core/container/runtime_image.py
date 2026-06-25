"""Helpers for loading a runtime image from a Docker archive for one run."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from repo2ree_core.container.run_script import (
    LogSink,
    docker_load_argv,
    docker_rmi_argv,
    docker_tag_argv,
    format_command,
    runtime_image_tag,
    stream_output,
)


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
    preserve_base_image: bool = False,
) -> Iterator[str]:
    """Load a runtime tarball and expose a run-scoped image tag.

    When ``preserve_base_image`` is set, cleanup drops only the run-scoped tag
    and leaves the loaded base image in place — used when the runtime daemon's
    image cache is shared across runs and the base should survive for reuse.
    """
    docker_bin = shutil.which("docker") or "docker"
    run_image = runtime_image_tag(run_id)

    load_cmd = docker_load_argv(docker_bin, str(runtime_archive_path))
    log("system", "info", format_command(load_cmd))
    load_result = subprocess.run(load_cmd, capture_output=True, text=True)
    stream_output(log, load_result)
    if load_result.returncode != 0:
        raise RuntimeError(f"Failed to load runtime image from {runtime_archive_path.name}")

    loaded_ref = _loaded_image_ref(load_result)
    if not loaded_ref:
        raise RuntimeError("Docker did not report a loaded runtime image")

    tag_cmd = docker_tag_argv(docker_bin, loaded_ref, run_image)
    log("system", "info", format_command(tag_cmd))
    tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
    stream_output(log, tag_result)
    if tag_result.returncode != 0:
        raise RuntimeError(f"Failed to tag loaded runtime image {loaded_ref}")

    try:
        yield run_image
    finally:
        with suppress(Exception):
            loaded_ref_cleanup = None if preserve_base_image else loaded_ref
            subprocess.run(
                docker_rmi_argv(docker_bin, image=run_image, loaded_ref=loaded_ref_cleanup),
                capture_output=True,
                text=True,
            )
