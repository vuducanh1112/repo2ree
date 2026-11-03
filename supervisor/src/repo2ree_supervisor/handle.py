"""Where an REE's commands go: the REE, its store, and the workbench serving that store now."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReeRoute:
    ree_id: str
    # The workbench serving the REE's store when the route was taken; every op on it goes there.
    workbench_id: str
    store_id: str
