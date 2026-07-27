from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.repository.reproducibility_report import (
    ReproducibilityReport,
    SbomCrossCheckSummary,
)
from repo2ree_core.analysis.sbom.crosscheck import cross_check
from repo2ree_core.analysis.sbom.cyclonedx import parse_cyclonedx
from repo2ree_core.digests import digest_file
from repo2ree_core.evidence.receipts.models import CrossCheckSbomReceipt, receipt_envelope
from repo2ree_core.evidence.receipts.store import record_receipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.time_utils import OperationTimer, format_duration_ms, utc_now
from repo2ree_protocol.command import CrossCheckSbomArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus

_REPORT_FILENAME = "reproducibility-report.json"


class CrossCheckSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_relative_path: str
    sbom_relative_path: str
    # The cross-check summary (an SbomCrossCheckSummary dump); kept as a dict
    # here because the outputs envelope stays JSON.
    cross_check: dict[str, Any]
    receipt: dict[str, Any]


def handle_cross_check_sbom(
    args: CrossCheckSbomArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "cross_check_sbom canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()

    # The SBOM's home is fixed, so this reads it rather than resolving whatever
    # the intent declares: a baseline loaded from a bundle lands its SBOM in the
    # same artifacts/ slot the author's scan wrote, and cross-checks identically.
    sbom_abs = layout.sbom
    sbom_rel = SBOM_ARTIFACT_PATH
    if not sbom_abs.is_file():
        log("system", "error", f"SBOM not found: {sbom_rel} — run generate-sbom first")
        return ActionResult.failed("precondition", f"SBOM not found: {sbom_rel} — run generate-sbom first")

    report_path = layout.artifacts / _REPORT_FILENAME
    if not report_path.is_file():
        log("system", "error", "No reproducibility report — run evaluate first")
        return ActionResult.failed("precondition", "No reproducibility report — run evaluate first")

    timer = OperationTimer.start()
    sbom_digest = digest_file(sbom_abs)

    def receipt(status: ActionStatus, counts: SbomCrossCheckSummary | None = None) -> CrossCheckSbomReceipt:
        aggregates = counts or SbomCrossCheckSummary()
        timing = timer.finish()
        built = CrossCheckSbomReceipt(
            **receipt_envelope(run_id, timing, status),
            sbom_digest=sbom_digest,
            declared_direct_total=aggregates.declared_direct_total,
            observed_matched=aggregates.observed_matched,
            version_mismatches=aggregates.version_mismatches,
            undeclared_same_ecosystem=aggregates.undeclared_same_ecosystem,
            observed_total=aggregates.observed_total,
        )
        record_receipt(layout, built, log=log)
        log(
            "system",
            "info" if status == "succeeded" else "error",
            f"cross_check_sbom {status} in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return built

    try:
        report = ReproducibilityReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))
    except Exception as exc:
        log("system", "error", f"unreadable reproducibility report: {exc}")
        receipt("failed")
        return ActionResult.failed("internal", f"unreadable reproducibility report: {exc}")

    observed = parse_cyclonedx(sbom_abs.read_text(encoding="utf-8"))
    log("system", "info", f"SBOM: {sbom_rel} — {len(observed)} observed packages")
    # Cross-check declared rows only: rows a previous cross-check added would
    # otherwise mask their packages as "declared".
    declared_rows = [dep for dep in report.dependencies if dep.status != "undeclared"]
    result = cross_check(declared_rows, observed)

    summary = result.summary
    summary.sbom_digest = sbom_digest
    summary.checked_at = utc_now()

    if is_canceled():
        timing = timer.finish()
        log(
            "system",
            "warn",
            f"cross_check_sbom canceled in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return ActionResult(status="canceled")

    try:
        report.dependencies = result.dependencies
        report.sbom_cross_check = summary
        report_path.write_text(
            json.dumps(report.model_dump(), indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        log("system", "error", f"failed to persist cross-checked report: {exc}")
        receipt("failed")
        return ActionResult.failed("internal", f"failed to persist cross-checked report: {exc}")

    log(
        "system",
        "info",
        f"Cross-check succeeded: {summary.observed_matched}/{summary.declared_direct_total} "
        f"declared deps observed, {summary.version_mismatches} version mismatches, "
        f"{summary.undeclared_same_ecosystem} undeclared",
    )
    recorded = receipt("succeeded", counts=summary)
    outputs = CrossCheckSbomOutputs(
        report_relative_path=_REPORT_FILENAME,
        sbom_relative_path=sbom_rel,
        cross_check=summary.model_dump(),
        receipt=recorded.model_dump(),
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
