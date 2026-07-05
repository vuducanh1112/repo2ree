from __future__ import annotations

import json
import subprocess
from typing import Any

from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    resolve_workspace_path,
)
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.tooling import resolve_tool
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_generate_sbom(
    args: GenerateSbomArgs,
    *,
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
        return ActionResult(status="failed", exit_code=result.returncode)

    try:
        sbom_data = json.loads(output_path.read_text())
        with open(layout.workspace / "sbom_readable.json", "w") as f:
            json.dump(sbom_data, f, indent=2)
        patch_ree_intent(ReeStore(layout), {"sbom": "sbom.json"})
    except Exception as exc:
        log("system", "error", f"post-processing SBOM failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "SBOM run succeeded")
    outputs: dict[str, Any] = {
        "sbomRelativePath": "sbom.json",
        "runtimeRelativePath": runtime_path,
        "format": "spdx-json",
    }
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)
