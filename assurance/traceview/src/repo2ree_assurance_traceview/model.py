"""The behaviour trace a page is drawn from. Built from checked evidence; spans only annotate it.

Times are seconds from the first journal record, for display. Order never comes from them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Where a line in a view comes from, from strongest to weakest.
type Provenance = Literal["journal", "git", "inferred", "span", "time", "gap"]
type Tone = Literal["commit", "effect", "gap", "fold"]


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


class SessionMove(ViewModel):
    """A workbench session admitted, refused, or lost: the facts its line is phrased from."""

    kind: Literal["session"] = "session"
    session: str
    state: str
    workbench: str | None = None
    nonce: str | None = None
    reason: str | None = None
    close_code: int | None = None
    # For an admitted workbench seen before: the session its process held before, or that it is a new process.
    returning: str | None = None
    new_process: bool = False


class JournalMark(ViewModel):
    """An API journal opening, or one that ended without closing: a process that crashed."""

    kind: Literal["journal"] = "journal"
    journal: str
    mark: Literal["opened", "crashed"]


class AuthoringFold(ViewModel):
    """The authoring attempts a lifecycle folds into one line."""

    kind: Literal["authoring"] = "authoring"
    attempts: int
    failed: int
    operations: dict[str, int]


type Said = Annotated[SessionMove | JournalMark | AuthoringFold, Field(discriminator="kind")]


class Row(ViewModel):
    t: float
    lane: str  # Where a note sits, or where a message starts.
    to: str | None = None  # Set for messages.
    label: str
    detail: str | None = None
    provenance: Provenance
    ref: str | None = None
    tone: Tone | None = None
    # For a line the page phrases itself, the facts to phrase it from; its label is then empty.
    said: Said | None = None
    # For a dispatch: the workbench session it was sent on.
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
    """One stretch of the lifecycle: an entry of the trace, an action outside every entry, a store's
    workbench sessions, or an API journal's beginning or end."""

    kind: Literal["setup", "operation", "authoring", "action", "session", "epoch"]
    # The entry's or action's name; a session stretch's store; nothing for the API's journals.
    label: str
    outcome: str | None = None
    entry: int | None = None  # Its entry in BehaviourTrace.entries, if it is one.
    ree: str | None = None  # The REE it belongs to, where several are drawn together.
    told: str | None = None  # What the author was told: a run's last state, or the outcome.
    # Where the attempt or the dispatch ended otherwise than the author was told.
    attempt: str | None = None
    dispatch: str | None = None
    first: int  # Its rows in Lifecycle.rows, first to last.
    last: int


class Activity(ViewModel):
    """An activation over rows of the lifecycle: its rows, since its segments may overlap in time."""

    lane: str
    first: int
    last: int
    label: str
    duration: float
    provenance: Provenance = "span"


class Lifecycle(ViewModel):
    """The REE from its creation to its last action, as one sequence of segments in evidence order."""

    lanes: tuple[Lane, ...]
    rows: tuple[Row, ...]
    activations: tuple[Activity, ...]
    segments: tuple[Segment, ...]


class Entry(ViewModel):
    """One line of the trace: setup, an REE operation, or a run of authoring attempts."""

    kind: Literal["setup", "operation", "authoring"]
    name: str
    start: float | None
    end: float | None
    outcome: str | None = None
    # The author action the author watched as a run, for an operation or an REE's creation.
    run: Machine | None = None
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


class HistoryRow(ViewModel):
    part: str
    label: str
    kind: Literal["lifecycle", "field", "receipt"]
    group: str


class HistoryStep(ViewModel):
    operation: str
    ref: str  # The capture that made it.
    states: dict[str, str]
    moved: tuple[str, ...]


class ChangeHistory(ViewModel):
    """The REE after each operation that changed it: every part's state, rows in the order they are drawn."""

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
    """An REE of the same dossier, drawn on a page of its own beside this one."""

    ree: str
    name: str | None = None
    page: str  # Its page, beside this one.
    sealed: bool
    summary: str


class BehaviourTrace(ViewModel):
    """One REE's operations in one dossier."""

    dossier: DossierInfo
    ree: str
    name: str | None = None  # The name its definition gives it.
    spec_digest: str
    verdict: str
    sealed: bool
    duration: float
    sources: tuple[SourceSummary, ...]
    entries: tuple[Entry, ...]
    steps: tuple[str, ...]
    baseline: dict[str, str] = {}  # Each step's standing before the first capture.
    history: ChangeHistory | None = None
    lifecycle: Lifecycle | None = None
    siblings: tuple[Sibling, ...] = ()  # Every REE of the dossier, this one among them, in page order.
    reviews: int = 0  # Review attempts on this REE, not drawn until reviews are specified.
    unreadable_spans: int = 0  # Span records passed over because they could not be read.
