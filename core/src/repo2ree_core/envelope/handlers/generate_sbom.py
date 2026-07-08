from __future__ import annotations

import json
import subprocess
from typing import Any

from repo2ree_core.digests import digest_file
from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    resolve_workspace_path,
)
from repo2ree_core.receipts import GenerateSbomReceipt, receipt_run_id, record_receipt
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
from repo2ree_core.tooling import resolve_tool
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus


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
        return ActionResult(status="failed", exit_code=1)

    if not runtime_abs.is_file():
        log("system", "error", f"Runtime tarball not found: {runtime_path}")
        return ActionResult(status="failed", exit_code=1)
    if not runtime_path.lower().endswith((".tar", ".tar.gz", ".tgz")):
        log(
            "system",
            "error",
            "SBOM generation currently supports runtime tarballs only",
        )
        return ActionResult(status="failed", exit_code=1)

    # Workspace-independent step: its only input is the declared runtime
    # artifact, digested before syft consumes it.
    declared_runtime_digest = digest_file(runtime_abs)

    def receipt(status: ActionStatus, *, sbom_digest: str | None = None) -> GenerateSbomReceipt:
        built = GenerateSbomReceipt(
            run_id=receipt_run_id(run_id),
            recorded_at=utc_now(),
            status=status,
            runtime_path=runtime_path,
            declared_runtime_digest=declared_runtime_digest,
            sbom_path="sbom.json" if sbom_digest else None,
            sbom_digest=sbom_digest,
        )
        record_receipt(layout, built, log=log)
        return built

    output_path = layout.workspace / "sbom.json"
    syft = resolve_tool("syft")
    log("system", "info", f"Runtime input: {runtime_path}")
    log("system", "info", f"$ {syft} docker-archive:{runtime_abs} -o json={output_path}")

    result = subprocess.run(
        [
            syft,
            f"docker-archive:{runtime_abs}",
            "-o",
            f"json={output_path}",
        ],
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
        return ActionResult(status="failed", exit_code=result.returncode)

    try:
        sbom_data = json.loads(output_path.read_text())
        with open(layout.workspace / "sbom_readable.json", "w") as f:
            json.dump(sbom_data, f, indent=2)
        patch_ree_intent(ReeStore(layout), {"sbom": "sbom.json"})
    except Exception as exc:
        log("system", "error", f"post-processing SBOM failed: {exc}")
        receipt("failed")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "SBOM run succeeded")
    recorded = receipt("succeeded", sbom_digest=digest_file(output_path))
    outputs: dict[str, Any] = {
        "sbomRelativePath": "sbom.json",
        "runtimeRelativePath": runtime_path,
        "format": "spdx-json",
        "receipt": recorded.model_dump(by_alias=True),
    }
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)
