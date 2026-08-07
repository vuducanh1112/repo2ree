"""Generate an SBOM for the selected built runtime and commit its receipt."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.sbom.scan import SBOM_FORMAT, is_runtime_archive, scan_runtime_archive
from repo2ree_core.digests import digest_file
from repo2ree_core.domain.primitives import ArtifactPath, WorkspacePath
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.receipt import GenerateSbomReceipt, receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import publish_atomic, staging_path
from repo2ree_core.persistence.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class GenerateSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sbom_relative_path: str
    runtime_relative_path: str
    format: str
    receipt: GenerateSbomReceipt


def handle_generate_sbom(
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
        runtime_path = _check_preconditions(ree, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot generate SBOM: {exc}")
        return ActionResult.failed("precondition", f"cannot generate SBOM: {exc}")
    except ValueError as exc:
        log("system", "error", f"invalid SBOM request: {exc}")
        return ActionResult.failed("validation", f"invalid SBOM request: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load SBOM inputs: {exc}")

    before_revision = revision_of(ree)
    runtime_abs = layout.workspace / str(runtime_path)
    runtime_digest = digest_file(runtime_abs)
    timer = OperationTimer.start()
    output_path = layout.sbom
    staged = staging_path(output_path)
    log("system", "info", f"Runtime input: {runtime_path}")

    try:
        scan = scan_runtime_archive(runtime_abs, staged, log=log, is_canceled=is_canceled)
    except Exception as exc:
        staged.unlink(missing_ok=True)
        log("system", "error", f"SBOM scanner failed: {exc}")
        return failed_from_exception(exc, f"SBOM scanner failed: {exc}")
    if scan.canceled:
        staged.unlink(missing_ok=True)
        log("system", "warn", "generate_sbom canceled")
        return ActionResult(status="canceled")
    if scan.returncode != 0:
        staged.unlink(missing_ok=True)
        log("system", "error", f"syft failed (exit {scan.returncode})")
        return ActionResult.failed(
            "execution",
            f"syft failed (exit {scan.returncode})",
            exit_code=scan.returncode or 1,
        )
    if not staged.is_file():
        return ActionResult.failed("execution", "SBOM scanner succeeded without producing a document")
    if not scan.tool_version:
        staged.unlink(missing_ok=True)
        return ActionResult.failed("execution", "SBOM scanner did not report its tool version")

    sbom_digest = digest_file(staged)
    try:
        publish_atomic(staged, output_path)
    except Exception as exc:
        staged.unlink(missing_ok=True)
        return failed_from_exception(exc, f"failed to publish SBOM: {exc}")

    timing = timer.finish()
    receipt = GenerateSbomReceipt(
        **receipt_envelope(run_id, timing),
        runtime_path=runtime_path,
        runtime_digest=runtime_digest,
        sbom_path=ArtifactPath(SBOM_ARTIFACT_PATH),
        sbom_digest=sbom_digest,
        sbom_format=SBOM_FORMAT,
        tool_version=scan.tool_version,
    )
    try:
        save_ree(
            layout,
            store,
            commit_receipt(ree, receipt),
            expected_revision=before_revision,
        )
    except ReeRevisionConflictError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        log("system", "error", f"failed to commit SBOM receipt: {exc}")
        return failed_from_exception(exc, f"failed to commit SBOM receipt: {exc}")

    log(
        "system",
        "info",
        f"generate_sbom succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    outputs = GenerateSbomOutputs(
        sbom_relative_path=SBOM_ARTIFACT_PATH,
        runtime_relative_path=runtime_path,
        format=SBOM_FORMAT,
        receipt=receipt,
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=outputs.model_dump(mode="json", exclude_none=True),
    )


def _check_preconditions(
    ree: Ree,
    layout: ReeLayout,
) -> WorkspacePath:
    """Resolve the runtime to scan from the build recipe that produced it.

    The path is not a parameter of the scan. The author declared it before the
    build ran and the build receipt binds it, so a caller could only ever pass
    back the value the REE already holds — an echo that can agree, never
    inform. Reading it here keeps one declaration to check the evidence
    against.
    """
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot generate an SBOM")
    runtime = ree.subject.definition.build_runtime
    runtime_path = runtime.runtime_path if runtime else None
    if runtime is None or runtime_path is None:
        raise ReePreconditionError("no runtime artifact path is declared")
    if not is_runtime_archive(str(runtime.runtime_path)):
        raise ValueError("SBOM generation currently supports runtime tarballs only")
    build = ree.subject.receipts.build
    if build is None:
        raise ReePreconditionError("runtime has not been built")
    runtime_audit = audit(ree).runtime
    if runtime_audit.evidence != "current":
        detail = "; ".join(runtime_audit.reasons) or "build evidence is not current"
        raise ReePreconditionError(detail)
    runtime_abs = layout.workspace / str(runtime.runtime_path)
    if not runtime_abs.is_file():
        raise ReePreconditionError(f"runtime artifact is missing: {runtime.runtime_path}")
    if digest_file(runtime_abs) != build.produced_runtime_digest:
        raise ReePreconditionError("runtime artifact does not match the selected build receipt")
    return runtime_path
