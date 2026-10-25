"""The overview's reading of the documents it draws from: the specification, the zones, and the operations.

Each comes from its owner as JSON (``python -m repo2ree_assurance_checker export``,
``python scripts/zones.py export``, ``python -m repo2ree_assurance_traceview operations``),
so the views never import the checker, the guard, or traceview. These models are this
package's own typed view of those documents, and a document in a format they do not
know is refused rather than half read.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from typing import Annotated, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from repo2ree_repoview.documents import Document
from repo2ree_repoview.repository import ROOT

# The owners' exports, and the commands that produce them.
SPEC_EXPORT = (sys.executable, "-m", "repo2ree_assurance_checker", "export")
ZONES_EXPORT = (sys.executable, "scripts/zones.py", "export")


def operations_export(verifications: Iterable[str]) -> tuple[str, ...]:
    """The catalogue of operations traceview folds from these verifications (paths from the repository root)."""
    return (sys.executable, "-m", "repo2ree_assurance_traceview", "operations", *verifications)


def exported(command: tuple[str, ...]) -> str:
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def shown(command: tuple[str, ...]) -> str:
    """The export command as a reader would type it."""
    return " ".join(("python", *command[1:]))


class Export(Document):
    FORMAT: ClassVar[str]

    format: str

    @model_validator(mode="before")
    @classmethod
    def _known_format(cls, data: Any) -> Any:
        found = data.get("format") if isinstance(data, dict) else None
        if found != cls.FORMAT:
            raise ValueError(f"expected a {cls.FORMAT} document, got {found!r}")
        return data


# ---------------------------------------------------------------------------- conditions

type Scalar = str | bool | int | float | None


class _Condition(Document):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OneOf(_Condition):
    """``{"in": [...]}``: the fact is one of the values."""

    values: tuple[Scalar, ...] = Field(alias="in")


class NotEqual(_Condition):
    """``{"not": value}``: the fact is present and is not the value."""

    value: Scalar = Field(alias="not")


class PerFact(_Condition):
    """``{"per": fact, "in": {...}}``: the values allowed depend on the trigger's ``fact``."""

    fact: str = Field(alias="per")
    cases: dict[str, tuple[Scalar, ...]] = Field(alias="in")


type Condition = PerFact | OneOf | NotEqual | Scalar
type Conditions = dict[str, Condition]


# ---------------------------------------------------------------------------- specification


class Component(Document):
    name: str
    process: str
    summary: str


class Transition(Document):
    source: str = Field(alias="from")
    targets: tuple[str, ...] = Field(alias="to")
    why: str = ""


class Entity(Document):
    name: str
    owner: str
    key: str
    partition: str
    evidence: str
    summary: str
    initial: tuple[str, ...]
    terminal: tuple[str, ...]
    settles_before_close: bool | Literal["final"]
    states: dict[str, str]
    facts: dict[str, str]
    required: dict[str, tuple[str, ...]]
    allowed: dict[str, tuple[str, ...]]
    meanings: dict[str, dict[str, str]]
    groups: dict[str, dict[str, tuple[str, ...]]]
    transitions: tuple[Transition, ...]
    edges: dict[str, tuple[str, ...]]


class EntitySide(Document):
    """An entity's record on reaching a state, naming (or named by) the other side in ``fact``."""

    kind: Literal["entity"]
    entity: str
    reached: str
    fact: str


class MessageSide(Document):
    kind: Literal["message"]
    message: str
    fact: str = ""


type Side = Annotated[EntitySide | MessageSide, Field(discriminator="kind")]


class Citation(Document):
    by: Side
    cited: Side


class Boundary(Document):
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


class EntityTrigger(Document):
    """An entity reaching one of ``to``, optionally from one of ``source``."""

    kind: Literal["entity"]
    entity: str
    source: tuple[str, ...] = Field(default=(), alias="from")
    to: tuple[str, ...]
    where: Conditions = Field(default_factory=dict)


class MessageTrigger(Document):
    kind: Literal["message"]
    boundary: str
    message: str
    where: Conditions = Field(default_factory=dict)


type Trigger = Annotated[EntityTrigger | MessageTrigger, Field(discriminator="kind")]


class EntityRequirement(Document):
    kind: Literal["entity"]
    entity: str
    key_from: str
    reached: tuple[str, ...]
    where: Conditions = Field(default_factory=dict)
    order: Literal["any", "before"] = "any"


class MessageRequirement(Document):
    kind: Literal["message"]
    boundary: str
    message: str
    key_from: str
    order: Literal["any", "before"] = "any"


class GuardRequirement(Document):
    """A condition on the trigger itself."""

    kind: Literal["guard"]
    where: Conditions


class ExclusionRequirement(Document):
    kind: Literal["exclusion"]
    entity: str
    in_states: tuple[str, ...]


type Requirement = Annotated[
    EntityRequirement | MessageRequirement | GuardRequirement | ExclusionRequirement, Field(discriminator="kind")
]


class Invariant(Document):
    id: str
    pattern: str
    summary: str
    when: Trigger
    require: Requirement | None = None
    eventually: tuple[str, ...] = ()


class Spec(Export):
    FORMAT = "repo2ree-behaviour-spec/1"

    digest: str
    vocabulary_digest: str
    components: dict[str, Component]
    entities: dict[str, Entity]
    boundaries: dict[str, Boundary]
    invariants: tuple[Invariant, ...]


# ---------------------------------------------------------------------------- zones


class Entry(Document):
    path: str
    description: str


class Group(Document):
    name: str
    summary: str
    entries: tuple[Entry, ...]


class Zone(Document):
    name: str
    summary: str
    protected: bool
    groups: tuple[Group, ...]

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(entry for group in self.groups for entry in group.entries)


class Placed(Document):
    """A tracked file and the zone it belongs to; None when no entry claims it."""

    path: str
    zone: str | None


class Zones(Export):
    FORMAT = "repo2ree-zones/1"

    zones: tuple[Zone, ...]
    files: tuple[Placed, ...]
    problems: tuple[str, ...]


# ---------------------------------------------------------------------------- operations

# Where a line comes from, from strongest to weakest, as traceview names it.
type Provenance = Literal["journal", "git", "inferred", "span", "time", "gap"]
# What an operation's evidence shows of one lane in every instance, strongest first.
type Reach = Literal["checked", "exchanged", "span", "none"]


class Lane(Document):
    id: str
    label: str
    process: str


class Line(Document):
    lane: str
    to: str | None = None
    label: str
    provenance: Provenance
    t: float
    seen: int


class Instance(Document):
    source: str
    test: str | None
    ree: str
    outcome: str | None
    duration: float | None
    verdict: str


class Tally(Document):
    rule: str
    passed: int = 0
    violated: int = 0
    inconclusive: int = 0


class Operation(Document):
    name: str
    outcome: str | None
    kind: Literal["setup", "operation"]
    instances: tuple[Instance, ...]
    representative: int
    lines: tuple[Line, ...]
    elsewhere: tuple[Line, ...]
    reach: dict[str, Reach]
    rules: tuple[Tally, ...]


class Undrawn(Document):
    source: str
    test: str | None = None
    verdict: str | None = None
    reason: str


class Operations(Export):
    FORMAT = "repo2ree-operations/1"

    lanes: tuple[Lane, ...]
    operations: tuple[Operation, ...]
    undrawn: tuple[Undrawn, ...] = ()
