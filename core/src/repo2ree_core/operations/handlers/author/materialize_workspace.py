"""Handler for the materialize_workspace operation.

Rebuilds /ree/workspace as the merge of /ree/upstream and /ree/overlay (overlay
wins on conflict) by running the generated ``materialize_workspace.sh`` — the
single, shared merge muscle also shipped in the bundle and called by run.sh.
Idempotent: the script clears the workspace first.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.authoring.script_generation.materialize_workspace import build_materialize_sh
from repo2ree_core.execution.process import (
    CancelCheck,
    format_command,
    run_streaming_process,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import MATERIALIZE_SCRIPT_FILENAME, ReeLayout
from repo2ree_core.workspace.materialization import record_materialization
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def _write_materialize_script(*, log: LogSink, layout: ReeLayout) -> Path:
    """Persist ``materialize_workspace.sh`` in the REE.

    Written to the reserved root path so it is sealed into the bundle and run.sh
    can call the very same file. Materialize only ever runs inside a workbench
    REE, so the REE root is always present. The script takes no per-source inputs
    — it merges whatever is on disk under the fixed layout dirs.
    """
    write_atomic(layout.materialize_script, build_materialize_sh())
    log("system", "info", f"wrote materialize script → {MATERIALIZE_SCRIPT_FILENAME}")
    return layout.materialize_script


def handle_materialize_workspace(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    log("system", "info", f"materializing {layout.workspace}")

    # The script owns the fixed REE layout paths and the clear-and-merge; the
    # handler only writes it and drives it.
    script = _write_materialize_script(log=log, layout=layout)
    cmd = ["sh", str(script)]
    log("system", "info", format_command(cmd))
    result = run_streaming_process(cmd, log=log, is_canceled=is_canceled)

    if result.canceled or is_canceled():
        log("system", "warn", "materialize_workspace canceled")
        return ActionResult(status="canceled")
    if result.returncode != 0:
        return ActionResult.failed(
            "execution",
            f"materialize script exited {result.returncode}",
            exit_code=result.returncode or 1,
        )

    store = ReeDirectory(layout)
    snapshot_digest = store.read_state().source_snapshot_digest if store.sidecar_exists() else None
    record_materialization(layout, snapshot_digest=snapshot_digest, log=log)

    log("system", "info", "materialize_workspace succeeded")
    return ActionResult(status="succeeded", exit_code=0)
