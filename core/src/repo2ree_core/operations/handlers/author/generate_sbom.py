"""Generate an SBOM for the selected built experiment environment and commit its receipt."""

from __future__ import annotations

from repo2ree_core.analysis.sbom.scan import (
    SBOM_FORMAT,
    is_experiment_environment_archive,
    scan_experiment_environment_archive,
)
from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import publish_atomic, staging_path
from repo2ree_core.persistence.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import GenerateSbomOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree
from repo2ree_ree.primitives import ArtifactPath, ExperimentEnvironmentPath
from repo2ree_ree.receipt import GenerateSbomReceipt


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
        experiment_environment_path = _check_preconditions(ree, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot generate SBOM: {exc}")
        return ActionResult.failed("precondition", f"cannot generate SBOM: {exc}")
    except ValueError as exc:
        log("system", "error", f"invalid SBOM request: {exc}")
        return ActionResult.failed("validation", f"invalid SBOM request: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load SBOM inputs: {exc}")

    before_revision = revision_of(ree)
    experiment_environment_abs = layout.workspace / str(experiment_environment_path)
    experiment_environment_digest = digest_file(experiment_environment_abs)
    timer = OperationTimer.start()
    output_path = layout.sbom
    staged = staging_path(output_path)
    log("system", "info", f"Experiment environment input: {experiment_environment_path}")

    try:
        scan = scan_experiment_environment_archive(experiment_environment_abs, staged, log=log, is_canceled=is_canceled)
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
        experiment_environment_path=experiment_environment_path,
        experiment_environment_digest=experiment_environment_digest,
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
        experiment_environment_relative_path=experiment_environment_path,
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
) -> ExperimentEnvironmentPath:
    """Resolve the experiment environment to scan from the build recipe that produced it.

    The path is not a parameter of the scan. The author declared it before the
    build ran and the build receipt binds it, so a caller could only ever pass
    back the value the REE already holds — an echo that can agree, never
    inform. Reading it here keeps one declaration to check the evidence
    against.
    """
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot generate an SBOM")
    experiment_environment = ree.subject.definition.experiment_environment
    experiment_environment_path = experiment_environment.artifact_path if experiment_environment else None
    if experiment_environment is None or experiment_environment_path is None:
        raise ReePreconditionError("no experiment environment artifact path is declared")
    if not is_experiment_environment_archive(str(experiment_environment.artifact_path)):
        raise ValueError("SBOM generation currently supports experiment environment tarballs only")
    build = ree.subject.receipts.experiment_environment
    if build is None:
        raise ReePreconditionError("experiment environment has not been built")
    experiment_environment_audit = audit(ree).experiment_environment
    if experiment_environment_audit.evidence != "current":
        detail = "; ".join(experiment_environment_audit.reasons) or "build evidence is not current"
        raise ReePreconditionError(detail)
    experiment_environment_abs = layout.workspace / str(experiment_environment.artifact_path)
    if not experiment_environment_abs.is_file():
        raise ReePreconditionError(
            f"experiment environment artifact is missing: {experiment_environment.artifact_path}"
        )
    if digest_file(experiment_environment_abs) != build.produced_artifact_digest:
        raise ReePreconditionError("experiment environment artifact does not match the selected build receipt")
    return experiment_environment_path
