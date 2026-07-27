"""Background-run orchestration: the run registry and the ways routes start work.

Routes own HTTP validation and response shaping; this module owns starting a run
and, for the single-command case, the runner that drives it. It is the one place
routes reach the ``RunRegistry``, so the registry itself stays free of route
concerns.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from repo2ree_api.contracts import RunOperation
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_commands import require_handle
from repo2ree_api.run_registry import RunRegistry
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult

# ================================================
# Registry
# ================================================


def _require_workspace(ree_id: str) -> None:
    """Starting new work needs a live workbench (404 unknown / 503 unreachable).

    Reading run history deliberately does not — see ``RunRegistry``. The same
    resolution every synchronous command route uses, so one REE cannot read as
    "not found" from one route and "unavailable" from another.
    """
    require_handle(ree_id)


_registry = RunRegistry(_require_workspace)

append_run_log = _registry.append_log
update_run_outputs = _registry.update_outputs
is_cancel_requested = _registry.is_cancel_requested
mark_cancel_requested = _registry.mark_cancel_requested
run_summary = _registry.run_summary
get_run_state = _registry.get_run_state
list_runs = _registry.list_runs
observe_run = _registry.observe
start_background_run = _registry.start_background


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
    outputs = dict(fallback_outputs or {})

    def _runner(rid: str, run_id: str) -> ActionResult:
        def _log(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        if is_cancel_requested(rid, run_id):
            _log("system", "warn", canceled_message)
            return ActionResult(status="canceled", outputs=outputs)

        # The REE was live when the run was created; by the time this worker
        # thread runs it may not be. Retryable only when the workbench is
        # registered but unreachable (503) — a 404 means the REE is gone, and
        # retrying that can never succeed.
        try:
            handle = require_handle(rid)
        except HTTPException as exc:
            _log("system", "error", str(exc.detail))
            return ActionResult.failed(
                "unavailable",
                str(exc.detail),
                origin="api",
                retryable=exc.status_code == 503,
            )

        result = workbench_manager.dispatch_action(handle, command, run_id, _log)
        # Preserve the route's fallback outputs when the command reported none.
        if not result.outputs and outputs:
            return result.model_copy(update={"outputs": outputs})
        return result

    return start_background_run(
        ree_id,
        operation,
        request_payload,
        run_id_prefix,
        _runner,
        idempotency_key=idempotency_key,
        initial_outputs=outputs,
    )
