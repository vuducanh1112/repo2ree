from __future__ import annotations

import shlex
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.storage.layout import ReeLayout, validate_relative_path
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck, StepOutcome

WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_workspace_path(layout: ReeLayout, rel_path: str) -> Path:
    path = rel_path.strip()
    validate_relative_path(path)
    if PurePosixPath(path).name.startswith(WORKSPACE_CONTROL_PREFIXES):
        raise ValueError("Invalid workspace path")
    candidate = (layout.workspace / path).resolve()
    candidate.relative_to(layout.workspace.resolve())
    return candidate


def run_script_directly(
    *,
    workspace: Path,
    script_rel_path: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> StepOutcome:
    """Run a script as a native subprocess inside the workbench.

    The workbench IS the isolated execution environment, so no nested
    Docker container is needed. The script runs in the script's own directory
    so that relative paths (e.g. `docker build .`) resolve correctly.
    """
    script_abs = (workspace / script_rel_path).resolve()
    if not script_abs.is_file():
        log("system", "error", f"script not found: {script_rel_path}")
        return StepOutcome("failed", 1)

    script_dir = str(script_abs.parent)

    log(
        "system",
        "info",
        f"$ bash --login -c 'set -e; cd {shlex.quote(script_dir)}; source {shlex.quote(str(script_abs))}'",
    )

    proc = subprocess.Popen(
        [
            "bash",
            "--login",
            "-c",
            f"set -e; cd {shlex.quote(script_dir)}; source {shlex.quote(str(script_abs))}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=script_dir,
    )

    assert proc.stdout is not None

    def _stream() -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            log("stdout", "info", line.rstrip())

    reader = threading.Thread(target=_stream, daemon=True)
    reader.start()

    while proc.poll() is None:
        if is_canceled():
            proc.terminate()
            reader.join(timeout=5)
            return StepOutcome("canceled")

    reader.join()
    exit_code = proc.returncode
    status = "succeeded" if exit_code == 0 else "failed"
    return StepOutcome(status, exit_code)


def patch_ree_intent(store: ReeStore, patch: dict[str, Any]) -> None:
    if not store.metadata_exists():
        raise FileNotFoundError("metadata not found")

    metadata = store.read_metadata_json()
    intent = ReeIntent.from_metadata(metadata).apply_patch(patch)
    metadata["reeIntent"] = intent.model_dump(exclude_none=True)
    if intent.name:
        metadata["name"] = intent.name
    metadata["externalRef"] = intent.origin_url or None
    source = metadata.get("source")
    if isinstance(source, dict) and intent.source_type:
        source["sourceType"] = intent.source_type
        metadata["source"] = source
    metadata["updatedAt"] = utc_now()
    store.write_metadata_json(metadata)
