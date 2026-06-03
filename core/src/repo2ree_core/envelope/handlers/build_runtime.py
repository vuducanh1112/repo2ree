from __future__ import annotations

from typing import Any

from repo2ree_core.container.run_script import LogSink
from repo2ree_protocol.command import BuildRuntimeArgs
from repo2ree_core.envelope.handlers._common import (
    resolve_workspace_path,
    run_script_directly,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.working_environment import CancelCheck


def handle_build_runtime(
    args: BuildRuntimeArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "build_runtime canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    script_path = args.build_runtime_script_path.strip()
    try:
        resolve_workspace_path(layout, script_path)
    except Exception as exc:
        log("system", "error", f"invalid build script path: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"Starting build run {run_id}")
    log("system", "info", f"Build script: {script_path}")
    outcome = run_script_directly(
        workspace=layout.workspace.resolve(),
        script_rel_path=script_path,
        log=log,
        is_canceled=is_canceled,
    )

    log(
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"Build run {outcome.status} (exit code {outcome.exit_code})",
    )
    outputs: dict[str, Any] = {"buildRuntimeScriptPath": script_path}
    if outcome.exit_code is not None:
        outputs["containerExitCode"] = outcome.exit_code
    return ActionResult(
        status=outcome.status,
        exit_code=outcome.exit_code or 0,
        outputs=outputs,
    )
