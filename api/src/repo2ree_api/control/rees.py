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
from pydantic import ValidationError

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
from repo2ree_api.control.run_orchestration import (
    append_run_log,
    is_cancel_requested,
    list_runs,
    run_summary,
    start_provisioning_run,
)
from repo2ree_api.control.run_registry import ACTIVE_STATUSES
from repo2ree_api.deps import provider_connections, workbench_manager
from repo2ree_api.pagination import keyset_paginate
from repo2ree_api.workbench.commands import ree_command_span, require_handle
from repo2ree_core.domain.ree.model import Ree, ree_status
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol import ActionResult
from repo2ree_supervisor import WorkbenchHandle

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
    location_id = payload.location_id.strip()
    profile_id = payload.profile_id.strip()

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
            provider_managed = any(
                provider.location_id == location_id for provider in provider_connections.list_providers()
            )
            if provider_managed:
                handle = workbench_manager.provision(
                    rid, name, log=_log_run, location_id=location_id, profile_id=profile_id
                )
            else:
                handle = workbench_manager.reserve_external(rid, name, location_id, profile_id)
        except Exception as exc:  # noqa: BLE001 — provisioning is the workbench's, so any failure is reported as an unavailable run
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
    items = [
        summary
        for handle, manifest in workbench_manager.list_all_manifests()
        if (summary := _summarize(handle, manifest)) is not None
    ]
    if status:
        items = [m for m in items if m.status == status]
    items.sort(key=_ree_page_key, reverse=True)
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_ree_page_key)
    return ReeList.model_validate({"items": page, "next_cursor": next_cursor})


def _summarize(handle: WorkbenchHandle, manifest: dict[str, Any]) -> ReeSummary | None:
    """Project one workbench's REE document onto its listing entry.

    Parsed, not indexed. The projection used to read the document as a dict
    (``ree["subject"]["definition"]["name"]``) in the supervisor, where a shape
    change answers ``""`` instead of raising — the same silent-wrong-answer that
    made every downloaded bundle ``ree.zip``. Here the shape is checked once and
    ``status`` comes from core's own ``ree_status`` rather than a second reading
    of what a seal means.

    A document this control plane cannot parse drops out of the listing rather
    than failing it, matching how an unreachable bench is already treated: the
    two are the same event to a caller — a workbench this node cannot report on.
    """
    try:
        ree = Ree.model_validate(manifest)
    except ValidationError:
        _log.warning("REE %s has a document this control plane cannot parse; omitting it", handle.ree_id)
        return None
    return ReeSummary(
        ree_id=handle.ree_id,
        name=ree.subject.definition.name,
        status=ree_status(ree),
        allocation_id=handle.allocation_id,
        location_id=handle.location_id,
        profile_id=handle.profile_id,
    )


def _ree_page_key(summary: ReeSummary) -> tuple[str, str]:
    return summary.name, summary.ree_id


@rees_router.get(
    "/api/v1/rees/{ree_id}",
    operation_id="getRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def get_ree_route(ree_id: str) -> ReeDocument:
    handle = require_handle(ree_id)
    document = workbench_manager.get_ree_document(handle)
    document["allocation_id"] = handle.allocation_id
    document["location_id"] = handle.location_id
    document["profile_id"] = handle.profile_id
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
    # The workbench returns the same document `getRee` publishes, so it is parsed
    # as one rather than picked apart by key: this view *is* that document plus
    # liveness (which bench, which runs are in flight), and assembling it field
    # by field out of a dict hid that relationship behind an intermediate nobody
    # could typecheck. It also mixed a raising read (`document["ree"]`) with a
    # defaulting one (`document.get("workspace_files", [])`) over the same
    # document; the model's own defaults now settle what may be absent.
    document = ReeDocument.model_validate(workbench_manager.get_ree_state(handle))
    # Runs are this process's own records, not a workbench's, so they are parsed
    # strictly: a summary that will not validate is a bug here rather than a peer
    # speaking a version we do not know, and it should say so loudly.
    runs = [RunSummary.model_validate(run) for run in list_runs(ree_id)]
    return ReeState(
        ree_id=document.ree_id,
        ree=document.ree,
        status=document.status,
        audit=document.audit,
        workbench=WorkbenchStatus(
            status="available",
            workbench_id=handle.workbench_id,
            allocation_id=handle.allocation_id,
            location_id=handle.location_id,
            profile_id=handle.profile_id,
            substrate=handle.observation.substrate if handle.observation else None,
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
