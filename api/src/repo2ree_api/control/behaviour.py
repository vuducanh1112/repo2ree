"""Behaviour evidence for collectors: the owners' journals and persisted state, read only.

A deployment is distributed, so the control plane is the one place a collector
can rely on reaching. It serves what the API process's owners wrote; nothing
here interprets it. The state snapshot carries the journal positions read around
it, its cut, so the checker knows which journal records it must agree with.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    BehaviourArchive,
    BehaviourArchiveList,
    BehaviourJournal,
    BehaviourJournalList,
    BehaviourPositions,
    BehaviourState,
)
from repo2ree_api.deps import store_registry, workbench_client, workbench_connections
from repo2ree_api.settings import service_settings
from repo2ree_supervisor import WorkbenchUnavailableError
from repo2ree_telemetry.behaviour import journal_file, journal_files, positions, records_after

behaviour_router = APIRouter(tags=["behaviour"])

# The REE archives this control plane served, beside the journals. Not a journal:
# what a collector needs to place a client's downloaded copy, not owner behaviour.
ARCHIVES = "ree-archives.ndjson"
_archives_lock = threading.Lock()


def journal_positions() -> dict[str, int]:
    return positions(service_settings.BEHAVIOUR_JOURNAL_DIR)


def record_archive(ree_id: str, sha256: str, size: int, before: dict[str, int]) -> None:
    """Note an archive as served, with the journal positions read before building it and now: its cut."""
    directory = service_settings.BEHAVIOUR_JOURNAL_DIR
    after = positions(directory)
    cut = {journal_id: [before.get(journal_id, 0), position] for journal_id, position in after.items()}
    line = json.dumps({"ree_id": ree_id, "sha256": sha256, "size": size, "cut": cut}, separators=(",", ":"))
    with _archives_lock:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ARCHIVES).open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())


@behaviour_router.get(
    "/api/v1/behaviour/archives",
    response_model=BehaviourArchiveList,
    responses=ERROR_RESPONSES,
    operation_id="listBehaviourArchives",
)
def list_behaviour_archives() -> BehaviourArchiveList:
    path = service_settings.BEHAVIOUR_JOURNAL_DIR / ARCHIVES
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.is_file() else []
    return BehaviourArchiveList(
        archives=[BehaviourArchive.model_validate_json(line) for line in lines if line.endswith("\n")]
    )


@behaviour_router.get(
    "/api/v1/behaviour/journals",
    response_model=BehaviourJournalList,
    responses=ERROR_RESPONSES,
    operation_id="listBehaviourJournals",
)
def list_behaviour_journals() -> BehaviourJournalList:
    directory = service_settings.BEHAVIOUR_JOURNAL_DIR
    current = positions(directory)
    return BehaviourJournalList(
        journals=[
            BehaviourJournal(id=file.id, process=file.process, epoch=file.epoch, last_seq=current.get(file.id, 0))
            for file in journal_files(directory)
        ]
    )


@behaviour_router.get(
    "/api/v1/behaviour/journals/{journal_id}",
    responses={
        **ERROR_RESPONSES,
        200: {"description": "The journal's complete records as written, one JSON object per line"},
    },
    response_class=Response,
    operation_id="readBehaviourJournal",
)
def read_behaviour_journal(
    journal_id: str, after: int = Query(0, ge=0, description="Only records with a higher sequence number")
) -> Response:
    file = journal_file(service_settings.BEHAVIOUR_JOURNAL_DIR, journal_id)
    if file is None:
        raise HTTPException(status_code=404, detail=f"no behaviour journal {journal_id}")
    return Response(records_after(file.path, after), media_type="application/x-ndjson")


@behaviour_router.get(
    "/api/v1/behaviour/positions",
    response_model=BehaviourPositions,
    responses=ERROR_RESPONSES,
    operation_id="getBehaviourPositions",
)
def get_behaviour_positions() -> BehaviourPositions:
    return BehaviourPositions(positions=positions(service_settings.BEHAVIOUR_JOURNAL_DIR))


@behaviour_router.get(
    "/api/v1/behaviour/state",
    response_model=BehaviourState,
    responses=ERROR_RESPONSES,
    operation_id="getBehaviourState",
)
def get_behaviour_state() -> BehaviourState:
    """Owners write their store and then journal the change, so the stores are read inside the cut."""
    directory = service_settings.BEHAVIOUR_JOURNAL_DIR
    before = positions(directory)
    runs: dict[str, dict[str, Any]] = {}
    for path in sorted(service_settings.RUN_REGISTRY_DIR.glob("*/state.json")):
        try:
            runs[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue  # Removed with its REE while listing.
    after = positions(directory)
    cut = {journal_id: (before.get(journal_id, 0), position) for journal_id, position in after.items()}
    return BehaviourState(cut=cut, runs=runs)


def _store_workbench(store_id: str) -> str:
    if store_registry.get(store_id) is None:
        raise HTTPException(status_code=404, detail=f"no store {store_id}")
    workbench_id = workbench_connections.store_workbench(store_id)
    if workbench_id is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "store_unavailable",
                "message": f"No workbench is serving store {store_id} right now",
                "details": {"store_id": store_id},
                "retryable": True,
            },
        )
    return workbench_id


@behaviour_router.get(
    "/api/v1/behaviour/stores/{store_id}/journals",
    response_model=BehaviourJournalList,
    responses=ERROR_RESPONSES,
    operation_id="listStoreBehaviourJournals",
)
def list_store_behaviour_journals(store_id: str) -> BehaviourJournalList:
    """The journals the workbench serving the store keeps in it, read through that workbench."""
    workbench_id = _store_workbench(store_id)
    try:
        listed = workbench_client.list_journals(workbench_id)
    except WorkbenchUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return BehaviourJournalList(
        journals=[
            BehaviourJournal(id=item.id, process=item.process, epoch=item.epoch, last_seq=item.last_seq)
            for item in listed.journals
        ]
    )


@behaviour_router.get(
    "/api/v1/behaviour/stores/{store_id}/journals/{journal_id}",
    responses={
        **ERROR_RESPONSES,
        200: {"description": "The journal's complete records as written, one JSON object per line"},
    },
    response_class=Response,
    operation_id="readStoreBehaviourJournal",
)
def read_store_behaviour_journal(
    store_id: str,
    journal_id: str,
    after: int = Query(0, ge=0, description="Only records with a higher sequence number"),
) -> Response:
    workbench_id = _store_workbench(store_id)
    try:
        data = b"".join(workbench_client.read_journal(workbench_id, journal_id, after))
    except WorkbenchUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=f"no behaviour journal {journal_id} in store {store_id}") from exc
    return Response(data, media_type="application/x-ndjson")
