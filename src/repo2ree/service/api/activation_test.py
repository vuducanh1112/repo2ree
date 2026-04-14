from __future__ import annotations

import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree.service.api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree.service.storage.workspace_files import (
    read_workspace_metadata,
    workspace_dir,
)


activation_test_router = APIRouter()


class CreateActivationTestRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_script_path: str
    idempotencyKey: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_log(
    entries: list[dict[str, Any]],
    seq: int,
    stream: str,
    level: str,
    message: str,
) -> int:
    entries.append(
        {
            "seq": seq,
            "ts": _utc_now(),
            "stream": stream,
            "level": level,
            "message": message,
        }
    )
    return seq + 1


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


def resolve_activation_script_path(
    ree_id: str,
    *,
    params: dict[str, Any] | None = None,
    activation_script_path: str | None = None,
) -> str:
    metadata = read_workspace_metadata(ree_id)
    ree_draft = dict(metadata.get("reeDraft") or {})
    params = dict(params or {})
    script_path = (
        activation_script_path
        or str(
            params.get("activation_script")
            or params.get("activation_script_path")
            or ree_draft.get("activation_script")
            or ree_draft.get("validate_runtime_reproducibility_script")
            or ""
        ).strip()
    )

    if not script_path:
        raise HTTPException(status_code=400, detail="activation_script is required")

    script_abs_path = _resolve_workspace_relative_path(ree_id, script_path)
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Activation script not found: {script_path}"
        )

    return script_path


def run_activation_test(
    ree_id: str,
    run_id: str,
    activation_script_path: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    workspace_path = workspace_dir(ree_id).resolve()
    script_abs_path = _resolve_workspace_relative_path(ree_id, activation_script_path)
    script_in_container = Path("/workspace") / script_abs_path.relative_to(
        workspace_path
    )
    script_dir_in_container = script_in_container.parent

    entries: list[dict[str, Any]] = []
    seq = 1
    seq = _append_log(
        entries, seq, "system", "info", f"Starting activation run {run_id}"
    )
    seq = _append_log(
        entries, seq, "system", "info", "Starting container image docker:latest"
    )
    seq = _append_log(
        entries, seq, "system", "info", f"Activation script: {activation_script_path}"
    )

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-activation-{run_id}"
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
            f"echo '--- activation_script ({shlex.quote(activation_script_path)}) ---'; "
            f"cat {shlex.quote(str(script_in_container))}; "
            "echo '--- end activation_script ---'; "
            f"sh {shlex.quote(str(script_in_container))}"
        ),
    ]
    docker_rm_cmd = ["sudo", docker_bin, "rm", "-f", container_name]

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_create_cmd),
    )
    create_result = subprocess.run(docker_create_cmd, capture_output=True, text=True)
    if create_result.returncode != 0:
        for line in create_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Activation run failed (exit code {create_result.returncode})",
        )
        outputs = {
            "activationScriptPath": activation_script_path,
            "dockerImage": "docker:latest",
            "containerExitCode": create_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_cp_cmd),
    )
    cp_result = subprocess.run(docker_cp_cmd, capture_output=True, text=True)
    if cp_result.returncode != 0:
        for line in cp_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Activation run failed (exit code {cp_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "activationScriptPath": activation_script_path,
            "dockerImage": "docker:latest",
            "containerExitCode": cp_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_start_cmd),
    )
    start_result = subprocess.run(docker_start_cmd, capture_output=True, text=True)
    if start_result.returncode != 0:
        for line in start_result.stdout.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stdout", "info", line)
        for line in start_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Container start failed (exit code {start_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "activationScriptPath": activation_script_path,
            "dockerImage": "docker:latest",
            "containerExitCode": start_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_exec_script_cmd),
    )
    exec_result = subprocess.run(docker_exec_script_cmd, capture_output=True, text=True)

    for line in exec_result.stdout.splitlines():
        if line.strip():
            seq = _append_log(entries, seq, "stdout", "info", line)
    for line in exec_result.stderr.splitlines():
        if line.strip():
            seq = _append_log(entries, seq, "stderr", "warn", line)

    try:
        subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    except Exception:
        pass

    status = "succeeded" if exec_result.returncode == 0 else "failed"
    final_level = "info" if status == "succeeded" else "error"
    seq = _append_log(
        entries,
        seq,
        "system",
        final_level,
        f"Activation run {status} (exit code {exec_result.returncode})",
    )

    outputs = {
        "activationScriptPath": activation_script_path,
        "dockerImage": "docker:latest",
        "containerExitCode": exec_result.returncode,
    }
    return status, entries, outputs


def create_activation_run_state(
    ree_id: str,
    payload: CreateActivationTestRunPayload,
) -> dict[str, Any]:
    activation_script_path = resolve_activation_script_path(
        ree_id,
        params={},
        activation_script_path=payload.activation_script_path,
    )
    request_payload = {"activation_script_path": activation_script_path}

    def _runner(ws_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        if _is_cancel_requested(ws_id, run_id):
            _append_run_log(ws_id, run_id, "system", "warn", "Activation run canceled")
            return "canceled", {"activationScriptPath": activation_script_path}
        status, logs, outputs = run_activation_test(
            ree_id=ws_id,
            run_id=run_id,
            activation_script_path=activation_script_path,
        )
        for entry in logs:
            _append_run_log(
                ws_id,
                run_id,
                str(entry.get("stream") or "system"),
                str(entry.get("level") or "info"),
                str(entry.get("message") or ""),
            )
        if _is_cancel_requested(ws_id, run_id) and status not in {
            "failed",
            "succeeded",
        }:
            return "canceled", outputs
        return status, outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="activation",
        request_payload=request_payload,
        run_id_prefix="activation",
        runner=_runner,
    )


@activation_test_router.post("/api/v1/rees/{ree_id}/activation-test")
def create_workspace_activation_test_run(
    ree_id: str, payload: CreateActivationTestRunPayload
):
    run_state = create_activation_run_state(ree_id, payload)
    return _run_summary(run_state)
