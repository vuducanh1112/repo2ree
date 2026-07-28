from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.sbom.scan import SBOM_FORMAT, is_runtime_archive, scan_runtime_archive
from repo2ree_core.digests import digest_file
from repo2ree_core.evidence.receipts.models import GenerateSbomReceipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.author import (
    patch_ree_intent,
    resolve_workspace_path,
    settle_step,
)
from repo2ree_core.ree.files import publish_atomic, staging_path
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus

_OPERATION = "generate_sbom"


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
    except ValueError as exc:
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
        """Settle this step, on whichever of its four exits reached here."""
        return settle_step(
            layout,
            lambda envelope: GenerateSbomReceipt(
                **envelope,
                runtime_path=runtime_path,
                declared_runtime_digest=declared_runtime_digest,
                sbom_path=SBOM_ARTIFACT_PATH if sbom_digest else None,
                sbom_digest=sbom_digest,
                sbom_format=SBOM_FORMAT if sbom_digest else None,
                tool_version=tool_version,
            ),
            operation=_OPERATION,
            run_id=run_id,
            timer=timer,
            status=status,
            log=log,
        )

    # Written straight into the REE's own artifacts/, never into the workspace:
    # the SBOM is produced evidence, so nothing downstream has to lift it out of
    # a materialized tree — or exempt it from that tree's drift check.
    output_path = layout.sbom
    log("system", "info", f"Runtime input: {runtime_path}")

    # Scanned into a staging sibling and promoted only once syft has finished
    # cleanly. The scanner writes its own output file, so a scan that fails or
    # is canceled part-way leaves a partial document behind — and this path is
    # the one the intent points at, so publishing that would leave the REE
    # declaring an SBOM that no longer parses.
    staged = staging_path(output_path)
    scan = scan_runtime_archive(runtime_abs, staged, log=log, is_canceled=is_canceled)
    if scan.canceled:
        staged.unlink(missing_ok=True)
        receipt("canceled")
        return ActionResult(status="canceled")
    if scan.returncode != 0:
        staged.unlink(missing_ok=True)
        log("system", "error", f"syft failed (exit {scan.returncode})")
        receipt("failed")
        # Never 0: a failed step must not report the exit code of a success.
        return ActionResult.failed("execution", f"syft failed (exit {scan.returncode})", exit_code=scan.returncode or 1)
    publish_atomic(staged, output_path)

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
