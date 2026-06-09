from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_protocol.command import BuildRuntimeArgs
from repo2ree_core.envelope.handlers._common import run_workspace_script_handler
from repo2ree_protocol.result import ActionResult
from repo2ree_core.working_environment import CancelCheck


def handle_build_runtime(
    args: BuildRuntimeArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    return run_workspace_script_handler(
        args.build_runtime_script_path,
        operation="build_runtime",
        noun="Build",
        output_key="buildRuntimeScriptPath",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
