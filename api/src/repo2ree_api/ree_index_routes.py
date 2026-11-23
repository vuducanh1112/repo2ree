from __future__ import annotations

from fastapi import APIRouter, Query

from repo2ree_api.contracts import ERROR_RESPONSES, ReeIndexList
from repo2ree_api.deps import ree_index
from repo2ree_api.pagination import keyset_paginate
from repo2ree_api.ree_index import ReeIndexEntry

ree_index_router = APIRouter(tags=["ree-index"])


@ree_index_router.get(
    "/api/v1/ree-index",
    operation_id="listReeIndex",
    response_model=ReeIndexList,
    responses=ERROR_RESPONSES,
)
def list_ree_index_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None, ge=1),
    deposited_only: bool = Query(False),
) -> ReeIndexList:
    items = list(reversed(ree_index.list_all(deposited_only=deposited_only)))
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_index_page_key)
    return ReeIndexList(items=page, next_cursor=next_cursor)


def _index_page_key(entry: ReeIndexEntry) -> tuple[str, str]:
    return entry.sealed_at, entry.subject_digest
