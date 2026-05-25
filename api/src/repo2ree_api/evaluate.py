from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.repo_profiler.reproducibility_report import (
    FileSignals,
    ReproducibilityReport,
    build_report,
    is_dockerfile_filename,
    is_manifest_filename,
    is_vm_artifact_filename,
    parse_renovate_stdout,
)

from repo2ree_api.api_utils import append_completed_process_output
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    WorkspacePatchPayload,
    artifact_dir,
    patch_workspace,
    workspace_dir,
)


evaluate_router = APIRouter()

_REPORT_FILENAME = "reproducibility-report.json"


def _report_path(ree_id: str) -> Path:
    return artifact_dir(ree_id) / _REPORT_FILENAME


class CreateEvaluateRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = False
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


def _analyze_workspace_files(workspace_path: Path) -> FileSignals:
    signals = FileSignals()
    for file_path in _iter_workspace_source_files(workspace_path):
        lower_name = file_path.name.lower()
        if is_manifest_filename(lower_name):
            signals.has_manifest = True
        if is_dockerfile_filename(lower_name):
            signals.has_dockerfile = True
            try:
                signals.dockerfile_texts.append(
                    file_path.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                pass
        if lower_name.endswith(".nix"):
            signals.has_nix_file = True
        if is_vm_artifact_filename(lower_name):
            signals.has_vm = True
    return signals


def _write_report_file(ree_id: str, report: ReproducibilityReport) -> None:
    path = _report_path(ree_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(by_alias=True), indent=2),
        encoding="utf-8",
    )


def _compute_evaluate_outputs(
    ree_id: str,
    strict: bool,
    renovate_stdout: str,
    renovate_exit_code: int,
) -> dict[str, Any]:
    workspace_path = workspace_dir(ree_id).resolve()
    file_signals = _analyze_workspace_files(workspace_path)
    renovate_payload = parse_renovate_stdout(renovate_stdout)
    if strict and renovate_payload is None:
        raise RuntimeError(
            "Renovate output did not include an extractable dependencies payload"
        )
    report = build_report(renovate_payload=renovate_payload, file_signals=file_signals)
    _write_report_file(ree_id, report)
    # The draft keeps the per-axis standing for the rest of the UI; the full threat
    # report lives in its own artifact file (see GET .../evaluate/report).
    patch_workspace(
        ree_id,
        WorkspacePatchPayload(
            reePatch={
                "dependency_level": int(report.dependency_level),
                "environment_level": int(report.environment_level),
                "machine_level": int(report.machine_level),
                "detected_dependencies": report.detected_dependencies,
            }
        ),
    )
    return {
        "renovateExitCode": renovate_exit_code,
        "dependencyCount": report.dependency_summary.total,
        "manifestCount": report.dependency_summary.manifests,
        "dependencyLevel": int(report.dependency_level),
        "environmentLevel": int(report.environment_level),
        "machineLevel": int(report.machine_level),
        "detectedDependencies": report.detected_dependencies,
        "report": report.model_dump(by_alias=True),
    }


def create_evaluate_run_state(
    ree_id: str,
    payload: CreateEvaluateRunPayload,
) -> dict[str, Any]:
    request_payload = {
        "strict": bool(payload.strict),
    }

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        workspace_path = workspace_dir(ree_id).resolve()
        _append_run_log(
            ree_id, run_id, "system", "info", f"Starting evaluate run {run_id}"
        )
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "info",
            f"Workspace source directory: {workspace_path}",
        )

        command = ["renovate", "--platform=local", "--dry-run=extract"]
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "info",
            "$ " + " ".join(shlex.quote(part) for part in command),
        )

        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Evaluate run canceled")
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

        append_completed_process_output(
            completed,
            lambda stream, level, message: _append_run_log(
                ree_id, run_id, stream, level, message
            ),
        )

        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Evaluate run canceled")
            return "canceled", {"renovateExitCode": completed.returncode}

        if completed.returncode != 0:
            _append_run_log(
                ree_id,
                run_id,
                "system",
                "error",
                f"Renovate failed (exit code {completed.returncode})",
            )
            outputs = _compute_evaluate_outputs(
                ree_id=ree_id,
                strict=False,
                renovate_stdout=completed.stdout,
                renovate_exit_code=completed.returncode,
            )
            return "failed", outputs

        outputs = _compute_evaluate_outputs(
            ree_id=ree_id,
            strict=bool(payload.strict),
            renovate_stdout=completed.stdout,
            renovate_exit_code=completed.returncode,
        )
        _append_run_log(ree_id, run_id, "system", "info", "Evaluate run succeeded")
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


@evaluate_router.get("/api/v1/rees/{ree_id}/evaluate/report")
def get_workspace_evaluate_report(ree_id: str) -> dict[str, Any]:
    path = _report_path(ree_id)
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="No reproducibility report; run evaluate first"
        )
    return json.loads(path.read_text(encoding="utf-8"))
