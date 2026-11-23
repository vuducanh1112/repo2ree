from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from repo2ree_ree.dependency import Dependency

Side = Literal["declared", "locked"]


@dataclass(frozen=True)
class SourceParser:
    format_id: str
    side: Side
    matches: Callable[[str], bool]
    parse: Callable[[str, str], list[Dependency]]
