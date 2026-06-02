from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.envelope.command import GenerateSbomArgs
from repo2ree_core.envelope.handlers._common import (
    patch_ree_draft_metadata,
    resolve_workspace_path,
)
from repo2ree_core.envelope.result import ActionResult
from repo2ree_core.sbom.generate_sbom import generate_sbom
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment import CancelCheck


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

    log("system", "info", f"Runtime input: {runtime_path}")
    try:
        generated = generate_sbom(runtime_abs, layout.workspace)
        if generated.name != "sbom.json":
            raise RuntimeError(f"Unexpected generated SBOM filename: {generated.name}")
        patch_ree_draft_metadata(ReeStore(layout), {"sbom": "sbom.json"})
    except Exception as exc:
        log("system", "error", f"SBOM generation failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "SBOM run succeeded")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={
            "sbomRelativePath": "sbom.json",
            "runtimeRelativePath": runtime_path,
            "format": "spdx-json",
        },
    )
