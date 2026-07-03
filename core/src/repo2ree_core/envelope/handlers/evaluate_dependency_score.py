from __future__ import annotations

import json

from repo2ree_core.repo_profiler.profiler import AnalysisError, analyze_repo
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.command import EvaluateDependencyScoreArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_REPORT_FILENAME = "reproducibility-report.json"


def handle_evaluate_dependency_score(
    args: EvaluateDependencyScoreArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "evaluate_dependency_score canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    log("system", "info", f"Workspace: {layout.workspace.resolve()}")
    try:
        report = analyze_repo(layout.workspace.resolve(), log=log, strict=args.strict)
    except AnalysisError as exc:
        log("system", "error", str(exc))
        return ActionResult(status="failed", exit_code=1)
    except Exception as exc:
        log("system", "error", f"evaluate_dependency_score failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    if is_canceled():
        log("system", "warn", "evaluate_dependency_score canceled")
        return ActionResult(status="canceled")

    try:
        layout.artifacts.mkdir(parents=True, exist_ok=True)
        report_path = layout.artifacts / _REPORT_FILENAME
        report_path.write_text(
            json.dumps(report.model_dump(by_alias=True), indent=2),
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
        return ActionResult(status="failed", exit_code=1)

    outputs = {
        "dependencyCount": report.dependency_summary.total,
        "manifestCount": report.dependency_summary.manifests,
        "dependencyLevel": int(report.dependency_level),
        "environmentLevel": int(report.environment_level),
        "machineLevel": int(report.machine_level),
        "detectedDependencies": report.detected_dependencies,
        "report": report.model_dump(by_alias=True),
    }
    log("system", "info", "Evaluate run succeeded")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)
