from __future__ import annotations

from repo2ree_core.envelope.handlers._common import run_bare_script_handler
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.run_script import CancelCheck
from repo2ree_protocol.command import BuildRuntimeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_build_runtime(
    args: BuildRuntimeArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    # The build script is fixed: always the reserved, REE-owned build script.
    return run_bare_script_handler(
        RESERVED_BUILD_SCRIPT,
        operation="build_runtime",
        noun="Build",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
