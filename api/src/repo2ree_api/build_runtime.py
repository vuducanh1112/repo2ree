from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _start_background_run,
    _run_summary,
)
from repo2ree_api.storage.workspace_files import workspace_dir


build_runtime_router = APIRouter()


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBuildRuntimeRunPayload(_StrictRequestModel):
    build_runtime_script_path: str
    idempotencyKey: str | None = None


def _resolve_workspace_relative_path(ree_id: str, relative_path: str) -> Path:
    root = workspace_dir(ree_id).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid workspace path") from exc
    if candidate.name.startswith(".workspace") or candidate.name.startswith(".upload."):
        raise HTTPException(status_code=400, detail="Invalid workspace path")
    return candidate


def _require_non_empty_path(path_value: str, field_name: str) -> str:
    path = path_value.strip()
    if not path:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return path


def _docker_copy_workspace_into_container(
    docker_bin: str,
    container_name: str,
    workspace_path: Path,
    ree_id: str,
    run_id: str,
) -> bool:
    cmd = [docker_bin, "cp", f"{workspace_path}/.", f"{container_name}:/workspace"]
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(t) for t in cmd),
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            if line.strip():
                _append_run_log(ree_id, run_id, "stderr", "warn", line)
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "error",
            f"Failed to copy workspace into container (exit code {result.returncode})",
        )
        return False
    return True


def _docker_sync_workspace_from_container(
    docker_bin: str,
    container_name: str,
    workspace_path: Path,
    ree_id: str,
    run_id: str,
) -> bool:
    _append_run_log(
        ree_id, run_id, "system", "info", "Syncing container workspace to host"
    )

    cp_cmd = [docker_bin, "cp", f"{container_name}:/workspace/.", str(workspace_path)]
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(t) for t in cp_cmd),
    )
    cp_result = subprocess.run(cp_cmd, capture_output=True, text=True)
    if cp_result.returncode != 0:
        _append_run_log(
            ree_id, run_id, "system", "error", "Failed to copy workspace from container"
        )
        for line in cp_result.stderr.splitlines():
            if line.strip():
                _append_run_log(ree_id, run_id, "stderr", "warn", line)
        return False

    _append_run_log(ree_id, run_id, "system", "info", "Sync complete")
    return True


def _docker_build_run(
    ree_id: str,
    run_id: str,
    script_relative_path: str,
) -> tuple[str, dict[str, Any]]:
    workspace_path = workspace_dir(ree_id).resolve()
    script_abs_path = _resolve_workspace_relative_path(ree_id, script_relative_path)
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Build script not found: {script_relative_path}"
        )

    script_in_container = Path("/workspace") / script_abs_path.relative_to(
        workspace_path
    )
    script_dir_in_container = script_in_container.parent

    _append_run_log(ree_id, run_id, "system", "info", f"Starting build run {run_id}")
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "Starting container image docker:latest",
    )
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        f"Build script: {script_relative_path}",
    )

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-build-{run_id}"
    docker_create_cmd = [
        docker_bin,
        "create",
        "--name",
        container_name,
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "docker:latest",
        "sleep",
        "infinity",
    ]
    docker_start_cmd = [docker_bin, "start", container_name]
    docker_exec_script_cmd = [
        docker_bin,
        "exec",
        container_name,
        "sh",
        "-lc",
        (
            "set -e; "
            f"cd {shlex.quote(str(script_dir_in_container))}; "
            f"echo '--- build_runtime_script ({shlex.quote(script_relative_path)}) ---'; "
            f"cat {shlex.quote(str(script_in_container))}; "
            "echo '--- end build_runtime_script ---'; "
            f"sh {shlex.quote(str(script_in_container))}"
        ),
    ]
    docker_rm_cmd = [docker_bin, "rm", "-f", container_name]

    canceled_outputs: dict[str, Any] = {
        "buildRuntimeScriptPath": script_relative_path,
        "dockerImage": "docker:latest",
    }

    def cancel_and_cleanup(msg: str) -> tuple[str, dict[str, Any]]:
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        _append_run_log(ree_id, run_id, "system", "warn", msg)
        return "canceled", canceled_outputs

    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(t) for t in docker_create_cmd),
    )
    create_result = subprocess.run(docker_create_cmd, capture_output=True, text=True)
    if _is_cancel_requested(ree_id, run_id):
        return cancel_and_cleanup("Build run canceled")
    if create_result.returncode != 0:
        for line in create_result.stderr.splitlines():
            if line.strip():
                _append_run_log(ree_id, run_id, "stderr", "warn", line)
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "error",
            f"Build run failed (exit code {create_result.returncode})",
        )
        return "failed", {
            **canceled_outputs,
            "containerExitCode": create_result.returncode,
        }

    if not _docker_copy_workspace_into_container(
        docker_bin, container_name, workspace_path, ree_id, run_id
    ):
        if _is_cancel_requested(ree_id, run_id):
            return cancel_and_cleanup("Build run canceled")
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        return "failed", canceled_outputs
    if _is_cancel_requested(ree_id, run_id):
        return cancel_and_cleanup("Build run canceled")

    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(t) for t in docker_start_cmd),
    )
    start_result = subprocess.run(docker_start_cmd, capture_output=True, text=True)
    if _is_cancel_requested(ree_id, run_id):
        return cancel_and_cleanup("Build run canceled")
    if start_result.returncode != 0:
        for line in start_result.stdout.splitlines():
            if line.strip():
                _append_run_log(ree_id, run_id, "stdout", "info", line)
        for line in start_result.stderr.splitlines():
            if line.strip():
                _append_run_log(ree_id, run_id, "stderr", "warn", line)
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "error",
            f"Container start failed (exit code {start_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        return "failed", {
            **canceled_outputs,
            "containerExitCode": start_result.returncode,
        }

    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(t) for t in docker_exec_script_cmd),
    )
    exec_result = subprocess.run(docker_exec_script_cmd, capture_output=True, text=True)
    if _is_cancel_requested(ree_id, run_id):
        return cancel_and_cleanup("Build run canceled")

    for line in exec_result.stdout.splitlines():
        if line.strip():
            _append_run_log(ree_id, run_id, "stdout", "info", line)
    for line in exec_result.stderr.splitlines():
        if line.strip():
            _append_run_log(ree_id, run_id, "stderr", "warn", line)

    sync_succeeded = False
    if exec_result.returncode == 0:
        _append_run_log(
            ree_id, run_id, "system", "info", "Build script executed (exit code 0)"
        )
        sync_succeeded = _docker_sync_workspace_from_container(
            docker_bin, container_name, workspace_path, ree_id, run_id
        )
    else:
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "error",
            f"Build script failed (exit code {exec_result.returncode})",
        )

    try:
        subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    except Exception:
        pass

    status = "succeeded" if exec_result.returncode == 0 and sync_succeeded else "failed"
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info" if status == "succeeded" else "error",
        f"Build run {status} (exit code {exec_result.returncode})",
    )

    return status, {**canceled_outputs, "containerExitCode": exec_result.returncode}


def create_build_run_state(
    ree_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    script_path = _require_non_empty_path(
        payload.build_runtime_script_path,
        "build_runtime_script_path",
    )
    return _start_background_run(
        ree_id=ree_id,
        operation="build",
        request_payload={"build_runtime_script_path": script_path},
        run_id_prefix="build",
        runner=lambda ws_id, run_id: _docker_build_run(
            ree_id=ws_id,
            run_id=run_id,
            script_relative_path=script_path,
        ),
    )


@build_runtime_router.post("/api/v1/rees/{ree_id}/build-runtime")
def create_workspace_build_runtime_run(
    ree_id: str, payload: CreateBuildRuntimeRunPayload
):
    run_state = create_build_run_state(ree_id, payload)
    return _run_summary(run_state)
