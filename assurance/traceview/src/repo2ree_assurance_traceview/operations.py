"""The behaviour trace of one REE: setup, the operations that produce evidence, and the authoring between them.

An operation is an author attempt that belongs to a run (acquire_source, build_runtime, …): the run
names its attempt, or, when it failed before it could (its workbench was lost), the attempt's dispatch
names the run. Attempts without a run of their own (definition patches, file writes, lints) are
authoring and are collapsed between operations. Every entry is grouped from the verification of the dossier (the
verifier's artifact, read back), and carries the verdict of each rule occurrence its events triggered.

Order: attempts keep capture order, which step evidence depends on. Setup, which only
the journal records, is merged in by the journal position of each attempt's dispatch, the request
the attempt's record cites, which is how the checker orders Git evidence too. Wall-clock time places
nothing.

Scope: the REE's own history is the Git source that witnesses its Ree transitions. Review histories
of the same REE are not drawn yet (reviews are not specified); they are only counted.

Built in three steps: the REE's history is cut into commits (``_commits``), each commit that
captured an attempt is read as a capture (``_Capture.of``), and a ``_Timeline`` folds them, in
order and with the journal-only setups between them, into entries.

The lifecycle then joins every entry's sequence and the actions no entry draws (a deletion, a
request refused before anything was dispatched) in journal order: the order the author and the
control plane saw them in, where entries keep the order their attempts were captured in.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from repo2ree_assurance_checker.evidence import Event
from repo2ree_assurance_checker.verification import Judgement, VerifiedModel
from repo2ree_assurance_traceview import terms
from repo2ree_assurance_traceview.history import change_history
from repo2ree_assurance_traceview.model import (
    Attempt,
    BehaviourTrace,
    Dispatch,
    DossierInfo,
    Entry,
    Lifecycle,
    Machine,
    ReeChange,
    RuleHit,
    Segment,
    Sequence,
    SourceSummary,
    SpanSummary,
    StateAt,
    StepChange,
)
from repo2ree_assurance_traceview.sequence import build_lifecycle, build_sequence, fold
from repo2ree_assurance_traceview.spans import SpanIndex, timestamp

NOISE = ("websocket", "GET ", "HTTP /workbench/connect")
TOP_SPANS = 6


class _Evidence:
    """One REE's share of a verification: its events in order, and the verdicts they triggered."""

    def __init__(self, model: VerifiedModel, spans: SpanIndex, ree: str) -> None:
        self.model = model
        self.spans = spans
        self.events = model.evidence.ordered([e for e in model.evidence.events if e.partition == ree])
        kinds = {source.id: source.kind for source in model.evidence.sources}
        self.journal = [e for e in self.events if kinds.get(e.source) == "journal"]
        self.position = {e.ref: index for index, e in enumerate(self.journal)}
        own = {e.source for e in self.events if e.subject == terms.REE}
        self.git = [e for e in self.events if kinds.get(e.source) == "git" and e.source in own]
        reviewed = (e for e in self.events if kinds.get(e.source) == "git" and e.source not in own)
        self.reviews = len({e.key for e in reviewed if e.subject == terms.ATTEMPT})
        self.origin = min((timestamp(e.at) for e in self.journal if e.at), default=0.0)
        self.judged = _judged(model.judgements)
        self.flagged = _flagged(model)

    def rel(self, event: Event | None) -> float | None:
        return round(timestamp(event.at) - self.origin, 3) if event is not None and event.at else None

    def rules(self, events: list[Event]) -> tuple[RuleHit, ...]:
        hits = [
            RuleHit(rule=j.rule, verdict=j.verdict, event=j.event, subject=j.subject, key=j.key)
            for ref in dict.fromkeys(e.ref for e in events)  # Git events of one commit share a ref.
            for j in self.judged.get(ref, [])
        ]
        hits += [
            RuleHit(rule=self.flagged[e.ref], verdict="violated", event=e.ref, subject=e.subject, key=e.key)
            for e in {e.ref: e for e in events}.values()
            if e.ref in self.flagged
        ]
        return tuple(hits)

    def machine(self, events: list[Event]) -> Machine:
        facts = {name: str(value) for name, value in events[0].facts.items() if value is not None}
        states = tuple(StateAt(state=e.target_state or "", t=self.rel(e), ref=e.ref) for e in events)
        return Machine(key=events[0].key, states=states, facts=facts)

    def span_summary(self, events: list[Event]) -> tuple[SpanSummary, ...]:
        """The longest spans in the traces these events were recorded in."""
        related = [s for s in self.spans.in_traces(e.trace_id for e in events) if not any(n in s.name for n in NOISE)]
        top = sorted(related, key=lambda span: -span.duration)[:TOP_SPANS]
        return tuple(
            SpanSummary(
                service=span.service,
                name=span.name,
                start=round(span.start - self.origin, 3),
                duration=round(span.duration, 3),
                status=span.status,
            )
            for span in sorted(top, key=lambda span: span.start)
        )


def _judged(judgements: Iterable[Judgement]) -> dict[str, list[Judgement]]:
    """Each invariant occurrence's verdict, by the event that triggered it."""
    judged: dict[str, list[Judgement]] = defaultdict(list)
    for judgement in judgements:
        judged[judgement.event].append(judgement)
    return judged


def _flagged(model: VerifiedModel) -> dict[str, str]:
    """The machine or boundary rule each event broke, by the event."""
    return {
        ref: rule.rule
        for rule in model.result.rules
        if rule.kind in ("machine", "boundary")
        for finding in rule.findings
        if finding.verdict == "violated"
        for ref in finding.evidence
    }


def rees(model: VerifiedModel) -> list[str]:
    """The REEs a dossier holds, each witnessed by its own Git history."""
    return sorted(model.instances.get(terms.REE, {}))


# ================================================
# Journal-only work: setup
# ================================================


@dataclass
class _Setup:
    """Journal-only work: an REE's creation."""

    position: int
    run: list[Event]


def _runs(evidence: _Evidence) -> dict[str, list[Event]]:
    """The author actions the author watched as runs, by action: the long ones, which carry a run_id.

    A synchronous action (an edit, a lint) answers within its request; its attempt is authoring.
    """
    actions: dict[str, list[Event]] = defaultdict(list)
    for event in evidence.journal:
        if event.subject == terms.ACTION and event.kind == "transition":
            actions[event.key].append(event)
    return {key: events for key, events in actions.items() if any(e.facts.get(terms.RUN_ID) for e in events)}


def _setups(evidence: _Evidence, runs: dict[str, list[Event]]) -> list[_Setup]:
    setups = [
        _Setup(evidence.position[events[0].ref], events)
        for events in runs.values()
        if events[0].facts.get(terms.ACTION_NAME) == terms.PROVISION
    ]
    return sorted(setups, key=lambda setup: setup.position)


def _setup_entry(evidence: _Evidence, setup: _Setup) -> Entry:
    run = setup.run
    return Entry(
        kind="setup",
        name="provision",
        start=evidence.rel(run[0]),
        end=evidence.rel(run[-1]),
        outcome=run[-1].target_state,
        run=evidence.machine(run),
        rules=evidence.rules(run),
        spans=evidence.span_summary(run),
        sequence=build_sequence(evidence.spans, runs=run, origin=evidence.origin),
    )


# ================================================
# The REE's history: commits, and the attempts they captured
# ================================================


@dataclass(frozen=True)
class _Commit:
    """One commit of the REE's own history: a capture of an attempt, or a snapshot between attempts."""

    attempt: list[Event]
    receipts: list[Event]
    ree: list[Event]


def _commits(evidence: _Evidence) -> list[_Commit]:
    by_commit: dict[str, list[Event]] = defaultdict(list)
    for event in evidence.git:
        by_commit[event.locator or event.source].append(event)
    return [
        _Commit(
            attempt=[e for e in events if e.subject == terms.ATTEMPT],
            receipts=[e for e in events if e.subject == terms.RECEIPT],
            ree=[e for e in events if e.subject == terms.REE],
        )
        for events in by_commit.values()
    ]


@dataclass(frozen=True)
class _Capture:
    """A commit that captured an attempt, with the dispatch that started it and the run it belongs to."""

    commit: _Commit
    key: str
    operation: str
    outcome: str | None
    changes: list[StepChange]  # What the attempt changed; a baseline is the standing it found.
    exchange: list[Event]
    sent: Event | None
    answered: Event | None
    run: list[Event] | None  # None for authoring: an attempt no watched action names.

    @classmethod
    def of(cls, evidence: _Evidence, commit: _Commit, run_of_attempt: dict[str, list[Event]]) -> _Capture:
        key = commit.attempt[0].key
        exchange = evidence.model.exchanges.get(terms.DISPATCH, {}).get(key)
        journaled = evidence.position
        return cls(
            commit=commit,
            key=key,
            operation=_str(commit.attempt[0].facts.get(terms.OPERATION)) or "unnamed operation",
            outcome=next(
                (_str(e.facts.get(terms.OUTCOME)) for e in commit.attempt if e.target_state == terms.COMPLETED), None
            ),
            changes=[
                StepChange(
                    step=_step(e),
                    before=e.source_state,
                    after=e.target_state or "",
                    cause=_str(e.facts.get(terms.CAUSE)),
                    ref=e.ref,
                )
                for e in commit.receipts
                if e.facts.get(terms.CAUSE) != terms.BASELINE
            ],
            exchange=[e for e in exchange.events if e.ref in journaled] if exchange else [],
            sent=exchange.request if exchange and exchange.request and exchange.request.ref in journaled else None,
            answered=exchange.outcome if exchange and exchange.outcome and exchange.outcome.ref in journaled else None,
            run=run_of_attempt.get(key),
        )

    @property
    def checked(self) -> list[Event]:
        return self.commit.attempt + self.commit.receipts + self.commit.ree + self.exchange


def _operation_entry(evidence: _Evidence, capture: _Capture, run: list[Event], files: Mapping[str, int]) -> Entry:
    attempt, answered = capture.commit.attempt, capture.answered
    commit = next((str(e.facts[terms.COMMIT]) for e in attempt if e.facts.get(terms.COMMIT)), None)
    changed = next((bool(e.facts.get(terms.CHANGED)) for e in attempt if e.target_state == terms.CAPTURED), None)
    first = capture.commit.ree[0] if capture.commit.ree else None
    ree_change = ReeChange(before=first.source_state, after=first.target_state or "") if first else None
    size = files.get(commit) if commit else None
    return Entry(
        kind="operation",
        name=capture.operation,
        start=evidence.rel(run[0]),
        end=evidence.rel(run[-1]),
        outcome=capture.outcome,
        run=evidence.machine(run),
        dispatch=Dispatch(
            sent=capture.sent.ref if capture.sent else None,
            received=answered.ref if answered else None,
            outcome=(
                (_str(answered.facts.get(terms.STATUS)) or answered.message)
                if answered and answered.kind == "receive"
                else (answered.kind if answered else None)
            ),
            start=evidence.rel(capture.sent),
            end=evidence.rel(answered),
        ),
        attempt=Attempt(
            key=capture.key,
            states=tuple(e.target_state or "" for e in attempt),
            outcome=capture.outcome,
            commit=commit,
            changed=changed,
            files=size,
        ),
        ree=ree_change,
        changes=tuple(capture.changes),
        rules=evidence.rules(run + capture.checked),
        spans=evidence.span_summary(run + capture.exchange),
        sequence=build_sequence(
            evidence.spans,
            runs=run,
            exchange=capture.exchange,
            attempt=attempt,
            changes=capture.changes,
            ree=ree_change,
            origin=evidence.origin,
            commit=commit,
            files=size,
        ),
    )


# ================================================
# Folding the history into entries
# ================================================


@dataclass
class _Authoring:
    start: float | None
    position: int | None  # Its first dispatch's place in the journal.
    end: float | None = None
    operations: Counter[str] = field(default_factory=Counter)
    failed: int = 0
    changes: list[StepChange] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


class _Timeline:
    """Folds the REE's commits, in capture order, into entries; keeps each step's standing as it goes."""

    def __init__(self, evidence: _Evidence, setups: list[_Setup], files: Mapping[str, int]) -> None:
        self.evidence = evidence
        self.pending = deque(setups)
        self.files = files
        self.entries: list[Entry] = []
        self.positions: list[int | None] = []  # Each entry's place in the journal, where it has one.
        self.drawn: set[str] = set()  # The actions whose runs the entries draw.
        self.standing: dict[str, str] = {}
        self.baseline: dict[str, str] | None = None  # Each step's standing before the first capture.
        self.authoring: _Authoring | None = None

    def add(self, commit: _Commit, capture: _Capture | None) -> None:
        for event in commit.receipts:
            if capture is None or event.facts.get(terms.CAUSE) == terms.BASELINE:
                self.standing[_step(event)] = event.target_state or ""
        if capture is None:
            return
        if self.baseline is None:
            self.baseline = dict(self.standing)
        if capture.sent is not None:
            self.setups_before(self.evidence.position[capture.sent.ref])
        if capture.run is None:
            self._author(capture)
        else:
            self.close_authoring()
        for change in capture.changes:
            self.standing[change.step] = change.after
        if capture.run is not None:
            self.entries.append(_operation_entry(self.evidence, capture, capture.run, self.files))
            self.positions.append(self.evidence.position.get(capture.run[0].ref))
            self.drawn.add(capture.run[0].key)

    def setups_before(self, position: int | None) -> None:
        """Journal-only entries the journal places before ``position`` (all of them when None)."""
        while self.pending and (position is None or self.pending[0].position < position):
            self.close_authoring()
            setup = self.pending.popleft()
            self.entries.append(_setup_entry(self.evidence, setup))
            self.positions.append(setup.position)
            self.drawn.add(setup.run[0].key)

    def close_authoring(self) -> None:
        authoring, self.authoring = self.authoring, None
        if authoring is None:
            return
        self.entries.append(
            Entry(
                kind="authoring",
                name="authoring",
                start=authoring.start,
                end=authoring.end,
                changes=tuple(authoring.changes),
                rules=self.evidence.rules(authoring.events),
                operations=dict(authoring.operations),
                attempts=sum(authoring.operations.values()),
                failed=authoring.failed,
            )
        )
        self.positions.append(authoring.position)

    def _author(self, capture: _Capture) -> None:
        if self.authoring is None:
            position = self.evidence.position.get(capture.sent.ref) if capture.sent else None
            self.authoring = _Authoring(start=self.evidence.rel(capture.sent), position=position)
        authoring = self.authoring
        authoring.operations[capture.operation] += 1
        authoring.failed += capture.outcome != terms.SUCCEEDED
        authoring.changes += capture.changes
        authoring.events += capture.checked
        authoring.end = self.evidence.rel(capture.answered) if capture.answered else authoring.end


def build_trace(
    model: VerifiedModel,
    spans: SpanIndex,
    *,
    ree: str,
    dossier: DossierInfo,
    commit_files: Mapping[str, int] | None = None,
) -> BehaviourTrace:
    """One REE's behaviour trace, drawn from a verification: its verdicts are the verifier's, never redrawn."""
    evidence = _Evidence(model, spans, ree)
    runs = _runs(evidence)
    run_of_attempt = {
        str(e.facts[terms.ATTEMPT_ID]): events
        for events in runs.values()
        for e in events
        if e.facts.get(terms.ATTEMPT_ID)
    }
    run_of_attempt.update(_runs_by_dispatch(evidence, runs, run_of_attempt, ree))
    timeline = _Timeline(evidence, _setups(evidence, runs), commit_files or {})
    for commit in _commits(evidence):
        timeline.add(commit, _Capture.of(evidence, commit, run_of_attempt) if commit.attempt else None)
    timeline.close_authoring()
    timeline.setups_before(None)

    standing = timeline.standing
    steps = [s for s in terms.STEP_ORDER if s in standing] + sorted(s for s in standing if s not in terms.STEP_ORDER)
    instance = model.instances.get(terms.REE, {}).get(ree)
    replayed = model.history(terms.REE, ree)
    result = model.result
    return BehaviourTrace(
        dossier=dossier,
        ree=ree,
        spec_digest=result.spec_digest,
        verdict=result.verdict,
        sealed=instance is not None and instance.current == terms.SEALED,
        duration=max((entry.end or 0 for entry in timeline.entries), default=0.0),
        sources=tuple(SourceSummary(id=s.id, kind=s.kind, complete=s.complete) for s in result.sources),
        entries=tuple(timeline.entries),
        steps=tuple(steps),
        baseline=timeline.baseline or {},
        history=change_history(replayed) if replayed else None,
        lifecycle=_lifecycle(evidence, timeline),
        reviews=evidence.reviews,
        unreadable_spans=spans.unreadable,
    )


def _runs_by_dispatch(
    evidence: _Evidence, runs: dict[str, list[Event]], named: Mapping[str, list[Event]], ree: str
) -> dict[str, list[Event]]:
    """The runs no attempt was named for, by the attempt whose dispatch names them.

    A run whose workbench was lost fails without naming its attempt; the attempt's dispatch still
    carries the run's id. Reads that watch a run carry its id too, and are not it. An REE's creation
    dispatches its own patch under the creation's run id, so creations are left out: they are setups,
    never an attempt's run.
    """
    claimed = {id(events) for events in named.values()}
    by_id = {
        run_id: events
        for events in runs.values()
        if events[0].facts.get(terms.ACTION_NAME) not in (terms.PROVISION, *terms.READS) and id(events) not in claimed
        for run_id in {_str(e.facts.get(terms.RUN_ID)) for e in events} - {None}
    }
    found: dict[str, list[Event]] = {}
    for key, exchange in evidence.model.exchanges.get(terms.DISPATCH, {}).items():
        request = exchange.request
        if key in named or request is None or request.partition != ree:
            continue
        events = by_id.get(_str(request.facts.get(terms.RUN_ID)) or "")
        if events is not None and id(events) not in claimed:
            found[key] = events
            claimed.add(id(events))
    return found


def _dispatches_by_run(evidence: _Evidence) -> dict[str, list[Event]]:
    """Each dispatch exchange this REE's journal records, by the run its request names."""
    journaled = evidence.position
    found: dict[str, list[Event]] = defaultdict(list)
    for exchange in evidence.model.exchanges.get(terms.DISPATCH, {}).values():
        request = exchange.request
        run_id = _str(request.facts.get(terms.RUN_ID)) if request is not None else None
        if request is not None and run_id and request.ref in journaled:
            found[run_id] += [e for e in exchange.events if e.ref in journaled]
    return found


def _loose(evidence: _Evidence, drawn: set[str]) -> list[tuple[int, list[Event]]]:
    """The actions no entry draws, with their journal position: neither a read nor any entry's run or attempt."""
    actions: dict[str, list[Event]] = defaultdict(list)
    for event in evidence.journal:
        if event.subject == terms.ACTION and event.kind == "transition":
            actions[event.key].append(event)
    return [
        (evidence.position[events[0].ref], events)
        for key, events in actions.items()
        if key not in drawn
        and events[0].facts.get(terms.ACTION_NAME) not in terms.READS
        and not any(e.facts.get(terms.ATTEMPT_ID) for e in events)
    ]


def _lifecycle(evidence: _Evidence, timeline: _Timeline) -> Lifecycle:
    """Every entry's sequence and every action no entry draws, in journal order.

    An entry the journal does not place (authoring without a recorded dispatch) stays after the one before it.
    """
    placed: list[tuple[int, Segment, Sequence]] = []
    last = -1
    for index, (entry, position) in enumerate(zip(timeline.entries, timeline.positions, strict=True)):
        last = position if position is not None else last
        segment = Segment(kind=entry.kind, label=entry.name, outcome=entry.outcome, entry=index, first=0, last=0)
        if entry.kind == "authoring":
            counts = " · ".join(f"{count}\N{MULTIPLICATION SIGN} {name}" for name, count in entry.operations.items())
            failed = f" · {entry.failed} failed" if entry.failed else ""
            label = f"authoring · {entry.attempts} attempt{'s' if entry.attempts != 1 else ''}{failed}"
            placed.append((last, segment, fold(entry.start, label, counts)))
        elif entry.sequence is not None:
            placed.append((last, segment, entry.sequence))
    dispatched = _dispatches_by_run(evidence)
    for position, events in _loose(evidence, timeline.drawn):
        name = _str(events[0].facts.get(terms.ACTION_NAME)) or "action"
        segment = Segment(kind="action", label=name, outcome=events[-1].target_state, first=0, last=0)
        # A run that dispatched an attempt no capture recorded (its workbench died) still shows its dispatch.
        run_ids = {_str(e.facts.get(terms.RUN_ID)) for e in events} - {None}
        exchange = [e for run_id in sorted(r for r in run_ids if r) for e in dispatched.get(run_id, [])]
        sequence = build_sequence(evidence.spans, runs=events, exchange=exchange, origin=evidence.origin)
        placed.append((position, segment, sequence))
    placed.sort(key=lambda part: part[0])  # Stable: an unplaced entry keeps its place after its predecessor.
    return build_lifecycle([(segment, sequence) for _, segment, sequence in placed])


def _step(event: Event) -> str:
    return event.key.split("/", 1)[1] if "/" in event.key else event.key


def _str(value: object) -> str | None:
    return None if value is None else str(value)
