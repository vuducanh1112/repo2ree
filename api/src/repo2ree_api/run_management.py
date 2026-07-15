from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import HTTPException

from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_registry import RunRegistry
from repo2ree_protocol.command import Command

# ================================================
# Types
# ================================================


RunOperation = Literal[
    "provision", "build", "sbom", "crosscheck", "hbom", "activation", "source", "evaluate", "experiment"
]


# ================================================
# Registry
# ================================================


def _require_workspace(ree_id: str) -> None:
    if workbench_manager.lookup(ree_id) is not None:
        return
    # The workbench may not exist yet during a provisioning run; accept the REE
    # while that run is on record so its logs/status stay readable as it streams.
    if _registry.has_runs(ree_id):
        return
    raise HTTPException(status_code=404, detail="Workspace not found")


_registry = RunRegistry(_require_workspace)

append_run_log = _registry.append_log
update_run_outputs = _registry.update_outputs
is_cancel_requested = _registry.is_cancel_requested
mark_cancel_requested = _registry.mark_cancel_requested
run_summary = _registry.run_summary
get_run_state = _registry.get_run_state
list_runs = _registry.list_runs
observe_run = _registry.observe


def start_background_run(
    ree_id: str,
    operation: RunOperation,
    request_payload: dict[str, Any],
    run_id_prefix: str,
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return _registry.start_background(
        ree_id,
        operation,
        request_payload,
        run_id_prefix,
        runner,
        idempotency_key=idempotency_key,
    )


def start_provisioning_run(
    ree_id: str,
    request_payload: dict[str, Any],
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Start the background run that provisions a brand-new workbench.

    Unlike other runs, this one creates its own REE, so it skips the
    workbench-existence check that would otherwise 404 the not-yet-built REE.
    """
    return _registry.start_background(
        ree_id,
        "provision",
        request_payload,
        "provision",
        runner,
        require_ree_exists=False,
    )


def start_single_command_run(
    ree_id: str,
    *,
    operation: RunOperation,
    command: Command,
    run_id_prefix: str,
    request_payload: dict[str, Any],
    canceled_message: str,
    fallback_outputs: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Start a background run that dispatches a single workbench command.

    Collapses the common runner shape used by the build / activation / sbom /
    hbom routes: cancel-check → workbench lookup → dispatch → result. The
    fallback outputs are returned when the command yields none (and on cancel).
    """
    outputs = fallback_outputs or {}

    def _runner(rid: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        if is_cancel_requested(rid, run_id):
            _log("system", "warn", canceled_message)
            return "canceled", outputs

        handle = workbench_manager.lookup(rid)
        if handle is None:
            _log("system", "error", f"No workbench available for {command.operation}")
            return "failed", {}

        result = workbench_manager.dispatch_action(handle, command, run_id, _log)
        return result.status, result.outputs or outputs

    return start_background_run(
        ree_id=ree_id,
        operation=operation,
        request_payload=request_payload,
        run_id_prefix=run_id_prefix,
        runner=_runner,
        idempotency_key=idempotency_key,
    )
