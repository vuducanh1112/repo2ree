from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReeRoute:
    ree_id: str
    workbench_id: str
    store_id: str
