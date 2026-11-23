from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from repo2ree_repoview.documents import Document
from repo2ree_repoview.repository import ROOT

EXPORTS = ROOT / "reports/exports"
SPEC_EXPORT = (sys.executable, "-m", "repo2ree_assurance_checker", "export")
ZONES_EXPORT = (sys.executable, "scripts/zones.py", "export")
CONTRACTS_EXPORT = (sys.executable, "-m", "scripts.contracts", "export")
VOCABULARY_EXPORT = (sys.executable, "-m", "scripts.vocabulary", "export")


def operations_export(verifications: Iterable[str]) -> tuple[str, ...]:
    return (sys.executable, "-m", "repo2ree_assurance_traceview", "operations", *verifications)


def exported(command: tuple[str, ...]) -> str:
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout


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


type Scalar = str | bool | int | float | None


class _Condition(Document):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OneOf(_Condition):
    values: tuple[Scalar, ...] = Field(alias="in")


class NotEqual(_Condition):
    value: Scalar = Field(alias="not")


class PerFact(_Condition):
    fact: str = Field(alias="per")
    cases: dict[str, tuple[Scalar, ...]] = Field(alias="in")


class Holds(_Condition):
    fact: str = Field(alias="has")


type Condition = PerFact | OneOf | NotEqual | Holds | Scalar
type Conditions = dict[str, Condition]


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
    constrained: bool = True


class EntitySide(Document):
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
    kind: Literal["guard"]
    where: Conditions


class ExclusionRequirement(Document):
    kind: Literal["exclusion"]
    entity: str
    in_states: tuple[str, ...]


class Beside(Document):
    reached: tuple[str, ...]
    where: Conditions


class NextRequirement(Document):
    kind: Literal["next"]
    entity: str
    reached: tuple[str, ...]
    where: Conditions
    beside: Beside | None = None


class EachRequirement(Document):
    kind: Literal["each"]
    entity: str
    reached: tuple[str, ...]
    fact: str
    of: str


type Requirement = Annotated[
    EntityRequirement
    | MessageRequirement
    | GuardRequirement
    | ExclusionRequirement
    | NextRequirement
    | EachRequirement,
    Field(discriminator="kind"),
]


class Invariant(Document):
    id: str
    pattern: str
    summary: str
    when: Trigger
    require: Requirement | None = None
    eventually: tuple[str, ...] = ()


class MachineEdge(Document):
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    by: tuple[str, ...]


class SubMachine(Document):
    kind: Literal["lifecycle", "field", "receipt"]
    name: str
    group: str
    states: tuple[str, ...]
    edges: tuple[MachineEdge, ...]
    bulk: tuple[str, ...] = ()
    keyed: bool = False


class AggregateReceipt(Document):
    about: tuple[str, ...] = ()
    applies_without_declaration: bool = False
    rests_on: tuple[str, ...] = ()
    made_from: tuple[str, ...] = ()
    cleared_by: tuple[str, ...] = ()
    keyed: bool = False


class Aggregate(Document):
    name: str
    receipt_entity: str | None = None
    receipts: dict[str, AggregateReceipt] = Field(default_factory=dict)
    machines: tuple[SubMachine, ...]


class Spec(Export):
    FORMAT = "repo2ree-behaviour-spec/1"

    digest: str
    vocabulary_digest: str
    components: dict[str, Component]
    entities: dict[str, Entity]
    boundaries: dict[str, Boundary]
    invariants: tuple[Invariant, ...]
    aggregates: dict[str, Aggregate] = Field(default_factory=dict)


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
    path: str
    zone: str | None


class Zones(Export):
    FORMAT = "repo2ree-zones/1"

    zones: tuple[Zone, ...]
    files: tuple[Placed, ...]
    problems: tuple[str, ...]


class GraphVocabulary(Document):
    name: str
    origin: Literal["spec", "contract", "source"]
    summary: str
    where: str
    names: tuple[str, ...]
    anchored: bool


class GraphEdge(Document):
    target: str
    relation: Literal["equals", "within", "derived"]
    sources: tuple[str, ...]
    extras: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


class GraphClaim(Document):
    site: str
    reason: str


class VocabularyGraph(Export):
    FORMAT = "repo2ree-vocabulary/1"

    roots: tuple[str, ...]
    vocabularies: tuple[GraphVocabulary, ...]
    edges: tuple[GraphEdge, ...]
    exceptions: tuple[GraphClaim, ...]
    problems: tuple[str, ...]


class GeneratedContract(Document):
    name: str
    path: str
    summary: str
    between: str
    rendered_by: str
    write: str

    @property
    def file(self) -> Path:
        return ROOT / self.path

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.file.read_bytes()).hexdigest()


type ContractName = Literal[
    "cli-schema", "protocol-schema", "openapi", "behaviour-schema", "ree-schema", "ree-layout", "environment"
]


class Contracts(Export):
    FORMAT = "repo2ree-contracts/1"

    contracts: tuple[GeneratedContract, ...]
    fixtures: tuple[str, ...]

    @classmethod
    def read(cls, path: Path = EXPORTS / "contracts.json") -> Contracts:
        return cls.model_validate_json(path.read_bytes())

    def entry(self, name: ContractName) -> GeneratedContract:
        found = next((contract for contract in self.contracts if contract.name == name), None)
        if found is None:
            raise LookupError(f"the contract registry names no {name!r}")
        return found


type Provenance = Literal["journal", "git", "inferred", "span", "time", "gap"]
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


class ShowcaseTier(Document):
    tier: str
    surface: Literal["api", "cli", "browser"]
    environments: tuple[str, ...]
    recipe: str
    run: str | None


class ShowcaseTest(Document):
    surface: Literal["api", "cli", "browser"]
    workflow: Literal["authoring", "review"] | None
    file: str
    tier: str
    run: str | None
    test: str | None


class Showcase(Document):
    name: str
    kind: Literal["showcase", "feature"]
    environment: str | None
    tests: tuple[ShowcaseTest, ...]


class ShowcaseRuns(Export):
    FORMAT = "repo2ree-showcase-runs/2"

    tiers: tuple[ShowcaseTier, ...]
    showcases: tuple[Showcase, ...]

    def runs(self) -> tuple[str, ...]:
        return tuple(tier.run for tier in self.tiers if tier.run)


class KeptFor(Document):
    kind: Literal["showed_problems", "new_arcs", "new_reached"]
    items: tuple[str, ...] = ()
    files: dict[str, int] = Field(default_factory=dict)


class CaseOrigin(Document):
    kind: Literal["hand_written", "searched"]
    search: str | None = None
    run: str | None = None
    kept_for: KeptFor | None = None


class ExerciseProblem(Document):
    kind: str
    step: int | None = None
    rule: str
    subject: str
    detail: str = ""


class CaseExpectation(Document):
    kind: Literal["conforms", "shows"]
    problems: tuple[ExerciseProblem, ...] = ()


class CaseReached(Document):
    spec_digest: str
    items: tuple[str, ...]


class CampaignSettings(Document):
    examples: int
    steps: int
    keep: int
    least: int
    hours: float | None
    workers: int


class KeptCase(Document):
    case: str
    kept_for: KeptFor
    steps: int
    worker: int


class Campaign(Document):
    run: str
    search: str
    settings: CampaignSettings
    commit: str
    dirty: bool
    machine: str | None
    started: str
    ended: str | None
    rounds: int
    rounds_found: int
    unconfirmed: int
    kept: tuple[KeptCase, ...]
    exit: int | None


class StepRun(Document):
    step: int
    ree: str
    operation: str
    words: tuple[str, ...] | None
    exit: int | None
    status: str | None
    failure: str | None
    scope: str | None
    commit: str | None
    changed: bool | None


class CaseReplay(Document):
    workdir: str
    when: str
    spec_digest: str
    problems: tuple[ExerciseProblem, ...]
    reached: tuple[str, ...]
    steps: tuple[StepRun, ...]
    session: str


class CaseFile(Document):
    path: str
    arcs: int
    unique: int
    stale: bool


class CaseCoverage(Document):
    commit: str
    dirty: bool
    files: tuple[CaseFile, ...]


class ExerciseCase(Document):
    digest: str
    exercise: dict[str, Any]
    origin: CaseOrigin
    expects: CaseExpectation
    reached: CaseReached
    unique_reached: tuple[str, ...]
    coverage: CaseCoverage | None
    replay: CaseReplay | None

    @property
    def rees(self) -> tuple[str, ...]:
        return tuple(self.exercise.get("rees", ()))

    @property
    def steps(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.exercise.get("steps", ()))

    @property
    def drifts(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.exercise.get("drifts", ()))

    @property
    def faults(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.exercise.get("faults", ()))


class Exercises(Export):
    FORMAT = "repo2ree-exercises/1"

    campaigns: tuple[Campaign, ...]
    cases: tuple[ExerciseCase, ...]
