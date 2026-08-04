"""Evaluate repository reproducibility and commit its successful receipt."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.repository.profiler import AnalysisError, analyze_repo
from repo2ree_core.digests import digest_file, digest_tree
from repo2ree_core.domain.primitives import ArtifactPath
from repo2ree_core.domain.ree.receipt import EvaluateReproducibilityReceipt, receipt_envelope
from repo2ree_core.domain.ree.transitions import commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.layout import ARTIFACTS_DIRNAME, REPRODUCIBILITY_REPORT_FILENAME, ReeLayout
from repo2ree_core.persistence.repository import load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.command import EvaluateDependencyScoreArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_ANALYZER_VERSION = "1"
_REPORT_PATH = ArtifactPath(f"{ARTIFACTS_DIRNAME}/{REPRODUCIBILITY_REPORT_FILENAME}")


class EvaluateOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependency_count: int
    manifest_count: int
    dependency_level: int
    environment_level: int
    machine_level: int
    detected_dependencies: str
    report: dict[str, Any]


def handle_evaluate_dependency_score(
    args: EvaluateDependencyScoreArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")

    try:
        ree = load_ree(layout, store)
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load REE: {exc}")
    if ree.seal is not None:
        return ActionResult.failed("precondition", "a sealed REE cannot be evaluated")
    source = ree.subject.receipts.source
    if source is None:
        return ActionResult.failed("precondition", "source has not been acquired")

    before_revision = revision_of(ree)
    timer = OperationTimer.start()
    log("system", "info", f"Workspace: {layout.workspace.resolve()}")
    try:
        report = analyze_repo(layout.workspace.resolve(), log=log, strict=args.strict)
    except AnalysisError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("execution", str(exc))
    except Exception as exc:
        log("system", "error", f"evaluate_dependency_score failed: {exc}")
        return failed_from_exception(exc, f"evaluate_dependency_score failed: {exc}")

    if is_canceled():
        log("system", "warn", "evaluate_dependency_score canceled")
        return ActionResult(status="canceled")

    try:
        write_json_atomic(layout.reproducibility_report, report.model_dump())
        timing = timer.finish()
        receipt = EvaluateReproducibilityReceipt(
            **receipt_envelope(run_id, timing),
            snapshot_digest=source.snapshot_digest,
            overlay_digest=digest_tree(layout.overlay),
            strict=args.strict,
            dependency_level=int(report.dependency_level),
            environment_level=int(report.environment_level),
            machine_level=int(report.machine_level),
            dependency_count=report.dependency_summary.total,
            manifest_count=report.dependency_summary.manifests,
            report_path=_REPORT_PATH,
            report_digest=digest_file(layout.reproducibility_report),
            analyzer_version=_ANALYZER_VERSION,
        )
        save_ree(
            layout,
            store,
            commit_receipt(ree, receipt),
            expected_revision=before_revision,
        )
    except Exception as exc:
        log("system", "error", f"failed to persist evaluation outputs: {exc}")
        return failed_from_exception(exc, f"failed to persist evaluation outputs: {exc}")

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
