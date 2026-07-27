from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.repository.profiler import AnalysisError, analyze_repo
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_protocol.command import EvaluateDependencyScoreArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class EvaluateOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependency_count: int
    manifest_count: int
    dependency_level: int
    environment_level: int
    machine_level: int
    detected_dependencies: str
    # The full evaluate report (a ReproducibilityReport dump); kept as a dict
    # here because the outputs envelope stays JSON.
    report: dict[str, Any]


def handle_evaluate_dependency_score(
    args: EvaluateDependencyScoreArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    log("system", "info", f"Workspace: {layout.workspace.resolve()}")
    try:
        report = analyze_repo(layout.workspace.resolve(), log=log, strict=args.strict)
    except AnalysisError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("execution", str(exc))
    except Exception as exc:
        log("system", "error", f"evaluate_dependency_score failed: {exc}")
        return ActionResult.failed("internal", f"evaluate_dependency_score failed: {exc}")

    if is_canceled():
        log("system", "warn", "evaluate_dependency_score canceled")
        return ActionResult(status="canceled")

    try:
        layout.artifacts.mkdir(parents=True, exist_ok=True)
        report_path = layout.reproducibility_report
        report_path.write_text(
            json.dumps(report.model_dump(), indent=2),
            encoding="utf-8",
        )
        store = ReeStore(layout)
        session = store.read_session().with_evaluation(
            dependency_level=int(report.dependency_level),
            environment_level=int(report.environment_level),
            machine_level=int(report.machine_level),
            detected_dependencies=report.detected_dependencies,
        )
        store.write_session(session)
    except Exception as exc:
        log("system", "error", f"failed to persist evaluation outputs: {exc}")
        return ActionResult.failed("internal", f"failed to persist evaluation outputs: {exc}")

    outputs = EvaluateOutputs(
        dependency_count=report.dependency_summary.total,
        manifest_count=report.dependency_summary.manifests,
        dependency_level=int(report.dependency_level),
        environment_level=int(report.environment_level),
        machine_level=int(report.machine_level),
        detected_dependencies=report.detected_dependencies,
        report=report.model_dump(),
    )
    log("system", "info", "Evaluate run succeeded")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
