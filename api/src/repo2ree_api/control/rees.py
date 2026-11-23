from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query

from repo2ree_api.clock import utc_now
from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    DeleteReeResponse,
    ReeCreatePayload,
    ReeDocument,
    ReeList,
    ReeState,
    ReeSummary,
    RunSummary,
    WorkbenchStatus,
)
from repo2ree_api.control.run_orchestration import append_run_log, list_runs, run_summary, start_provisioning_run
from repo2ree_api.control.run_registry import ACTIVE_STATUSES
from repo2ree_api.deps import command_dispatcher, ree_registry, store_registry, workbench_connections
from repo2ree_api.pagination import keyset_paginate
from repo2ree_api.storage import author_actions
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import ree_command_span, require_handle
from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree, ReeStatus, ree_status
from repo2ree_supervisor import ReeRoute

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
    return _create_in_store(ree_id, payload.name or ree_id[:8], payload.store_id.strip(), payload)


def _create_in_store(ree_id: str, name: str, store_id: str, payload: ReeCreatePayload) -> RunSummary:
    if store_registry.get(store_id) is None:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    def _runner(rid: str, run_id: str) -> ActionResult:
        def _log_run(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        author_actions.learn(store_id=store_id)
        ree_registry.create(rid, name, store_id)
        try:
            handle = require_handle(rid)
            command_dispatcher.init_ree(handle, name)
        except Exception as exc:  # noqa: BLE001
            ree_registry.delete(rid)
            detail = exc.detail if isinstance(exc, HTTPException) else exc
            _log_run("system", "error", f"The REE was not created in store {store_id}: {detail}")
            return ActionResult.failed(
                "unavailable", f"The REE was not created in store {store_id}: {detail}", origin="api", retryable=True
            )
        document = _provisioned_document(handle)
        return ActionResult(status="succeeded", outputs={"ree": document})

    run_state = start_provisioning_run(ree_id=ree_id, request_payload=payload.model_dump(), runner=_runner)
    return RunSummary.model_validate(run_summary(run_state))


def _provisioned_document(handle: ReeRoute) -> dict[str, Any]:
    document = command_dispatcher.get_ree_document(handle)
    _remember(handle, document.ree)
    return {**document.model_dump(mode="json"), "ree_id": handle.ree_id}


def _remember(handle: ReeRoute, ree: Ree) -> None:
    ree_registry.update_summary(handle.ree_id, name=ree.subject.definition.name, status=ree_status(ree))


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
    items = [
        ReeSummary(
            ree_id=record.ree_id,
            name=record.name,
            status=cast(ReeStatus, record.status),
            location_id=record.store_id,
        )
        for record in ree_registry.all()
    ]
    if status:
        items = [m for m in items if m.status == status]
    items.sort(key=_ree_page_key, reverse=True)
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_ree_page_key)
    return ReeList.model_validate({"items": page, "next_cursor": next_cursor})


def _ree_page_key(summary: ReeSummary) -> tuple[str, str]:
    return summary.name, summary.ree_id


@rees_router.get(
    "/api/v1/rees/{ree_id}",
    operation_id="getRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def get_ree_route(ree_id: str) -> ReeDocument:
    with author_api_action("view_ree", ree_id):
        handle = require_handle(ree_id)
        document = command_dispatcher.get_ree_document(handle)
        _remember(handle, document.ree)
        return ReeDocument.of(handle.ree_id, document, location_id=handle.store_id, store_id=handle.store_id)


@rees_router.get(
    "/api/v1/rees/{ree_id}/state",
    operation_id="getReeState",
    response_model=ReeState,
    responses=ERROR_RESPONSES,
)
def get_ree_state_route(ree_id: str) -> ReeState:
    with author_api_action("view_ree_state", ree_id):
        return _ree_state(ree_id)


def _ree_state(ree_id: str) -> ReeState:
    handle = require_handle(ree_id)
    document = ReeDocument.of(handle.ree_id, command_dispatcher.get_ree_state(handle))
    runs = [RunSummary.model_validate(run) for run in list_runs(ree_id)]
    bench = next(
        (
            candidate
            for candidate in workbench_connections.list_workbenches()
            if candidate.workbench_id == handle.workbench_id
        ),
        None,
    )
    return ReeState(
        ree_id=document.ree_id,
        ree=document.ree,
        status=document.status,
        audit=document.audit,
        steps=document.steps,
        workbench=WorkbenchStatus(
            status="available",
            workbench_id=handle.workbench_id,
            location_id=handle.store_id,
            build=bench.build if bench else BuildInfo(),
            executor_build=bench.executor_build if bench else BuildInfo(),
        ),
        workspace_files=document.workspace_files,
        ree_files=document.ree_files,
        active_runs=[run for run in runs if run.status in ACTIVE_STATUSES],
    )


@rees_router.delete(
    "/api/v1/rees/{ree_id}",
    operation_id="deleteRee",
    response_model=DeleteReeResponse,
    responses=ERROR_RESPONSES,
)
def delete_ree_route(ree_id: str) -> DeleteReeResponse:
    with author_api_action("delete_ree", ree_id):
        record = ree_registry.get(ree_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")
        author_actions.learn(store_id=record.store_id)
        with ree_command_span("delete", ree_id):
            command_dispatcher.delete_ree(require_handle(ree_id))
        ree_registry.delete(ree_id)
        return _deleted()


def _deleted() -> DeleteReeResponse:
    return DeleteReeResponse.model_validate({"deleted_at": utc_now(), "state": "deleted"})
