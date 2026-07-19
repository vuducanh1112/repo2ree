from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file
from repo2ree_core.receipts import CrossCheckSbomReceipt, receipt_run_id, record_receipt
from repo2ree_core.repo_profiler.reproducibility_report import (
    ReproducibilityReport,
    SbomCrossCheckSummary,
)
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.sbom.crosscheck import cross_check
from repo2ree_core.sbom.cyclonedx import parse_cyclonedx
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
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
    store = ReeStore(layout)

    sbom_rel = store.read_intent().sbom or "sbom.json"
    sbom_abs = layout.workspace / sbom_rel
    if not sbom_abs.is_file():
        log("system", "error", f"SBOM not found: {sbom_rel} — run generate-sbom first")
        return ActionResult(status="failed", exit_code=1)

    report_path = layout.artifacts / _REPORT_FILENAME
    if not report_path.is_file():
        log("system", "error", "No reproducibility report — run evaluate first")
        return ActionResult(status="failed", exit_code=1)

    sbom_digest = digest_file(sbom_abs)

    def receipt(status: ActionStatus, counts: SbomCrossCheckSummary | None = None) -> CrossCheckSbomReceipt:
        aggregates = counts or SbomCrossCheckSummary()
        built = CrossCheckSbomReceipt(
            run_id=receipt_run_id(run_id),
            recorded_at=utc_now(),
            status=status,
            sbom_digest=sbom_digest,
            declared_direct_total=aggregates.declared_direct_total,
            observed_matched=aggregates.observed_matched,
            version_mismatches=aggregates.version_mismatches,
            undeclared_same_ecosystem=aggregates.undeclared_same_ecosystem,
            observed_total=aggregates.observed_total,
        )
        record_receipt(layout, built, log=log)
        return built

    try:
        report = ReproducibilityReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))
    except Exception as exc:
        log("system", "error", f"unreadable reproducibility report: {exc}")
        receipt("failed")
        return ActionResult(status="failed", exit_code=1)

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
        log("system", "warn", "cross_check_sbom canceled")
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
        return ActionResult(status="failed", exit_code=1)

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
        sbom_relative_path=str(sbom_rel),
        cross_check=summary.model_dump(),
        receipt=recorded.model_dump(),
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
