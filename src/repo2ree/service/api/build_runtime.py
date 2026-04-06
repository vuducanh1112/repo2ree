from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree.service.api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _start_background_run,
)
from repo2ree.service.storage.workspace_files import workspace_dir


build_runtime_router = APIRouter()


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBuildRuntimeRunPayload(_StrictRequestModel):
    build_runtime_script_path: str
    produced_runtime_path: str
    idempotencyKey: str | None = None


def _resolve_workspace_relative_path(workspace_id: str, relative_path: str) -> Path:
    root = workspace_dir(workspace_id).resolve()
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


def _docker_build_run(
    workspace_id: str,
    run_id: str,
    script_relative_path: str,
    runtime_relative_path: str,
) -> tuple[str, dict[str, Any]]:
    workspace_path = workspace_dir(workspace_id).resolve()
    script_abs_path = _resolve_workspace_relative_path(
        workspace_id, script_relative_path
    )
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Build script not found: {script_relative_path}"
        )

    script_in_container = Path("/workspace") / script_abs_path.relative_to(
        workspace_path
    )
    script_dir_in_container = script_in_container.parent
    runtime_abs_path = _resolve_workspace_relative_path(
        workspace_id, runtime_relative_path
    )
    runtime_in_container = Path("/workspace") / runtime_abs_path.relative_to(
        workspace_path
    )

    _append_run_log(
        workspace_id, run_id, "system", "info", f"Starting build run {run_id}"
    )
    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        "Starting container image docker:latest",
    )
    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        f"Build script: {script_relative_path}",
    )
    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        f"Expected runtime output: {runtime_relative_path}",
    )

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-build-{run_id}"
    docker_create_cmd = [
        "sudo",
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
    docker_cp_cmd = [
        "sudo",
        docker_bin,
        "cp",
        f"{workspace_path}/.",
        f"{container_name}:/workspace",
    ]
    docker_start_cmd = ["sudo", docker_bin, "start", container_name]
    docker_exec_script_cmd = [
        "sudo",
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
    docker_exec_check_cmd = [
        "sudo",
        docker_bin,
        "exec",
        container_name,
        "sh",
        "-lc",
        f"test -f {shlex.quote(str(runtime_in_container))}",
    ]
    docker_rm_cmd = ["sudo", docker_bin, "rm", "-f", container_name]

    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_create_cmd),
    )
    create_result = subprocess.run(docker_create_cmd, capture_output=True, text=True)
    if _is_cancel_requested(workspace_id, run_id):
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        _append_run_log(workspace_id, run_id, "system", "warn", "Build run canceled")
        return (
            "canceled",
            {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
                "dockerImage": "docker:latest",
            },
        )
    if create_result.returncode != 0:
        for line in create_result.stderr.splitlines():
            if line.strip():
                _append_run_log(workspace_id, run_id, "stderr", "warn", line)
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "error",
            f"Build run failed (exit code {create_result.returncode})",
        )
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": create_result.returncode,
        }
        return "failed", outputs

    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_cp_cmd),
    )
    cp_result = subprocess.run(docker_cp_cmd, capture_output=True, text=True)
    if _is_cancel_requested(workspace_id, run_id):
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        _append_run_log(workspace_id, run_id, "system", "warn", "Build run canceled")
        return (
            "canceled",
            {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
                "dockerImage": "docker:latest",
            },
        )
    if cp_result.returncode != 0:
        for line in cp_result.stderr.splitlines():
            if line.strip():
                _append_run_log(workspace_id, run_id, "stderr", "warn", line)
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "error",
            f"Build run failed (exit code {cp_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": cp_result.returncode,
        }
        return "failed", outputs

    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_start_cmd),
    )
    start_result = subprocess.run(docker_start_cmd, capture_output=True, text=True)
    if _is_cancel_requested(workspace_id, run_id):
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        _append_run_log(workspace_id, run_id, "system", "warn", "Build run canceled")
        return (
            "canceled",
            {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
                "dockerImage": "docker:latest",
            },
        )
    if start_result.returncode != 0:
        for line in start_result.stdout.splitlines():
            if line.strip():
                _append_run_log(workspace_id, run_id, "stdout", "info", line)
        for line in start_result.stderr.splitlines():
            if line.strip():
                _append_run_log(workspace_id, run_id, "stderr", "warn", line)
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "error",
            f"Container start failed (exit code {start_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": start_result.returncode,
        }
        return "failed", outputs

    _append_run_log(
        workspace_id,
        run_id,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_exec_script_cmd),
    )
    exec_result = subprocess.run(docker_exec_script_cmd, capture_output=True, text=True)
    if _is_cancel_requested(workspace_id, run_id):
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        _append_run_log(workspace_id, run_id, "system", "warn", "Build run canceled")
        return (
            "canceled",
            {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
                "dockerImage": "docker:latest",
            },
        )

    for line in exec_result.stdout.splitlines():
        if line.strip():
            _append_run_log(workspace_id, run_id, "stdout", "info", line)
    for line in exec_result.stderr.splitlines():
        if line.strip():
            _append_run_log(workspace_id, run_id, "stderr", "warn", line)

    runtime_available = False
    if exec_result.returncode == 0:
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "info",
            "Build script executed (exit code 0)",
        )
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "info",
            f"Checking for produced runtime at {runtime_relative_path}",
        )
        check_result = subprocess.run(
            docker_exec_check_cmd, capture_output=True, text=True
        )

        if check_result.returncode == 0:
            docker_cp_back_cmd = [
                "sudo",
                docker_bin,
                "cp",
                f"{container_name}:{runtime_in_container}",
                str(runtime_abs_path),
            ]
            _append_run_log(
                workspace_id,
                run_id,
                "system",
                "info",
                "$ " + " ".join(shlex.quote(token) for token in docker_cp_back_cmd),
            )
            cp_back_result = subprocess.run(
                docker_cp_back_cmd, capture_output=True, text=True
            )
            if cp_back_result.returncode == 0:
                runtime_available = True
                _append_run_log(
                    workspace_id,
                    run_id,
                    "system",
                    "info",
                    f"Successfully copied produced runtime to {runtime_relative_path}",
                )
            else:
                _append_run_log(
                    workspace_id,
                    run_id,
                    "system",
                    "error",
                    f"Produced runtime could not be copied from container at {runtime_relative_path}",
                )
                if cp_back_result.stderr.strip():
                    for line in cp_back_result.stderr.splitlines():
                        if line.strip():
                            _append_run_log(
                                workspace_id, run_id, "stderr", "warn", line
                            )
        else:
            _append_run_log(
                workspace_id,
                run_id,
                "system",
                "error",
                f"Produced runtime not found in container at {runtime_relative_path}",
            )
    else:
        _append_run_log(
            workspace_id,
            run_id,
            "system",
            "error",
            f"Build script failed (exit code {exec_result.returncode})",
        )

    try:
        subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    except Exception:
        pass

    status = (
        "succeeded" if exec_result.returncode == 0 and runtime_available else "failed"
    )
    final_level = "info" if status == "succeeded" else "error"
    _append_run_log(
        workspace_id,
        run_id,
        "system",
        final_level,
        f"Build run {status} (exit code {exec_result.returncode})",
    )

    outputs = {
        "buildRuntimeScriptPath": script_relative_path,
        "producedRuntimePath": runtime_relative_path,
        "dockerImage": "docker:latest",
        "containerExitCode": exec_result.returncode,
    }
    return status, outputs


def create_build_run_state(
    workspace_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    script_path = _require_non_empty_path(
        payload.build_runtime_script_path,
        "build_runtime_script_path",
    )
    runtime_path = _require_non_empty_path(
        payload.produced_runtime_path,
        "produced_runtime_path",
    )
    request_payload = {
        "build_runtime_script_path": script_path,
        "produced_runtime_path": runtime_path,
    }
    return _start_background_run(
        workspace_id=workspace_id,
        operation="build",
        request_payload=request_payload,
        run_id_prefix="build",
        runner=lambda ws_id, run_id: _docker_build_run(
            workspace_id=ws_id,
            run_id=run_id,
            script_relative_path=script_path,
            runtime_relative_path=runtime_path,
        ),
    )


@build_runtime_router.post("/api/v1/workspaces/{workspace_id}/build-runtime")
def create_workspace_build_runtime_run(
    workspace_id: str, payload: CreateBuildRuntimeRunPayload
):
    from repo2ree.service.api.run_management import _run_summary

    run_state = create_build_run_state(workspace_id, payload)
    return _run_summary(run_state)
