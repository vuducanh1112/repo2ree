from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.repo_profiler.profiler import AnalysisError, analyze_repo
from repo2ree_core.repo_profiler.reproducibility_report import ReproducibilityReport

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


# ================================================
# Router
# ================================================


evaluate_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateEvaluateRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = False
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


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


# ================================================
# Helpers
# ================================================


_REPORT_FILENAME = "reproducibility-report.json"


def _report_path(ree_id: str) -> Path:
    return artifact_dir(ree_id) / _REPORT_FILENAME


def _write_report_file(ree_id: str, report: ReproducibilityReport) -> None:
    path = _report_path(ree_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(by_alias=True), indent=2),
        encoding="utf-8",
    )


def create_evaluate_run_state(
    ree_id: str,
    payload: CreateEvaluateRunPayload,
) -> dict[str, Any]:
    request_payload = {"strict": bool(payload.strict)}

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        workspace_path = workspace_dir(ree_id).resolve()
        _append_run_log(
            ree_id, run_id, "system", "info", f"Starting evaluate run {run_id}"
        )
        _append_run_log(
            ree_id, run_id, "system", "info", f"Workspace: {workspace_path}"
        )

        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Evaluate run canceled")
            return "canceled", {}

        def log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        try:
            report = analyze_repo(workspace_path, log=log, strict=bool(payload.strict))
        except AnalysisError as exc:
            _append_run_log(ree_id, run_id, "system", "error", str(exc))
            return "failed", {}

        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Evaluate run canceled")
            return "canceled", {}

        _write_report_file(ree_id, report)
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
        outputs = {
            "dependencyCount": report.dependency_summary.total,
            "manifestCount": report.dependency_summary.manifests,
            "dependencyLevel": int(report.dependency_level),
            "environmentLevel": int(report.environment_level),
            "machineLevel": int(report.machine_level),
            "detectedDependencies": report.detected_dependencies,
            "report": report.model_dump(by_alias=True),
        }
        _append_run_log(ree_id, run_id, "system", "info", "Evaluate run succeeded")
        return "succeeded", outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="evaluate",
        request_payload=request_payload,
        run_id_prefix="evaluate",
        runner=_runner,
    )
