"""The overview's reading of the two documents it draws from: the specification and the zones.

Both come from their owners as JSON (``python -m repo2ree_conformance export``,
``python scripts/zones.py export``), so the views never import the checker or the
guard. These classes are this package's own typed view of those documents, and a
document in a format they do not know is refused rather than half read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SPEC_FORMAT = "repo2ree-behaviour-spec/1"
ZONES_FORMAT = "repo2ree-zones/1"


def _require(document: dict[str, Any], expected: str) -> None:
    if document.get("format") != expected:
        raise ValueError(f"expected a {expected} document, got {document.get('format')!r}")


def _names(values: list[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


def _named_lists(values: dict[str, list[str]] | None) -> dict[str, tuple[str, ...]]:
    return {name: tuple(items) for name, items in (values or {}).items()}


# ---------------------------------------------------------------------------- specification


@dataclass(frozen=True)
class Component:
    name: str
    process: str
    summary: str


@dataclass(frozen=True)
class Transition:
    source: str
    targets: tuple[str, ...]
    why: str


@dataclass(frozen=True)
class Entity:
    name: str
    owner: str
    key: str
    partition: str
    evidence: str
    summary: str
    initial: tuple[str, ...]
    terminal: tuple[str, ...]
    settles_before_close: bool | str
    states: dict[str, str]
    facts: dict[str, str]
    required: dict[str, tuple[str, ...]]
    allowed: dict[str, tuple[str, ...]]
    meanings: dict[str, dict[str, str]]
    groups: dict[str, dict[str, tuple[str, ...]]]
    transitions: tuple[Transition, ...]
    edges: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Side:
    """One side of a citation: an entity's record on reaching a state, or a boundary message."""

    kind: str
    entity: str = ""
    reached: str = ""
    message: str = ""
    fact: str = ""


@dataclass(frozen=True)
class Citation:
    by: Side
    cited: Side


@dataclass(frozen=True)
class Boundary:
    name: str
    sender: str
    receiver: str
    key: str
    partition: str
    summary: str
    request: str
    responses: tuple[str, ...]
    messages: dict[str, str]
    facts: dict[str, dict[str, str]]
    required: dict[str, tuple[str, ...]]
    cites: tuple[Citation, ...]


@dataclass(frozen=True)
class Trigger:
    """``entity`` (an entity reaching ``to``, optionally ``from``) or ``message`` (a boundary message)."""

    kind: str
    entity: str = ""
    source: tuple[str, ...] = ()
    to: tuple[str, ...] = ()
    boundary: str = ""
    message: str = ""
    where: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Requirement:
    """``entity``, ``message``, ``guard`` (a condition on the trigger), or ``exclusion``."""

    kind: str
    entity: str = ""
    key_from: str = ""
    reached: tuple[str, ...] = ()
    order: str = "any"
    boundary: str = ""
    message: str = ""
    in_states: tuple[str, ...] = ()
    where: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Invariant:
    id: str
    pattern: str
    summary: str
    when: Trigger
    require: Requirement | None
    eventually: tuple[str, ...]


@dataclass(frozen=True)
class Spec:
    digest: str
    vocabulary_digest: str
    components: dict[str, Component]
    entities: dict[str, Entity]
    boundaries: dict[str, Boundary]
    invariants: tuple[Invariant, ...]


def _side(raw: dict[str, Any]) -> Side:
    return Side(
        kind=raw["kind"],
        entity=raw.get("entity", ""),
        reached=raw.get("reached", ""),
        message=raw.get("message", ""),
        fact=raw.get("fact", ""),
    )


def _entity(raw: dict[str, Any]) -> Entity:
    return Entity(
        name=raw["name"],
        owner=raw["owner"],
        key=raw["key"],
        partition=raw["partition"],
        evidence=raw["evidence"],
        summary=raw["summary"],
        initial=_names(raw["initial"]),
        terminal=_names(raw["terminal"]),
        settles_before_close=raw["settles_before_close"],
        states=dict(raw["states"]),
        facts=dict(raw["facts"]),
        required=_named_lists(raw["required"]),
        allowed=_named_lists(raw["allowed"]),
        meanings={fact: dict(values) for fact, values in raw["meanings"].items()},
        groups={fact: _named_lists(groups) for fact, groups in raw["groups"].items()},
        transitions=tuple(Transition(t["from"], _names(t["to"]), t.get("why", "")) for t in raw["transitions"]),
        edges=_named_lists(raw["edges"]),
    )


def _boundary(raw: dict[str, Any]) -> Boundary:
    return Boundary(
        name=raw["name"],
        sender=raw["sender"],
        receiver=raw["receiver"],
        key=raw["key"],
        partition=raw["partition"],
        summary=raw["summary"],
        request=raw["request"],
        responses=_names(raw["responses"]),
        messages=dict(raw["messages"]),
        facts={message: dict(facts) for message, facts in raw["facts"].items()},
        required=_named_lists(raw["required"]),
        cites=tuple(Citation(_side(cite["by"]), _side(cite["cited"])) for cite in raw["cites"]),
    )


def _trigger(raw: dict[str, Any]) -> Trigger:
    return Trigger(
        kind=raw["kind"],
        entity=raw.get("entity", ""),
        source=_names(raw.get("from")),
        to=_names(raw.get("to")),
        boundary=raw.get("boundary", ""),
        message=raw.get("message", ""),
        where=dict(raw.get("where") or {}),
    )


def _requirement(raw: dict[str, Any] | None) -> Requirement | None:
    if raw is None:
        return None
    return Requirement(
        kind=raw["kind"],
        entity=raw.get("entity", ""),
        key_from=raw.get("key_from", ""),
        reached=_names(raw.get("reached")),
        order=raw.get("order", "any"),
        boundary=raw.get("boundary", ""),
        message=raw.get("message", ""),
        in_states=_names(raw.get("in_states")),
        where=dict(raw.get("where") or {}),
    )


def read_spec(document: dict[str, Any]) -> Spec:
    _require(document, SPEC_FORMAT)
    return Spec(
        digest=document["digest"],
        vocabulary_digest=document["vocabulary_digest"],
        components={name: Component(**raw) for name, raw in document["components"].items()},
        entities={name: _entity(raw) for name, raw in document["entities"].items()},
        boundaries={name: _boundary(raw) for name, raw in document["boundaries"].items()},
        invariants=tuple(
            Invariant(
                id=raw["id"],
                pattern=raw["pattern"],
                summary=raw["summary"],
                when=_trigger(raw["when"]),
                require=_requirement(raw.get("require")),
                eventually=_names(raw.get("eventually")),
            )
            for raw in document["invariants"]
        ),
    )


# ---------------------------------------------------------------------------- zones


@dataclass(frozen=True)
class Entry:
    path: str
    zone: str
    group: str
    description: str


@dataclass(frozen=True)
class Group:
    name: str
    summary: str
    entries: tuple[Entry, ...]


@dataclass(frozen=True)
class Zone:
    name: str
    summary: str
    protected: bool
    groups: tuple[Group, ...]


@dataclass(frozen=True)
class Zones:
    zones: tuple[Zone, ...]
    # Each tracked file and the zone it belongs to; None when no entry claims it.
    files: dict[str, str | None]
    problems: tuple[str, ...]

    @property
    def entries(self) -> list[Entry]:
        return [entry for zone in self.zones for group in zone.groups for entry in group.entries]

    def zone(self, name: str) -> Zone:
        return next(zone for zone in self.zones if zone.name == name)


def read_zones(document: dict[str, Any]) -> Zones:
    _require(document, ZONES_FORMAT)
    zones = tuple(
        Zone(
            name=zone["name"],
            summary=zone["summary"],
            protected=bool(zone["protected"]),
            groups=tuple(
                Group(
                    group["name"],
                    group["summary"],
                    tuple(
                        Entry(entry["path"], zone["name"], group["name"], entry["description"])
                        for entry in group["entries"]
                    ),
                )
                for group in zone["groups"]
            ),
        )
        for zone in document["zones"]
    )
    files = {placed["path"]: placed["zone"] for placed in document["files"]}
    return Zones(zones, files, tuple(document["problems"]))
