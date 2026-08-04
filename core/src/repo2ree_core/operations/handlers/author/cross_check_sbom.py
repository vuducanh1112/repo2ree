"""Cross-check selected SBOM evidence against the reproducibility analysis."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.repository.reproducibility_report import ReproducibilityReport
from repo2ree_core.analysis.sbom.crosscheck import cross_check
from repo2ree_core.analysis.sbom.cyclonedx import parse_cyclonedx
from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.receipt import CrossCheckSbomReceipt, receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import REPRODUCIBILITY_REPORT_FILENAME, SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class CrossCheckSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_relative_path: str
    sbom_relative_path: str
    cross_check: dict[str, Any]
    receipt: CrossCheckSbomReceipt


def handle_cross_check_sbom(
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
        _check_preconditions(ree, layout)
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", f"cannot cross-check SBOM: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load cross-check inputs: {exc}")

    before_revision = revision_of(ree)
    timer = OperationTimer.start()
    try:
        report = ReproducibilityReport.model_validate(
            json.loads(layout.reproducibility_report.read_text(encoding="utf-8"))
        )
        observed = parse_cyclonedx(layout.sbom.read_text(encoding="utf-8"))
    except UNREADABLE_DOCUMENT as exc:
        return ActionResult.failed("validation", f"unreadable cross-check input: {exc}")

    declared_rows = [dependency for dependency in report.dependencies if dependency.status != "undeclared"]
    result = cross_check(declared_rows, observed)
    summary = result.summary
    summary.sbom_digest = digest_file(layout.sbom)
    summary.checked_at = utc_now()
    if is_canceled():
        return ActionResult(status="canceled")

    timing = timer.finish()
    receipt = CrossCheckSbomReceipt(
        **receipt_envelope(run_id, timing),
        sbom_digest=digest_file(layout.sbom),
        report_digest=digest_file(layout.reproducibility_report),
        declared_direct_total=summary.declared_direct_total,
        observed_matched=summary.observed_matched,
        version_mismatches=summary.version_mismatches,
        undeclared_same_ecosystem=summary.undeclared_same_ecosystem,
        observed_total=summary.observed_total,
    )
    try:
        save_ree(layout, store, commit_receipt(ree, receipt), expected_revision=before_revision)
    except ReeRevisionConflictError as exc:
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        return failed_from_exception(exc, f"failed to commit SBOM cross-check: {exc}")

    outputs = CrossCheckSbomOutputs(
        report_relative_path=REPRODUCIBILITY_REPORT_FILENAME,
        sbom_relative_path=SBOM_ARTIFACT_PATH,
        cross_check=summary.model_dump(),
        receipt=receipt,
    )
    log("system", "info", "cross_check_sbom succeeded")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _check_preconditions(ree: Ree, layout: ReeLayout) -> None:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot cross-check its SBOM")
    ree_audit = audit(ree)
    if ree_audit.evaluation.evidence != "current":
        detail = "; ".join(ree_audit.evaluation.reasons) or "reproducibility evidence is not current"
        raise ReePreconditionError(detail)
    if ree_audit.sbom.evidence != "current":
        detail = "; ".join(ree_audit.sbom.reasons) or "SBOM evidence is not current"
        raise ReePreconditionError(detail)
    evaluation = ree.subject.receipts.evaluation
    sbom = ree.subject.receipts.sbom
    if evaluation is None or sbom is None:
        raise ReePreconditionError("evaluation and SBOM receipts are required")
    if not layout.reproducibility_report.is_file():
        raise ReePreconditionError("reproducibility report is missing")
    if digest_file(layout.reproducibility_report) != evaluation.report_digest:
        raise ReePreconditionError("reproducibility report does not match its selected receipt")
    if not layout.sbom.is_file():
        raise ReePreconditionError("SBOM document is missing")
    if digest_file(layout.sbom) != sbom.sbom_digest:
        raise ReePreconditionError("SBOM document does not match its selected receipt")
