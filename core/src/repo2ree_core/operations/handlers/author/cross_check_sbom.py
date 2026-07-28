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
from repo2ree_core.evidence.receipts.models import CrossCheckSbomReceipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import log_step_outcome, settle_step
from repo2ree_core.ree.files import write_json_atomic
from repo2ree_core.ree.layout import REPRODUCIBILITY_REPORT_FILENAME, SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import UNREADABLE_DOCUMENT
from repo2ree_core.time_utils import OperationTimer, utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus

_OPERATION = "cross_check_sbom"


class CrossCheckSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_relative_path: str
    sbom_relative_path: str
    # The cross-check summary (an SbomCrossCheckSummary dump); kept as a dict
    # here because the outputs envelope stays JSON.
    cross_check: dict[str, Any]
    receipt: CrossCheckSbomReceipt


def handle_cross_check_sbom(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()

    # The SBOM's home is fixed, so this reads it rather than resolving whatever
    # the intent declares: a baseline loaded from a bundle lands its SBOM in the
    # same artifacts/ slot the author's scan wrote, and cross-checks identically.
    sbom_abs = layout.sbom
    sbom_rel = SBOM_ARTIFACT_PATH
    if not sbom_abs.is_file():
        log("system", "error", f"SBOM not found: {sbom_rel} — run generate-sbom first")
        return ActionResult.failed("precondition", f"SBOM not found: {sbom_rel} — run generate-sbom first")

    report_path = layout.reproducibility_report
    if not report_path.is_file():
        log("system", "error", "No reproducibility report — run evaluate first")
        return ActionResult.failed("precondition", "No reproducibility report — run evaluate first")

    timer = OperationTimer.start()
    sbom_digest = digest_file(sbom_abs)

    def receipt(status: ActionStatus, counts: SbomCrossCheckSummary | None = None) -> CrossCheckSbomReceipt:
        """Settle this step, on whichever of its three exits reached here."""
        aggregates = counts or SbomCrossCheckSummary()
        return settle_step(
            layout,
            lambda envelope: CrossCheckSbomReceipt(
                **envelope,
                sbom_digest=sbom_digest,
                declared_direct_total=aggregates.declared_direct_total,
                observed_matched=aggregates.observed_matched,
                version_mismatches=aggregates.version_mismatches,
                undeclared_same_ecosystem=aggregates.undeclared_same_ecosystem,
                observed_total=aggregates.observed_total,
            ),
            operation=_OPERATION,
            run_id=run_id,
            timer=timer,
            status=status,
            log=log,
        )

    try:
        report = ReproducibilityReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))
    except UNREADABLE_DOCUMENT as exc:
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

    # Nothing has been written yet, so a cancel here leaves no half-updated
    # report behind and needs no receipt to say what it left.
    if is_canceled():
        log_step_outcome(_OPERATION, "canceled", timer.finish(), log=log)
        return ActionResult(status="canceled")

    try:
        report.dependencies = result.dependencies
        report.sbom_cross_check = summary
        # Read-modify-write of the evaluate step's report: a torn write here
        # would lose that step's work too, not just this one's, and leave a
        # present-but-unparseable file that fails this handler's own
        # precondition on the next run.
        write_json_atomic(report_path, report.model_dump())
    except OSError as exc:
        log("system", "error", f"failed to persist cross-checked report: {exc}")
        receipt("failed")
        return failed_from_exception(exc, f"failed to persist cross-checked report: {exc}")

    log(
        "system",
        "info",
        f"Cross-check succeeded: {summary.observed_matched}/{summary.declared_direct_total} "
        f"declared deps observed, {summary.version_mismatches} version mismatches, "
        f"{summary.undeclared_same_ecosystem} undeclared",
    )
    recorded = receipt("succeeded", counts=summary)
    outputs = CrossCheckSbomOutputs(
        report_relative_path=REPRODUCIBILITY_REPORT_FILENAME,
        sbom_relative_path=sbom_rel,
        cross_check=summary.model_dump(),
        receipt=recorded,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
