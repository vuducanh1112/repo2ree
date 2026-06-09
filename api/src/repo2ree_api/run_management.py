from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import HTTPException

from repo2ree_protocol.command import Command
from repo2ree_api.run_registry import RunRegistry
from repo2ree_api.workbench.deps import workbench_manager


# ================================================
# Types
# ================================================


RunOperation = Literal[
    "build", "sbom", "hbom", "activation", "source", "evaluate", "experiment"
]


# ================================================
# Registry
# ================================================


def _require_workspace(ree_id: str) -> None:
    if workbench_manager.lookup(ree_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


_registry = RunRegistry("reeId", _require_workspace, include_id_in_summary=True)

_append_run_log = _registry.append_log
_update_run_outputs = _registry.update_outputs
_is_cancel_requested = _registry.is_cancel_requested
_mark_cancel_requested = _registry.mark_cancel_requested
_run_summary = _registry.run_summary
_get_run_state = _registry.get_run_state


def _start_background_run(
    ree_id: str,
    operation: RunOperation,
    request_payload: dict[str, Any],
    run_id_prefix: str,
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    return _registry.start_background(
        ree_id, operation, request_payload, run_id_prefix, runner
    )


def _start_single_command_run(
    ree_id: str,
    *,
    operation: RunOperation,
    command: Command,
    run_id_prefix: str,
    request_payload: dict[str, Any],
    canceled_message: str,
    fallback_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a background run that dispatches a single workbench command.

    Collapses the common runner shape used by the build / activation / sbom /
    hbom routes: cancel-check → workbench lookup → dispatch → result. The
    fallback outputs are returned when the command yields none (and on cancel).
    """
    outputs = fallback_outputs or {}

    def _runner(rid: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(rid, run_id, stream, level, message)

        if _is_cancel_requested(rid, run_id):
            _log("system", "warn", canceled_message)
            return "canceled", outputs

        handle = workbench_manager.lookup(rid)
        if handle is None:
            _log("system", "error", f"No workbench available for {command.operation}")
            return "failed", {}

        result = workbench_manager.dispatch_action(handle, command, run_id, _log)
        return result.status, result.outputs or outputs

    return _start_background_run(
        ree_id=ree_id,
        operation=operation,
        request_payload=request_payload,
        run_id_prefix=run_id_prefix,
        runner=_runner,
    )
