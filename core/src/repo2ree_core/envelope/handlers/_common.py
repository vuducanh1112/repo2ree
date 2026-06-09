from __future__ import annotations

import shlex
import subprocess
import threading
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.storage.layout import ReeLayout, validate_relative_path
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now  # noqa: F401  (re-exported)
from repo2ree_core.working_environment.base import CancelCheck, StepOutcome
from repo2ree_protocol.result import ActionResult

WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")


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

    if proc.stdout is None:
        raise RuntimeError("stdout pipe unavailable after Popen")

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


def run_workspace_script_handler(
    script_path: str,
    *,
    operation: str,
    noun: str,
    output_key: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    """Validate and run a workspace script directly inside the workbench.

    Shared by the build_runtime and activation_test handlers, which differ only
    in their labels (``operation``/``noun``) and the output key. ``noun`` is the
    capitalised run name (e.g. "Build", "Activation").
    """
    if is_canceled():
        log("system", "warn", f"{operation} canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    script_path = script_path.strip()
    try:
        resolve_workspace_path(layout, script_path)
    except Exception as exc:
        log("system", "error", f"invalid {noun.lower()} script path: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"Starting {noun.lower()} run {run_id}")
    log("system", "info", f"{noun} script: {script_path}")
    outcome = run_script_directly(
        workspace=layout.workspace.resolve(),
        script_rel_path=script_path,
        log=log,
        is_canceled=is_canceled,
    )

    log(
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"{noun} run {outcome.status} (exit code {outcome.exit_code})",
    )
    outputs: dict[str, Any] = {output_key: script_path}
    if outcome.exit_code is not None:
        outputs["containerExitCode"] = outcome.exit_code
    return ActionResult(
        status=outcome.status,
        exit_code=outcome.exit_code or 0,
        outputs=outputs,
    )


def patch_ree_intent(store: ReeStore, patch: dict[str, Any]) -> None:
    if not store.metadata_exists():
        raise FileNotFoundError("metadata not found")

    metadata = store.read_metadata_json()
    intent = ReeIntent.from_metadata(metadata).apply_patch(patch)
    metadata["reeIntent"] = intent.model_dump(exclude_none=True)
    if intent.name:
        metadata["name"] = intent.name
    if intent.origin_url:
        metadata["externalRef"] = intent.origin_url
    source = metadata.get("source")
    if isinstance(source, dict) and intent.source_type:
        source["sourceType"] = intent.source_type
        metadata["source"] = source
    metadata["updatedAt"] = utc_now()
    store.write_metadata_json(metadata)
