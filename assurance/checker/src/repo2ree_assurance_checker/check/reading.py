from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue

from repo2ree_assurance_checker.spec import ITEM, KEYED

TOKEN = re.compile(r"[a-z_]+|\[\*\]|\[\$name\]")
_DOCUMENT_ROOTS = frozenset({"seal", "subject"})
_ITEM_NAMES = ("name", "experiment_name")


def _name(item: JsonValue) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in _ITEM_NAMES:
        if isinstance(name := item.get(key), str):
            return name
    return None


def items(value: JsonValue) -> list[tuple[str, JsonValue]]:
    if isinstance(value, list):
        return [(name, item) for item in value if (name := _name(item)) is not None]
    if isinstance(value, dict):
        return list(value.items())
    return []


def values(
    document: Mapping[str, JsonValue], path: str, item: str | None = None, *, whole: bool = False
) -> list[tuple[str | None, JsonValue]]:
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
    if isinstance(value, dict):
        return any(held(inner) for inner in value.values())
    return value not in (None, "", [])


def within(value: JsonValue, path: str) -> JsonValue:
    for token in TOKEN.findall(path):
        value = value.get(token) if isinstance(value, dict) else None
    return value


@dataclass(frozen=True)
class Judged:
    subject: str
    held: bool | None
    reason: str = ""
