from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

type Provenance = Literal["journal", "git", "inferred", "span", "time", "gap"]
type Tone = Literal["commit", "effect", "gap", "fold"]


class ViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StateAt(ViewModel):
    state: str
    t: float | None = None
    ref: str


class Machine(ViewModel):
    key: str
    states: tuple[StateAt, ...]
    facts: dict[str, str] = {}


class StepChange(ViewModel):
    step: str
    before: str | None
    after: str
    cause: str | None = None
    ref: str


class RuleHit(ViewModel):
    rule: str
    verdict: Literal["passed", "violated", "inconclusive"]
    event: str
    subject: str
    key: str


class SpanSummary(ViewModel):
    service: str
    name: str
    start: float
    duration: float
    status: str


class Dispatch(ViewModel):
    sent: str | None
    received: str | None
    outcome: str | None
    start: float | None
    end: float | None


class Attempt(ViewModel):
    key: str
    states: tuple[str, ...]
    outcome: str | None
    commit: str | None
    changed: bool | None
    files: int | None


class ReeChange(ViewModel):
    before: str | None
    after: str


class Lane(ViewModel):
    id: str
    label: str
    process: str


class SessionMove(ViewModel):
    kind: Literal["session"] = "session"
    session: str
    state: str
    workbench: str | None = None
    nonce: str | None = None
    reason: str | None = None
    close_code: int | None = None
    returning: str | None = None
    new_process: bool = False


class JournalMark(ViewModel):
    kind: Literal["journal"] = "journal"
    journal: str
    mark: Literal["opened", "crashed"]


class AuthoringFold(ViewModel):
    kind: Literal["authoring"] = "authoring"
    attempts: int
    failed: int
    operations: dict[str, int]


type Said = Annotated[SessionMove | JournalMark | AuthoringFold, Field(discriminator="kind")]


class Row(ViewModel):
    t: float
    lane: str
    to: str | None = None
    label: str
    detail: str | None = None
    provenance: Provenance
    ref: str | None = None
    tone: Tone | None = None
    said: Said | None = None
    session: str | None = None


class Activation(ViewModel):
    lane: str
    start: float
    end: float
    label: str
    provenance: Provenance = "span"


class Sequence(ViewModel):
    lanes: tuple[Lane, ...]
    rows: tuple[Row, ...]
    activations: tuple[Activation, ...]


class Segment(ViewModel):
    kind: Literal["setup", "operation", "authoring", "action", "session", "epoch"]
    label: str
    outcome: str | None = None
    entry: int | None = None
    ree: str | None = None
    told: str | None = None
    attempt: str | None = None
    dispatch: str | None = None
    first: int
    last: int


class Activity(ViewModel):
    lane: str
    first: int
    last: int
    label: str
    duration: float
    provenance: Provenance = "span"


class Lifecycle(ViewModel):
    lanes: tuple[Lane, ...]
    rows: tuple[Row, ...]
    activations: tuple[Activity, ...]
    segments: tuple[Segment, ...]


class Entry(ViewModel):
    kind: Literal["setup", "operation", "authoring"]
    name: str
    start: float | None
    end: float | None
    outcome: str | None = None
    run: Machine | None = None
    dispatch: Dispatch | None = None
    attempt: Attempt | None = None
    ree: ReeChange | None = None
    changes: tuple[StepChange, ...] = ()
    rules: tuple[RuleHit, ...] = ()
    spans: tuple[SpanSummary, ...] = ()
    sequence: Sequence | None = None
    operations: dict[str, int] = {}
    attempts: int = 0
    failed: int = 0


class HistoryRow(ViewModel):
    part: str
    label: str
    kind: Literal["lifecycle", "field", "receipt"]
    group: str


class HistoryStep(ViewModel):
    operation: str
    ref: str
    states: dict[str, str]
    moved: tuple[str, ...]


class ChangeHistory(ViewModel):
    rows: tuple[HistoryRow, ...]
    steps: tuple[HistoryStep, ...]


class SourceSummary(ViewModel):
    id: str
    kind: str
    complete: bool


class DossierInfo(ViewModel):
    name: str
    test: str | None = None
    outcome: str | None = None
    revision: str | None = None


class Sibling(ViewModel):
    ree: str
    name: str | None = None
    page: str
    sealed: bool
    summary: str


class Drawn(ViewModel):
    revision: str
    dirty: bool
    at: str


class BehaviourTrace(ViewModel):
    dossier: DossierInfo
    ree: str
    name: str | None = None
    spec_digest: str
    verdict: str
    sealed: bool
    duration: float
    sources: tuple[SourceSummary, ...]
    entries: tuple[Entry, ...]
    steps: tuple[str, ...]
    baseline: dict[str, str] = {}
    history: ChangeHistory | None = None
    lifecycle: Lifecycle | None = None
    siblings: tuple[Sibling, ...] = ()
    reviews: int = 0
    unreadable_spans: int = 0
    drawn: Drawn | None = None
