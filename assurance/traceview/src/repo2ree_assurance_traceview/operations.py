"""The behaviour trace of one REE: setup, the operations that produce evidence, and the authoring between them.

An operation is an author attempt that belongs to a run (acquire_source, build_runtime, …).
Attempts without a run of their own (definition patches, file writes, lints) are authoring and are
collapsed between operations. Every entry is grouped from the verification of the dossier (the
verifier's artifact, read back), and carries the verdict of each rule occurrence its events triggered.

Order: attempts keep capture order, which step evidence depends on. Setup and release, which only
the journal records, are merged in by the journal position of each attempt's dispatch, the request
the attempt's record cites, which is how the checker orders Git evidence too. Wall-clock time places
nothing.

Scope: the REE's own history is the Git source that witnesses its Ree transitions. Review histories
of the same REE are not drawn yet (reviews are not specified); they are only counted.

Built in three steps: the REE's history is cut into commits (``_commits``), each commit that
captured an attempt is read as a capture (``_Capture.of``), and a ``_Timeline`` folds them, in
order and with the journal-only setups between them, into entries and the step standings after each.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from repo2ree_assurance_checker.evidence import Event
from repo2ree_assurance_checker.verification import Judgement, VerifiedModel
from repo2ree_assurance_traceview import terms
from repo2ree_assurance_traceview.model import (
    Attempt,
    BehaviourTrace,
    Dispatch,
    DossierInfo,
    Entry,
    Machine,
    ReeChange,
    RuleHit,
    SourceSummary,
    SpanSummary,
    Standing,
    StateAt,
    StepChange,
)
from repo2ree_assurance_traceview.sequence import build_sequence
from repo2ree_assurance_traceview.spans import SpanIndex, timestamp

NOISE = ("websocket", "GET ", "HTTP /provider/connect", "HTTP /workbench/connect")
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
# Journal-only work: setup and release
# ================================================


@dataclass
class _Setup:
    """Journal-only work: an REE's creation with the allocation moves it made, or an allocation's release."""

    position: int
    run: list[Event]
    allocation: list[Event]


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
    allocations = [e for e in evidence.journal if e.subject == terms.ALLOCATION and e.kind == "transition"]
    setups: list[_Setup] = []
    claimed: set[str] = set()
    for events in runs.values():
        if events[0].facts.get(terms.ACTION_NAME) != terms.PROVISION:
            continue
        first, last = evidence.position[events[0].ref], evidence.position[events[-1].ref]
        moved = [e for e in allocations if first <= evidence.position[e.ref] <= last]
        claimed |= {e.ref for e in moved}
        setups.append(_Setup(first, events, moved))
    rest: dict[str, list[Event]] = defaultdict(list)
    for event in allocations:
        if event.ref not in claimed:
            rest[event.key].append(event)
    setups += [_Setup(evidence.position[events[0].ref], [], events) for events in rest.values()]
    return sorted(setups, key=lambda setup: setup.position)


def _setup_entry(evidence: _Evidence, setup: _Setup) -> Entry:
    if setup.run:
        run, moved = setup.run, setup.allocation
        return Entry(
            kind="setup",
            name="provision",
            start=evidence.rel(run[0]),
            end=evidence.rel(run[-1]),
            outcome=run[-1].target_state,
            run=evidence.machine(run),
            allocation=evidence.machine(moved) if moved else None,
            rules=evidence.rules(run + moved),
            spans=evidence.span_summary(run + moved),
            sequence=build_sequence(evidence.spans, runs=run, allocations=moved),
        )
    moved = setup.allocation
    released = moved[-1].target_state in terms.RELEASED
    return Entry(
        kind="setup",
        name="release" if released else "allocation",
        start=evidence.rel(moved[0]),
        end=evidence.rel(moved[-1]),
        outcome=moved[-1].target_state,
        allocation=evidence.machine(moved),
        rules=evidence.rules(moved),
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
                _str(answered.facts.get(terms.STATUS))
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
    end: float | None = None
    operations: Counter[str] = field(default_factory=Counter)
    failed: int = 0
    changes: list[StepChange] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


class _Timeline:
    """Folds the REE's commits, in capture order, into entries and the step standings after each."""

    def __init__(self, evidence: _Evidence, setups: list[_Setup], files: Mapping[str, int]) -> None:
        self.evidence = evidence
        self.pending = deque(setups)
        self.files = files
        self.entries: list[Entry] = []
        self.standings: list[Standing] = []
        self.standing: dict[str, str] = {}
        self.ree_state: str | None = None
        self.authoring: _Authoring | None = None

    def add(self, commit: _Commit, capture: _Capture | None) -> None:
        for event in commit.receipts:
            if capture is None or event.facts.get(terms.CAUSE) == terms.BASELINE:
                self.standing[_step(event)] = event.target_state or ""
        reached = commit.ree[-1].target_state if commit.ree else self.ree_state
        if capture is None:
            self.ree_state = reached
            return
        if not self.standings:
            self.standings.append(
                Standing(label="created", kind="baseline", states=dict(self.standing), changed=(), sealed=False)
            )
        if capture.sent is not None:
            self.setups_before(self.evidence.position[capture.sent.ref])
        if capture.run is None:
            self._author(capture)
        else:
            self.close_authoring()
        self.ree_state = reached
        for change in capture.changes:
            self.standing[change.step] = change.after
        if capture.run is not None:
            self.entries.append(_operation_entry(self.evidence, capture, capture.run, self.files))
            self._stand(capture.operation, "operation", tuple(c.step for c in capture.changes))

    def setups_before(self, position: int | None) -> None:
        """Journal-only entries the journal places before ``position`` (all of them when None)."""
        while self.pending and (position is None or self.pending[0].position < position):
            self.close_authoring()
            self.entries.append(_setup_entry(self.evidence, self.pending.popleft()))

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
        self._stand("authoring", "authoring", tuple(dict.fromkeys(change.step for change in authoring.changes)))

    def _author(self, capture: _Capture) -> None:
        if self.authoring is None:
            self.authoring = _Authoring(start=self.evidence.rel(capture.sent))
        authoring = self.authoring
        authoring.operations[capture.operation] += 1
        authoring.failed += capture.outcome != terms.SUCCEEDED
        authoring.changes += capture.changes
        authoring.events += capture.checked
        authoring.end = self.evidence.rel(capture.answered) if capture.answered else authoring.end

    def _stand(self, label: str, kind: Literal["operation", "authoring"], changed: tuple[str, ...]) -> None:
        sealed = self.ree_state == terms.SEALED
        self.standings.append(
            Standing(label=label, kind=kind, states=dict(self.standing), changed=changed, sealed=sealed)
        )


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
    timeline = _Timeline(evidence, _setups(evidence, runs), commit_files or {})
    for commit in _commits(evidence):
        timeline.add(commit, _Capture.of(evidence, commit, run_of_attempt) if commit.attempt else None)
    timeline.close_authoring()
    timeline.setups_before(None)

    standing = timeline.standing
    steps = [s for s in terms.STEP_ORDER if s in standing] + sorted(s for s in standing if s not in terms.STEP_ORDER)
    instance = model.instances.get(terms.REE, {}).get(ree)
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
        standings=tuple(timeline.standings),
        reviews=evidence.reviews,
        unreadable_spans=spans.unreadable,
    )


def _step(event: Event) -> str:
    return event.key.split("/", 1)[1] if "/" in event.key else event.key


def _str(value: object) -> str | None:
    return None if value is None else str(value)
