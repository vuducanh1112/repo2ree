"""The HTTP surface over :mod:`repo2ree_api.ree_index`.

Split from the index itself for two reasons that both run the same direction.
``deps`` builds the index singleton, so the store has to sit below the
composition root, while a router has to sit above it — one module cannot be
both. And keeping the store below ``contracts`` is what makes it *unable* to see
the wire shape, so ``entry_from_manifest`` projecting from the sealed manifest
is enforced by import-linter rather than by a comment. That matters more than
the file count: reading an entry off a response model would publish a shape that
disagrees with what a peer rebuilds from a bundle.

Separate from ``control`` for a different reason. The fleet routes there answer
"what is running right now"; this one answers "what did this node produce that
outlives it", which is the whole point of the index.

Read-only for now. Depositing is the write half and lives in
:mod:`repo2ree_api.deposit`; its routes belong here too, above both the index
and the adapters, because publishing a deposit has to record its attestation and
neither of those two may reach up to the other.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from repo2ree_api.contracts import ERROR_RESPONSES, ReeIndexList
from repo2ree_api.deps import ree_index
from repo2ree_api.pagination import keyset_paginate

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
    """Every REE sealed on this node, newest first.

    ``deposited_only`` narrows to entries some archive has issued an identifier
    for — the subset another node could cite. The rest are local seals, real
    here but not yet citable anywhere else.

    Note the order is the reverse of the store's: the index's canonical order is
    ascending, because that is what a resumable ``since=`` cursor and a stable
    snapshot digest need, while a reader wants the most recent seal first.
    """
    items: list[dict[str, Any]] = [
        entry.model_dump() for entry in reversed(ree_index.list_all(deposited_only=deposited_only))
    ]
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_index_page_key)
    return ReeIndexList.model_validate({"items": page, "next_cursor": next_cursor})


def _index_page_key(entry: dict[str, Any]) -> tuple[str, str]:
    """The keyset cursor's key, matching the store's total order.

    Immutable per entry: both components are settled at seal and never change,
    so pages cannot shift under a caller mid-pagination the way they would under
    any key derived from mutable state.
    """
    return str(entry.get("sealed_at", "")), str(entry.get("subject_digest", ""))
