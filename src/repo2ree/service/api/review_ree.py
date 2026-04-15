from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from repo2ree.service.api.review_run_management import (
    _append_review_run_log,
    _get_review_run_state,
    _is_cancel_requested,
    _mark_review_cancel_requested,
    _paginate,
    _review_run_summary,
    _start_background_review_run,
)

from repo2ree.service.storage.review_files import (
    ReviewUploadCompletePayload,
    ReviewUploadInitPayload,
    complete_review_upload,
    get_review,
    init_review_upload,
    review_metadata_path,
    review_workspace_dir,
    store_review_upload_bytes,
)


review_ree_router = APIRouter()


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewBuildRuntimePayload(_StrictRequestModel):
    build_runtime_script_path: str
    produced_runtime_path: str
    idempotencyKey: str | None = None


class ReviewActivationTestPayload(_StrictRequestModel):
    activation_script_path: str
    idempotencyKey: str | None = None


def _load_review_metadata(review_id: str) -> dict[str, Any]:
    path = review_metadata_path(review_id)
    if not path.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _review_workspace_root(review_id: str) -> Path:
    root = review_workspace_dir(review_id).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    return root


def _resolve_path_in_root(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid review workspace path"
        ) from exc
    return candidate


def _resolve_review_relative_path(review_id: str, relative_path: str) -> Path:
    workspace_root = _review_workspace_root(review_id)
    return _resolve_path_in_root(workspace_root, relative_path)


def _require_non_empty_path(path_value: str, field_name: str) -> str:
    path = (path_value or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return path


def _clear_review_non_ree_content(review_id: str) -> None:
    root = _review_workspace_root(review_id)
    for item in root.iterdir():
        if item.name == "ree":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink(missing_ok=True)


def _copy_tree_contents(source_path: Path, destination: Path) -> None:
    if source_path.is_dir():
        for item in source_path.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        return
    target = destination / source_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def _download_or_open_local(origin_url: str, destination: Path) -> None:
    parsed = origin_url.strip()
    if not parsed:
        raise HTTPException(status_code=400, detail="origin_url is required")

    if parsed.startswith("http://") or parsed.startswith("https://"):
        with urlopen(parsed) as response:  # noqa: S310
            destination.write_bytes(response.read())
        return

    local_path = Path(parsed)
    if local_path.exists() and local_path.is_file():
        shutil.copy2(local_path, destination)
        return

    raise HTTPException(status_code=400, detail=f"Source not found: {origin_url}")


def _extract_archive_to_dir(archive_path: Path, destination: Path) -> None:
    lower = archive_path.name.lower()
    if lower.endswith(".zip"):
        destination_root = destination.resolve()
        with zipfile.ZipFile(archive_path) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                member_path = Path(member.filename)
                candidate = (destination / member_path).resolve()
                try:
                    candidate.relative_to(destination_root)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400, detail="Invalid archive entry path"
                    ) from exc
                candidate.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, candidate.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        return
    destination_root = destination.resolve()
    with tarfile.open(archive_path, mode="r:*") as tf:
        for tar_member in tf.getmembers():
            if not tar_member.isfile() or tar_member.issym() or tar_member.islnk():
                continue
            candidate = (destination / tar_member.name).resolve()
            try:
                candidate.relative_to(destination_root)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="Invalid archive entry path"
                ) from exc
            source_obj = tf.extractfile(tar_member)
            if source_obj is None:
                continue
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with source_obj, candidate.open("wb") as dst:
                shutil.copyfileobj(source_obj, dst)


def _append_subprocess_output(
    review_id: str,
    run_id: str,
    result: subprocess.CompletedProcess[str],
) -> None:
    for line in (result.stdout or "").splitlines():
        if line.strip():
            _append_review_run_log(review_id, run_id, "stdout", "info", line)
    for line in (result.stderr or "").splitlines():
        if line.strip():
            _append_review_run_log(review_id, run_id, "stderr", "warn", line)


def _run_review_source_acquire(
    review_id: str, run_id: str
) -> tuple[str, dict[str, object]]:
    metadata = _load_review_metadata(review_id)
    ree_draft = dict(metadata.get("reeDraft") or {})
    if bool(ree_draft.get("_sourceIncluded")):
        _append_review_run_log(
            review_id,
            run_id,
            "system",
            "info",
            "Source snapshot already included in review workspace",
        )
        return "succeeded", {"sourceIncluded": True}

    origin_url = str(ree_draft.get("origin_url") or "").strip()
    source_type = str(ree_draft.get("source_type") or "").strip()
    if not origin_url or source_type not in {"git", "tarball", "zip"}:
        raise HTTPException(
            status_code=400,
            detail="origin_url and source_type are required for source acquisition",
        )

    _append_review_run_log(
        review_id,
        run_id,
        "system",
        "info",
        f"Starting source acquire from {origin_url}",
    )
    if _is_cancel_requested(review_id, run_id):
        _append_review_run_log(
            review_id, run_id, "system", "warn", "Source acquire canceled"
        )
        return "canceled", {"originUrl": origin_url, "sourceType": source_type}

    root = _review_workspace_root(review_id)
    _clear_review_non_ree_content(review_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        extracted_source_path: Path
        if source_type == "git":
            clone_dir = tmp_root / "repo"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", origin_url, str(clone_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise HTTPException(
                    status_code=400,
                    detail=result.stderr.strip() or "git clone failed",
                )
            if _is_cancel_requested(review_id, run_id):
                _append_review_run_log(
                    review_id, run_id, "system", "warn", "Source acquire canceled"
                )
                return "canceled", {"originUrl": origin_url, "sourceType": source_type}
            extracted_source_path = clone_dir
        else:
            archive_path = tmp_root / "source.archive"
            _download_or_open_local(origin_url, archive_path)
            extract_dir = tmp_root / "source"
            extract_dir.mkdir(parents=True, exist_ok=True)
            _extract_archive_to_dir(archive_path, extract_dir)
            if _is_cancel_requested(review_id, run_id):
                _append_review_run_log(
                    review_id, run_id, "system", "warn", "Source acquire canceled"
                )
                return "canceled", {"originUrl": origin_url, "sourceType": source_type}
            extracted_source_path = extract_dir

        _copy_tree_contents(extracted_source_path, root)

    _append_review_run_log(
        review_id, run_id, "system", "info", "Source acquire succeeded"
    )
    return "succeeded", {"originUrl": origin_url, "sourceType": source_type}


def _run_review_build_runtime(
    review_id: str,
    run_id: str,
    script_relative_path: str,
    runtime_relative_path: str,
) -> tuple[str, dict[str, object]]:
    mount_root = _review_workspace_root(review_id)
    script_abs_path = _resolve_review_relative_path(review_id, script_relative_path)
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Build script not found: {script_relative_path}"
        )

    script_in_container = Path("/workspace") / script_abs_path.relative_to(mount_root)
    runtime_abs_path = _resolve_path_in_root(mount_root, runtime_relative_path)
    runtime_in_container = Path("/workspace") / runtime_abs_path.relative_to(mount_root)

    _append_review_run_log(
        review_id, run_id, "system", "info", f"Build script: {script_relative_path}"
    )
    _append_review_run_log(
        review_id,
        run_id,
        "system",
        "info",
        f"Expected runtime output: {runtime_relative_path}",
    )

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-review-build-{run_id}"
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
        f"{mount_root}/.",
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
            f"cd {shlex.quote(str(script_in_container.parent))}; "
            f"sh {shlex.quote(str(script_in_container))}"
        ),
    ]
    docker_cp_back_cmd = [
        "sudo",
        docker_bin,
        "cp",
        f"{container_name}:{runtime_in_container}",
        str(runtime_abs_path),
    ]
    docker_rm_cmd = ["sudo", docker_bin, "rm", "-f", container_name]

    for cmd in (
        docker_create_cmd,
        docker_cp_cmd,
        docker_start_cmd,
        docker_exec_script_cmd,
    ):
        if _is_cancel_requested(review_id, run_id):
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
            _append_review_run_log(
                review_id, run_id, "system", "warn", "Build run canceled"
            )
            return "canceled", {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
            }
        _append_review_run_log(
            review_id,
            run_id,
            "system",
            "info",
            "$ " + " ".join(shlex.quote(token) for token in cmd),
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        _append_subprocess_output(review_id, run_id, result)
        if result.returncode != 0:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
            return "failed", {
                "buildRuntimeScriptPath": script_relative_path,
                "producedRuntimePath": runtime_relative_path,
                "containerExitCode": result.returncode,
            }

    cp_back_result = subprocess.run(docker_cp_back_cmd, capture_output=True, text=True)
    _append_subprocess_output(review_id, run_id, cp_back_result)
    subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    if cp_back_result.returncode != 0:
        return "failed", {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "containerExitCode": cp_back_result.returncode,
        }

    _append_review_run_log(review_id, run_id, "system", "info", "Build run succeeded")
    return "succeeded", {
        "buildRuntimeScriptPath": script_relative_path,
        "producedRuntimePath": runtime_relative_path,
    }


def _run_review_activation(
    review_id: str,
    run_id: str,
    activation_script_path: str,
) -> tuple[str, dict[str, object]]:
    mount_root = _review_workspace_root(review_id)
    script_abs_path = _resolve_review_relative_path(review_id, activation_script_path)
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Activation script not found: {activation_script_path}",
        )
    script_in_container = Path("/workspace") / script_abs_path.relative_to(mount_root)

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-review-activation-{run_id}"
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
        f"{mount_root}/.",
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
            f"cd {shlex.quote(str(script_in_container.parent))}; "
            f"sh {shlex.quote(str(script_in_container))}"
        ),
    ]
    docker_rm_cmd = ["sudo", docker_bin, "rm", "-f", container_name]

    for cmd in (
        docker_create_cmd,
        docker_cp_cmd,
        docker_start_cmd,
        docker_exec_script_cmd,
    ):
        if _is_cancel_requested(review_id, run_id):
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
            _append_review_run_log(
                review_id, run_id, "system", "warn", "Activation run canceled"
            )
            return "canceled", {"activationScriptPath": activation_script_path}
        _append_review_run_log(
            review_id,
            run_id,
            "system",
            "info",
            "$ " + " ".join(shlex.quote(token) for token in cmd),
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        _append_subprocess_output(review_id, run_id, result)
        if result.returncode != 0:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
            return "failed", {
                "activationScriptPath": activation_script_path,
                "containerExitCode": result.returncode,
            }

    subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    _append_review_run_log(
        review_id, run_id, "system", "info", "Activation run succeeded"
    )
    return "succeeded", {"activationScriptPath": activation_script_path}


@review_ree_router.post("/api/v1/reviews:upload-init")
def review_upload_init_route(payload: ReviewUploadInitPayload):
    try:
        return init_review_upload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@review_ree_router.put("/api/v1/reviews/{review_id}/upload/{upload_token}")
async def review_upload_put_route(review_id: str, upload_token: str, request: Request):
    try:
        data = await request.body()
        return store_review_upload_bytes(review_id, upload_token, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.post("/api/v1/reviews/{review_id}:upload-complete")
def review_upload_complete_route(review_id: str, payload: ReviewUploadCompletePayload):
    try:
        return complete_review_upload(review_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@review_ree_router.get("/api/v1/reviews/{review_id}")
def get_review_route(review_id: str):
    try:
        return get_review(review_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.post("/api/v1/reviews/{review_id}/source:acquire")
def review_source_acquire_route(review_id: str):
    try:
        run_state = _start_background_review_run(
            review_id=review_id,
            operation="source",
            request_payload={"mode": "download"},
            run_id_prefix="review-source",
            runner=_run_review_source_acquire,
        )
        return _review_run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.post("/api/v1/reviews/{review_id}/build-runtime")
def review_build_runtime_route(review_id: str, payload: ReviewBuildRuntimePayload):
    try:
        script_path = _require_non_empty_path(
            payload.build_runtime_script_path, "build_runtime_script_path"
        )
        runtime_path = _require_non_empty_path(
            payload.produced_runtime_path, "produced_runtime_path"
        )
        run_state = _start_background_review_run(
            review_id=review_id,
            operation="build",
            request_payload={
                "build_runtime_script_path": script_path,
                "produced_runtime_path": runtime_path,
            },
            run_id_prefix="review-build",
            runner=lambda rid, run_id: _run_review_build_runtime(
                rid, run_id, script_path, runtime_path
            ),
        )
        return _review_run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.post("/api/v1/reviews/{review_id}/activation-test")
def review_activation_route(review_id: str, payload: ReviewActivationTestPayload):
    try:
        script_path = _require_non_empty_path(
            payload.activation_script_path, "activation_script_path"
        )
        run_state = _start_background_review_run(
            review_id=review_id,
            operation="activation",
            request_payload={"activation_script_path": script_path},
            run_id_prefix="review-activation",
            runner=lambda rid, run_id: _run_review_activation(rid, run_id, script_path),
        )
        return _review_run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.get("/api/v1/reviews/{review_id}/runs/{run_id}")
def review_run_get_route(review_id: str, run_id: str):
    run_state = _get_review_run_state(review_id, run_id)
    return _review_run_summary(run_state)


@review_ree_router.get("/api/v1/reviews/{review_id}/runs/{run_id}/logs")
def review_run_logs_route(
    review_id: str,
    run_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
):
    run_state = _get_review_run_state(review_id, run_id)
    logs = run_state.get("logs", [])
    page, next_cursor, has_more = _paginate(logs, cursor=cursor, limit=limit)
    return {
        "entries": page,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "runStatus": run_state["status"],
    }


@review_ree_router.post("/api/v1/reviews/{review_id}/runs/{run_id}:cancel")
def review_run_cancel_route(review_id: str, run_id: str):
    run_state = _get_review_run_state(review_id, run_id)
    current_status = run_state.get("status")
    if current_status in {"succeeded", "failed", "canceled"}:
        return {"status": current_status}

    _mark_review_cancel_requested(review_id, run_id)
    _append_review_run_log(
        review_id,
        run_id,
        "system",
        "warn",
        "Cancel requested by user",
    )

    operation = run_state.get("operation")
    docker_bin = shutil.which("docker") or "docker"
    if operation == "build":
        container_name = f"repo2ree-review-build-{run_id}"
        try:
            subprocess.run(
                ["sudo", docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
    elif operation == "activation":
        container_name = f"repo2ree-review-activation-{run_id}"
        try:
            subprocess.run(
                ["sudo", docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    refreshed = _get_review_run_state(review_id, run_id)
    return {"status": refreshed["status"]}
