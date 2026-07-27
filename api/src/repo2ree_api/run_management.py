from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from repo2ree_api.contracts import RunOperation
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_service import CommandRunSpec, ReeService
from repo2ree_api.run_registry import RunRegistry
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult

# ================================================
# Registry
# ================================================


def _require_workspace(ree_id: str) -> None:
    if workbench_manager.lookup(ree_id) is not None:
        return
    if workbench_manager.is_registered(ree_id):
        raise HTTPException(status_code=503, detail="Workbench unavailable for this REE")
    raise HTTPException(status_code=404, detail="Workspace not found")


_registry = RunRegistry(_require_workspace)
ree_service = ReeService(workbench_manager, _registry)

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
    runner: Callable[[str, str], ActionResult],
    idempotency_key: str | None = None,
    initial_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _registry.start_background(
        ree_id,
        operation,
        request_payload,
        run_id_prefix,
        runner,
        idempotency_key=idempotency_key,
        initial_outputs=initial_outputs,
    )


def start_provisioning_run(
    ree_id: str,
    request_payload: dict[str, Any],
    runner: Callable[[str, str], ActionResult],
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
    hbom routes: cancel-check → workbench lookup → dispatch → result.

    The fallback outputs stand in whenever the command reports none — on cancel,
    and when it simply produced nothing — and are also seeded onto the run at
    creation. They describe what the run *is about* rather than what it found,
    which is knowable before it runs and is what a caller needs back from its own
    POST: the review routes mint the attempt id themselves, and a client that
    could only learn it by waiting for the run could not address the attempt it
    just opened.
    """
    return ree_service.start_command(
        ree_id,
        CommandRunSpec(
            operation=operation,
            run_id_prefix=run_id_prefix,
            canceled_message=canceled_message,
            fallback_outputs=fallback_outputs or {},
        ),
        command,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
    )
