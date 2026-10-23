"""The behaviour trace a page is drawn from. Built from checked evidence; spans only annotate it.

Times are seconds from the first journal record, for display. Order never comes from them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# Where a line in a view comes from, from strongest to weakest.
type Provenance = Literal["journal", "git", "inferred", "span", "time", "gap"]
type Tone = Literal["commit", "effect", "gap"]


class ViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StateAt(ViewModel):
    state: str
    t: float | None = None
    ref: str


class Machine(ViewModel):
    """One entity's states during an entry."""

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
    subject: str  # The triggering entity or boundary, and its key.
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


class Row(ViewModel):
    t: float
    lane: str  # Where a note sits, or where a message starts.
    to: str | None = None  # Set for messages.
    label: str
    detail: str | None = None
    provenance: Provenance
    ref: str | None = None
    tone: Tone | None = None


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


class Entry(ViewModel):
    """One line of the trace: setup, an REE operation, or a run of authoring attempts."""

    kind: Literal["setup", "operation", "authoring"]
    name: str
    start: float | None
    end: float | None
    outcome: str | None = None
    # The author action the author watched as a run, for an operation or an REE's creation.
    run: Machine | None = None
    allocation: Machine | None = None
    dispatch: Dispatch | None = None
    attempt: Attempt | None = None
    ree: ReeChange | None = None
    changes: tuple[StepChange, ...] = ()
    rules: tuple[RuleHit, ...] = ()
    spans: tuple[SpanSummary, ...] = ()
    sequence: Sequence | None = None
    # Authoring only.
    operations: dict[str, int] = {}
    attempts: int = 0
    failed: int = 0


class Standing(ViewModel):
    """Every step's evidence standing after one entry; together, the REE's state path."""

    label: str
    kind: Literal["baseline", "operation", "authoring"]
    states: dict[str, str]
    changed: tuple[str, ...]
    sealed: bool


class SourceSummary(ViewModel):
    id: str
    kind: str
    complete: bool


class DossierInfo(ViewModel):
    name: str
    test: str | None = None
    outcome: str | None = None
    revision: str | None = None


class BehaviourTrace(ViewModel):
    """One REE's operations in one dossier."""

    dossier: DossierInfo
    ree: str
    spec_digest: str
    verdict: str
    sealed: bool
    duration: float
    sources: tuple[SourceSummary, ...]
    entries: tuple[Entry, ...]
    steps: tuple[str, ...]
    standings: tuple[Standing, ...]
    reviews: int = 0  # Review attempts on this REE, not drawn until reviews are specified.
