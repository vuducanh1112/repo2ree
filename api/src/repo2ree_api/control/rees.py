"""REE lifecycle: provision a workbench, observe it, replace it, tear it down.

Control-plane concerns, not authoring steps — these routes exist for every REE
regardless of how far through the step graph it is. Authoring the REE's content
lives under :mod:`repo2ree_api.authoring`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    DeleteReeResponse,
    ReeCreatePayload,
    ReeDocument,
    ReeList,
    ReeState,
    ReprovisionResponse,
    RunSummary,
)
from repo2ree_api.control.run_orchestration import (
    append_run_log,
    is_cancel_requested,
    list_runs,
    run_summary,
    start_provisioning_run,
)
from repo2ree_api.control.run_registry import ACTIVE_STATUSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.pagination import keyset_paginate
from repo2ree_api.workbench.commands import ree_command_span, require_handle
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol import ActionResult

_log = logging.getLogger(__name__)


rees_router = APIRouter(tags=["rees"])


@rees_router.post(
    "/api/v1/rees",
    operation_id="createRee",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_ree_route(payload: ReeCreatePayload) -> RunSummary:
    ree_id = uuid.uuid4().hex
    name = payload.name or ree_id[:8]
    # Blank/omitted image falls back to the server default in the manager.
    image = (payload.workbench_image or "").strip() or None
    # Blank/omitted agent means "any connected agent" (single-agent path).
    agent_id = (payload.agent_id or "").strip()

    # Provision in the background so the cold-machine image pull streams its
    # progress live into the run's log stream (GET .../runs/{run_id}/logs)
    # instead of blocking the request with no visible output. The ree_id is
    # minted up front, so the response carries it immediately.
    def _runner(rid: str, run_id: str) -> ActionResult:
        def _log_run(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        if is_cancel_requested(rid, run_id):
            _log_run("system", "warn", "Provisioning canceled before it started")
            return ActionResult(status="canceled")

        # Note: cancel is only honoured at the phase boundaries below — the image
        # pull and container start inside provision() run to completion once
        # begun, so a cancel mid-pull only takes effect afterwards.
        try:
            handle = workbench_manager.provision(rid, name, log=_log_run, image=image, agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001 — provisioning is the agent's, so any failure is reported as an unavailable run
            _log_run("system", "error", f"Workbench provisioning failed: {exc}")
            return ActionResult.failed(
                "unavailable",
                f"Workbench provisioning failed: {exc}",
                origin="supervisor",
                retryable=True,
            )

        if is_cancel_requested(rid, run_id):
            _log_run("system", "warn", "Provisioning canceled after workbench startup")
            return ActionResult(status="canceled", outputs={"ree": workbench_manager.get_ree_document(handle)})

        return ActionResult(status="succeeded", outputs={"ree": workbench_manager.get_ree_document(handle)})

    run_state = start_provisioning_run(
        ree_id=ree_id,
        request_payload=payload.model_dump(),
        runner=_runner,
    )
    return RunSummary.model_validate(run_summary(run_state))


@rees_router.get(
    "/api/v1/rees",
    operation_id="listRees",
    response_model=ReeList,
    responses=ERROR_RESPONSES,
)
def list_rees_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None, ge=1),
    status: str | None = Query(None),
) -> ReeList:
    items = workbench_manager.list_all_records()
    if status:
        items = [m for m in items if m.get("status") == status]
    items.sort(key=_ree_page_key, reverse=True)
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_ree_page_key)
    return ReeList.model_validate({"items": page, "next_cursor": next_cursor})


def _ree_page_key(metadata: dict[str, Any]) -> tuple[str, str]:
    return str(metadata.get("name", "")), str(metadata.get("ree_id", ""))


@rees_router.get(
    "/api/v1/rees/{ree_id}",
    operation_id="getRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def get_ree_route(ree_id: str) -> ReeDocument:
    handle = require_handle(ree_id)
    document = workbench_manager.get_ree_document(handle)
    # get-ree-document runs inside the container and can't know the image, so the
    # manager (which owns the registry) supplies it.
    document["workbench_image"] = workbench_manager.image_for(handle)
    return ReeDocument.model_validate(document)


@rees_router.get(
    "/api/v1/rees/{ree_id}/state",
    operation_id="getReeState",
    response_model=ReeState,
    responses=ERROR_RESPONSES,
)
def get_ree_state_route(ree_id: str) -> ReeState:
    """Compact automation view: durable state and file metadata, never contents."""
    handle = require_handle(ree_id)
    document = workbench_manager.get_ree_state(handle)
    active_runs = [run for run in list_runs(ree_id) if run.get("status") in ACTIVE_STATUSES]
    state = {
        "ree_id": document["ree_id"],
        "ree": document["ree"],
        "status": document["status"],
        "audit": document["audit"],
        "workbench": {
            "status": "available",
            "agent_id": handle.agent_id,
            "image": workbench_manager.image_for(handle),
        },
        "workspace_files": document.get("workspace_files", []),
        "ree_files": document.get("ree_files", []),
        "active_runs": active_runs,
    }
    return ReeState.model_validate(state)


@rees_router.delete(
    "/api/v1/rees/{ree_id}",
    operation_id="deleteRee",
    response_model=DeleteReeResponse,
    responses=ERROR_RESPONSES,
)
def delete_ree_route(ree_id: str) -> DeleteReeResponse:
    handle = require_handle(ree_id)
    with ree_command_span("delete", ree_id):
        try:
            workbench_manager.teardown(handle)
        except Exception as exc:
            _log.warning("workbench teardown failed for %s: %s", ree_id, exc)
            raise HTTPException(status_code=500, detail=f"Workbench teardown failed: {exc}") from exc
        return DeleteReeResponse.model_validate(
            {
                "deleted_at": utc_now(),
                "state": "deleted",
            }
        )


@rees_router.post(
    "/api/v1/rees/{ree_id}/workbench/reprovision",
    operation_id="reprovisionWorkbench",
    response_model=ReprovisionResponse,
    responses=ERROR_RESPONSES,
)
def reprovision_workbench_route(ree_id: str) -> ReprovisionResponse:
    """Replace the workbench container from the current image, keeping REE volume data."""
    try:
        workbench_manager.reprovision(ree_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "reprovision_failed",
                "message": f"Workbench reprovision failed: {exc}",
                "details": None,
                # A fresh container start can fail transiently (image pull,
                # agent hiccup); retrying the reprovision is safe.
                "retryable": True,
            },
        ) from exc
    return ReprovisionResponse.model_validate({"status": "reprovisioned", "ree_id": ree_id})
