"""Application service coordinating HTTP use-cases with the supervisor.

Routes own HTTP validation and response shaping; this service owns starting and
dispatching work. It is intentionally in-process and adds no deployment unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from repo2ree_api.contracts import RunOperation
from repo2ree_api.run_registry import RunRegistry
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchHandle, WorkbenchManager


@dataclass(frozen=True)
class CommandRunSpec:
    operation: RunOperation
    run_id_prefix: str
    canceled_message: str
    fallback_outputs: dict[str, Any] = field(default_factory=dict)


class ReeService:
    def __init__(self, manager: WorkbenchManager, runs: RunRegistry) -> None:
        self.manager = manager
        self.runs = runs

    def require_live_workbench(self, ree_id: str) -> WorkbenchHandle:
        handle = self.manager.lookup(ree_id)
        if handle is not None:
            return handle
        if self.manager.is_registered(ree_id):
            raise HTTPException(status_code=503, detail="Workbench unavailable for this REE")
        raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")

    def start_command(
        self,
        ree_id: str,
        spec: CommandRunSpec,
        command: Command,
        *,
        request_payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        outputs = dict(spec.fallback_outputs)

        def runner(rid: str, run_id: str) -> ActionResult:
            def log(stream: str, level: str, message: str) -> None:
                self.runs.append_log(rid, run_id, stream, level, message)

            if self.runs.is_cancel_requested(rid, run_id):
                log("system", "warn", spec.canceled_message)
                return ActionResult(status="canceled", outputs=outputs)

            try:
                handle = self.require_live_workbench(rid)
            except HTTPException as exc:
                log("system", "error", str(exc.detail))
                return ActionResult.failed(
                    "unavailable",
                    str(exc.detail),
                    origin="api",
                    retryable=exc.status_code == 503,
                )

            result = self.manager.dispatch_action(handle, command, run_id, log)
            if not result.outputs and outputs:
                return result.model_copy(update={"outputs": outputs})
            return result

        return self.runs.start_background(
            ree_id,
            spec.operation,
            request_payload,
            spec.run_id_prefix,
            runner,
            idempotency_key=idempotency_key,
            initial_outputs=outputs,
        )
