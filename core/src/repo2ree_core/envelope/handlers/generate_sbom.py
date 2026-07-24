from __future__ import annotations

import json
import subprocess
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file
from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    resolve_workspace_path,
)
from repo2ree_core.receipts import GenerateSbomReceipt, receipt_run_id, record_receipt
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_core.tooling import resolve_tool
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
    if is_canceled():
        log("system", "warn", "generate_sbom canceled before start")
        return ActionResult(status="canceled")

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
    if not runtime_path.lower().endswith((".tar", ".tar.gz", ".tgz")):
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
            run_id=receipt_run_id(run_id),
            started_at=timing.started_at,
            finished_at=timing.finished_at,
            duration_ms=timing.duration_ms,
            recorded_at=timing.finished_at,
            status=status,
            runtime_path=runtime_path,
            declared_runtime_digest=declared_runtime_digest,
            sbom_path="sbom.json" if sbom_digest else None,
            sbom_digest=sbom_digest,
            sbom_format="cyclonedx-json" if sbom_digest else None,
            tool_version=tool_version,
        )
        record_receipt(layout, built, log=log)
        log(
            "system",
            "info" if status == "succeeded" else "error",
            f"generate_sbom {status} in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return built

    output_path = layout.workspace / "sbom.json"
    syft = resolve_tool("syft")
    log("system", "info", f"Runtime input: {runtime_path}")
    # --scope squashed pinned explicitly: "observed in the runtime" must mean
    # the squashed filesystem, and syft defaults must not drift underneath us.
    argv = [
        syft,
        f"docker-archive:{runtime_abs}",
        "--scope",
        "squashed",
        "-o",
        f"cyclonedx-json={output_path}",
    ]
    log("system", "info", f"$ {' '.join(argv)}")

    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        log("stdout", "info", line)
    for line in result.stderr.splitlines():
        log("stdout", "info", line)

    if result.returncode != 0:
        log("system", "error", f"syft failed (exit {result.returncode})")
        receipt("failed")
        return ActionResult.failed("execution", f"syft failed (exit {result.returncode})", exit_code=result.returncode)

    try:
        sbom_data = json.loads(output_path.read_text())
        tool_version = _syft_version(sbom_data)
        patch_ree_intent(ReeStore(layout), {"sbom": "sbom.json"})
    except Exception as exc:
        log("system", "error", f"post-processing SBOM failed: {exc}")
        receipt("failed")
        return ActionResult.failed("internal", f"post-processing SBOM failed: {exc}")

    recorded = receipt(
        "succeeded",
        sbom_digest=digest_file(output_path),
        tool_version=tool_version,
    )
    outputs = GenerateSbomOutputs(
        sbom_relative_path="sbom.json",
        runtime_relative_path=runtime_path,
        format="cyclonedx-json",
        receipt=recorded.model_dump(),
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())


def _syft_version(sbom_data: Any) -> str | None:
    """The generating syft version out of the CycloneDX metadata.

    ``metadata.tools`` is a ``{"components": [...]}`` object on CycloneDX >= 1.5
    and a bare list of tool objects on 1.4; absence is not an error.
    """
    if not isinstance(sbom_data, dict):
        return None
    tools = (sbom_data.get("metadata") or {}).get("tools")
    entries = tools.get("components") if isinstance(tools, dict) else tools
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == "syft":
            version = entry.get("version")
            return version if isinstance(version, str) else None
    return None
