"""Parser contract for dependency sources.

Each ecosystem module (``pypi``, ``conda``, ``oci``, ...) exposes a
``PARSERS`` tuple of ``SourceParser`` entries; ``manifests.py`` aggregates
them into the scan registry. Adding an ecosystem means adding a module and
listing it in the registry — the scan itself never changes. The registry is
in-process for now; if third-party ecosystems ever plug in, this dataclass is
the contract they implement.

Parser obligations (defended by the scan's postconditions and the property
suite): total over arbitrary text — malformed input yields the rows that did
parse, never an exception; names normalized for their ecosystem; every row
cites its source file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from repo2ree_core.domain.dependency import Dependency

# Which side of the lock-merge the parser's rows land on: ``declared`` rows
# come from manifests, ``locked`` rows from lockfiles (and arrive direct=False).
Side = Literal["declared", "locked"]


@dataclass(frozen=True)
class SourceParser:
    format_id: str  # e.g. "requirements-txt"; unique across the registry
    side: Side
    matches: Callable[[str], bool]  # lower-cased basename -> handled?
    parse: Callable[[str, str], list[Dependency]]  # (text, relative path) -> rows
