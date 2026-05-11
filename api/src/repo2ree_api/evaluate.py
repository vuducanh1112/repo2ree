from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    WorkspacePatchPayload,
    patch_workspace,
    read_workspace_metadata,
    workspace_dir,
)


evaluate_router = APIRouter()

_LEVEL_LABELS = (
    "None",
    "Natural Language",
    "Manifest File",
    "Top-level Pins",
    "Dependencies Locked",
    "Container Env",
    "Declarative System",
    "Beyond",
)


class CreateEvaluateRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = False
    swhid_check: bool = True
    idempotencyKey: str | None = None


def _is_workspace_control_file(path: Path) -> bool:
    return path.name.startswith(".workspace") or path.name.startswith(".upload.")


def _iter_workspace_source_files(workspace_path: Path):
    for file_path in sorted(workspace_path.rglob("*")):
        if not file_path.is_file():
            continue
        if _is_workspace_control_file(file_path):
            continue
        yield file_path


def _extract_json_object_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    marker_pos = text.find(marker)
    if marker_pos < 0:
        return None
    json_start = text.find("{", marker_pos)
    if json_start < 0:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[json_start:])
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_renovate_dependencies(renovate_stdout: str) -> dict[str, Any] | None:
    return _extract_json_object_after_marker(
        renovate_stdout,
        "Extracted dependencies (repository=local)",
    )


def _is_exact_pin(version: str | None) -> bool:
    if not version:
        return False
    normalized = version.strip()
    if not normalized:
        return False
    if normalized.startswith("=="):
        return True
    if any(token in normalized for token in ("<", ">", "~", "^", "*", "||", ",")):
        return False
    return bool(re.match(r"^[0-9][A-Za-z0-9._+\-]*$", normalized))


def _analyze_workspace_files(workspace_path: Path) -> dict[str, bool]:
    has_readme = False
    has_manifest = False
    has_dockerfile = False
    has_nix_file = False
    has_beyond_signals = False

    for file_path in _iter_workspace_source_files(workspace_path):
        lower_name = file_path.name.lower()
        if lower_name in {"readme.md", "readme.txt", "readme.rst"}:
            has_readme = True

        if (
            lower_name == "requirements.txt"
            or lower_name == "pyproject.toml"
            or lower_name in {"environment.yml", "environment.yaml"}
            or lower_name == "package.json"
            or lower_name == "pipfile"
            or re.match(r"^requirements[-_].+\.txt$", lower_name)
        ):
            has_manifest = True

        if (
            lower_name == "dockerfile"
            or lower_name == "containerfile"
            or lower_name.startswith("dockerfile.")
            or lower_name.startswith("containerfile.")
            or lower_name in {"docker-compose.yml", "docker-compose.yaml"}
        ):
            has_dockerfile = True

        if lower_name.endswith(".nix"):
            has_nix_file = True

        if any(
            token in lower_name
            for token in ("reproduc", "determin", "provenance", "hardware", "swhid")
        ):
            has_beyond_signals = True

    return {
        "hasReadme": has_readme,
        "hasManifest": has_manifest,
        "hasDockerfile": has_dockerfile,
        "hasNixFile": has_nix_file,
        "hasBeyondSignals": has_beyond_signals,
    }


def _analyze_dependencies(renovate_payload: dict[str, Any] | None) -> dict[str, Any]:
    package_files: dict[str, Any] = {}
    if isinstance(renovate_payload, dict):
        package_files = renovate_payload.get("packageFiles") or {}
    if not isinstance(package_files, dict):
        package_files = {}

    manifest_count = len(package_files)
    dependency_count = 0
    has_exact_pins = False
    has_locked_dependencies = False

    for manager_files in package_files.values():
        if not isinstance(manager_files, list):
            continue
        for package_file in manager_files:
            if not isinstance(package_file, dict):
                continue
            deps = package_file.get("deps") or []
            if not isinstance(deps, list):
                continue
            dependency_count += len(deps)
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                if dep.get("lockedVersion"):
                    has_locked_dependencies = True
                if _is_exact_pin(dep.get("currentValue")):
                    has_exact_pins = True

    return {
        "manifestCount": manifest_count,
        "dependencyCount": dependency_count,
        "hasExactPins": has_exact_pins,
        "hasLockedDependencies": has_locked_dependencies,
    }


def _compute_level(
    file_signals: dict[str, bool],
    dependency_signals: dict[str, Any],
    has_swhid: bool,
    swhid_check: bool,
) -> int:
    level = 0
    if file_signals["hasReadme"]:
        level = 1
    if file_signals["hasManifest"] or dependency_signals["manifestCount"] > 0:
        level = 2
    if dependency_signals["hasExactPins"]:
        level = 3
    if dependency_signals["hasLockedDependencies"]:
        level = 4
    if file_signals["hasDockerfile"]:
        level = 5
    if file_signals["hasNixFile"]:
        level = 6
    if file_signals["hasNixFile"] and (
        file_signals["hasBeyondSignals"] or (swhid_check and has_swhid)
    ):
        level = 7
    return max(0, min(level, len(_LEVEL_LABELS) - 1))


def _compute_evaluate_outputs(
    ree_id: str,
    strict: bool,
    swhid_check: bool,
    renovate_stdout: str,
    renovate_exit_code: int,
) -> dict[str, Any]:
    workspace_path = workspace_dir(ree_id).resolve()
    metadata = read_workspace_metadata(ree_id)
    ree_draft = metadata.get("reeDraft") or {}
    has_swhid = bool(str(ree_draft.get("swhid") or "").strip())

    file_signals = _analyze_workspace_files(workspace_path)
    renovate_payload = _extract_renovate_dependencies(renovate_stdout)
    if strict and renovate_payload is None:
        raise RuntimeError(
            "Renovate output did not include an extractable dependencies payload"
        )

    dependency_signals = _analyze_dependencies(renovate_payload)
    level = _compute_level(
        file_signals=file_signals,
        dependency_signals=dependency_signals,
        has_swhid=has_swhid,
        swhid_check=swhid_check,
    )

    dependency_count = int(dependency_signals["dependencyCount"])
    manifest_count = int(dependency_signals["manifestCount"])
    summary = (
        f"{dependency_count} dependenc{'y' if dependency_count == 1 else 'ies'} across "
        f"{manifest_count} manifest file{'s' if manifest_count != 1 else ''}"
    )
    repro_level = f"L{level} · {_LEVEL_LABELS[level]}"

    patch_workspace(
        ree_id,
        WorkspacePatchPayload(
            reePatch={
                "eval_level": level,
                "repro_level": repro_level,
                "detected_dependencies": summary,
            }
        ),
    )

    return {
        "renovateExitCode": renovate_exit_code,
        "dependencyCount": dependency_count,
        "manifestCount": manifest_count,
        "hasDockerfile": file_signals["hasDockerfile"],
        "hasNixFile": file_signals["hasNixFile"],
        "evalLevel": level,
        "reproLevel": repro_level,
        "detectedDependencies": summary,
    }


def create_evaluate_run_state(
    ree_id: str,
    payload: CreateEvaluateRunPayload,
) -> dict[str, Any]:
    request_payload = {
        "strict": bool(payload.strict),
        "swhid_check": bool(payload.swhid_check),
    }

    def _runner(ws_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        workspace_path = workspace_dir(ws_id).resolve()
        _append_run_log(
            ws_id, run_id, "system", "info", f"Starting evaluate run {run_id}"
        )
        _append_run_log(
            ws_id,
            run_id,
            "system",
            "info",
            f"Workspace source directory: {workspace_path}",
        )

        command = ["renovate", "--platform=local", "--dry-run=extract"]
        _append_run_log(
            ws_id,
            run_id,
            "system",
            "info",
            "$ " + " ".join(shlex.quote(part) for part in command),
        )

        if _is_cancel_requested(ws_id, run_id):
            _append_run_log(ws_id, run_id, "system", "warn", "Evaluate run canceled")
            return "canceled", {}

        env = os.environ.copy()
        env["LOG_LEVEL"] = "info"
        completed = subprocess.run(
            command,
            cwd=str(workspace_path),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        for line in completed.stdout.splitlines():
            if line.strip():
                _append_run_log(ws_id, run_id, "stdout", "info", line)
        for line in completed.stderr.splitlines():
            if line.strip():
                _append_run_log(ws_id, run_id, "stderr", "warn", line)

        if _is_cancel_requested(ws_id, run_id):
            _append_run_log(ws_id, run_id, "system", "warn", "Evaluate run canceled")
            return "canceled", {"renovateExitCode": completed.returncode}

        if completed.returncode != 0:
            _append_run_log(
                ws_id,
                run_id,
                "system",
                "error",
                f"Renovate failed (exit code {completed.returncode})",
            )
            outputs = _compute_evaluate_outputs(
                ree_id=ws_id,
                strict=False,
                swhid_check=bool(payload.swhid_check),
                renovate_stdout=completed.stdout,
                renovate_exit_code=completed.returncode,
            )
            return "failed", outputs

        outputs = _compute_evaluate_outputs(
            ree_id=ws_id,
            strict=bool(payload.strict),
            swhid_check=bool(payload.swhid_check),
            renovate_stdout=completed.stdout,
            renovate_exit_code=completed.returncode,
        )
        _append_run_log(ws_id, run_id, "system", "info", "Evaluate run succeeded")
        return "succeeded", outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="evaluate",
        request_payload=request_payload,
        run_id_prefix="evaluate",
        runner=_runner,
    )


@evaluate_router.post("/api/v1/rees/{ree_id}/evaluate")
def create_workspace_evaluate_run(ree_id: str, payload: CreateEvaluateRunPayload):
    run_state = create_evaluate_run_state(ree_id, payload)
    return _run_summary(run_state)
