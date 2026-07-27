from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.sbom.scan import SBOM_FORMAT, is_runtime_archive, scan_runtime_archive
from repo2ree_core.digests import digest_file
from repo2ree_core.evidence.receipts.models import GenerateSbomReceipt, receipt_envelope
from repo2ree_core.evidence.receipts.store import record_receipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.author import (
    patch_ree_intent,
    resolve_workspace_path,
)
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus


class GenerateSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sbom_relative_path: str
    runtime_relative_path: str
    format: str
    receipt: dict[str, Any]


def handle_generate_sbom(
    args: GenerateSbomArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    runtime_path = args.produced_runtime_path.strip()
    try:
        runtime_abs = resolve_workspace_path(layout, runtime_path)
    except Exception as exc:
        log("system", "error", f"invalid runtime path: {exc}")
        return ActionResult.failed("validation", f"invalid runtime path: {exc}")

    if not runtime_abs.is_file():
        log("system", "error", f"Runtime tarball not found: {runtime_path}")
        return ActionResult.failed("precondition", f"Runtime tarball not found: {runtime_path}")
    if not is_runtime_archive(runtime_path):
        log(
            "system",
            "error",
            "SBOM generation currently supports runtime tarballs only",
        )
        return ActionResult.failed("validation", "SBOM generation currently supports runtime tarballs only")

    timer = OperationTimer.start()

    # Workspace-independent step: its only input is the declared runtime
    # artifact, digested before syft consumes it.
    declared_runtime_digest = digest_file(runtime_abs)

    def receipt(
        status: ActionStatus,
        *,
        sbom_digest: str | None = None,
        tool_version: str | None = None,
    ) -> GenerateSbomReceipt:
        timing = timer.finish()
        built = GenerateSbomReceipt(
            **receipt_envelope(run_id, timing, status),
            runtime_path=runtime_path,
            declared_runtime_digest=declared_runtime_digest,
            sbom_path=SBOM_ARTIFACT_PATH if sbom_digest else None,
            sbom_digest=sbom_digest,
            sbom_format=SBOM_FORMAT if sbom_digest else None,
            tool_version=tool_version,
        )
        record_receipt(layout, built, log=log)
        log(
            "system",
            "info" if status == "succeeded" else "error",
            f"generate_sbom {status} in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return built

    # Written straight into the REE's own artifacts/, never into the workspace:
    # the SBOM is produced evidence, so nothing downstream has to lift it out of
    # a materialized tree — or exempt it from that tree's drift check.
    output_path = layout.sbom
    log("system", "info", f"Runtime input: {runtime_path}")
    scan = scan_runtime_archive(runtime_abs, output_path, log=log)
    if scan.returncode != 0:
        log("system", "error", f"syft failed (exit {scan.returncode})")
        receipt("failed")
        return ActionResult.failed("execution", f"syft failed (exit {scan.returncode})", exit_code=scan.returncode)

    try:
        patch_ree_intent(ReeStore(layout), {"sbom": SBOM_ARTIFACT_PATH})
    except Exception as exc:
        log("system", "error", f"post-processing SBOM failed: {exc}")
        receipt("failed")
        return ActionResult.failed("internal", f"post-processing SBOM failed: {exc}")

    recorded = receipt(
        "succeeded",
        sbom_digest=digest_file(output_path),
        tool_version=scan.tool_version,
    )
    outputs = GenerateSbomOutputs(
        sbom_relative_path=SBOM_ARTIFACT_PATH,
        runtime_relative_path=runtime_path,
        format=SBOM_FORMAT,
        receipt=recorded.model_dump(),
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
