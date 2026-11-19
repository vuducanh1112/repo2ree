"""Reading a committed document: what a path names in it, item by item, and what a rule held a commit to."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue

from repo2ree_assurance_checker.spec import ITEM, KEYED

TOKEN = re.compile(r"[a-z_]+|\[\*\]|\[\$name\]")
# Paths that start here are read from the document itself; every other one from its subject.
_DOCUMENT_ROOTS = frozenset({"seal", "subject"})
_ITEM_NAMES = ("name", "experiment_name")


def _name(item: JsonValue) -> str | None:
    """An item's name: an REE's items are named ``name``, a review's ``experiment_name``."""
    if not isinstance(item, dict):
        return None
    for key in _ITEM_NAMES:
        if isinstance(name := item.get(key), str):
            return name
    return None


def items(value: JsonValue) -> list[tuple[str, JsonValue]]:
    """A list's items by their names, or an object's members by their keys."""
    if isinstance(value, list):
        return [(name, item) for item in value if (name := _name(item)) is not None]
    if isinstance(value, dict):
        return list(value.items())
    return []


def values(
    document: Mapping[str, JsonValue], path: str, item: str | None = None, *, whole: bool = False
) -> list[tuple[str | None, JsonValue]]:
    """What a path names in a document, each with the item it names; ``[$name]`` is ``item``. An REE's paths are
    read from its subject but for ``seal`` and ``subject``; a ``whole`` document's, a review's, from its top."""
    tokens = TOKEN.findall(path)
    rooted = whole or (tokens and tokens[0] in _DOCUMENT_ROOTS)
    base: JsonValue = dict(document) if rooted else document.get("subject")
    found: list[tuple[str | None, JsonValue]] = [(item, base)]
    for token in tokens:
        reached: list[tuple[str | None, JsonValue]] = []
        for named, value in found:
            if token == KEYED:
                reached.extend(items(value))
            elif token == ITEM:
                reached.append((named, dict(items(value)).get(named) if named is not None else None))
            else:
                reached.append((named, value.get(token) if isinstance(value, dict) else None))
        found = reached
    return found


def value(document: Mapping[str, JsonValue], path: str, item: str | None = None, *, whole: bool = False) -> JsonValue:
    found = values(document, path, item, whole=whole)
    return found[0][1] if len(found) == 1 else None


def held(value: JsonValue) -> bool:
    """Whether a part is set: present, and not empty, an object only when something in it is."""
    if isinstance(value, dict):
        return any(held(inner) for inner in value.values())
    return value not in (None, "", [])


def within(value: JsonValue, path: str) -> JsonValue:
    for token in TOKEN.findall(path):
        value = value.get(token) if isinstance(value, dict) else None
    return value


@dataclass(frozen=True)
class Judged:
    """One thing a rule held one commit to: ``None`` where the commit cannot evidence it."""

    subject: str
    held: bool | None
    reason: str = ""
