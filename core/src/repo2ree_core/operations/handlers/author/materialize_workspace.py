from __future__ import annotations

from pathlib import Path

from repo2ree_core.execution.process import (
    CancelCheck,
    format_command,
    run_streaming_process,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import MATERIALIZE_SCRIPT_FILENAME, ReeLayout
from repo2ree_core.reproduction.materialize_workspace import build_materialize_sh
from repo2ree_core.workspace.attempt import show_environment
from repo2ree_core.workspace.materialization import record_materialization
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest


def _write_materialize_script(*, log: LogSink, layout: ReeLayout) -> Path:
    write_atomic(layout.materialize_script, build_materialize_sh())
    log("system", "info", f"wrote materialize script → {MATERIALIZE_SCRIPT_FILENAME}")
    return layout.materialize_script


def materialize_workspace(
    layout: ReeLayout,
    *,
    snapshot_digest: Digest | None,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    log("system", "info", f"materializing {layout.workspace}")

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

    record_materialization(layout, snapshot_digest=snapshot_digest, log=log)
    if layout.manifest.is_file():
        declared = ReeDirectory(layout).read_ree().subject.definition.experiment_environment.artifact_path
        show_environment(layout, str(declared) if declared else None)
    log("system", "info", "materialize_workspace succeeded")
    return ActionResult(status="succeeded", exit_code=0)


def handle_materialize_workspace(
    *,
    layout: ReeLayout,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    source_receipt = store.read_ree().subject.receipts.acquire_source if store.manifest_exists() else None
    committed_digest = source_receipt.snapshot_digest if source_receipt else None
    return materialize_workspace(layout, snapshot_digest=committed_digest, log=log, is_canceled=is_canceled)
