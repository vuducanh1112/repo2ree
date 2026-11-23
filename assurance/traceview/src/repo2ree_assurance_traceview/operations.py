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
    AuthoringFold,
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
from repo2ree_assurance_traceview.sequence import (
    build_lifecycle,
    build_sequence,
    epoch_sequence,
    fold,
    invocation,
    session_sequence,
)
from repo2ree_assurance_traceview.spans import Span, SpanIndex, timestamp

NOISE = ("websocket", "GET ", "HTTP /workbench/connect")
TOP_SPANS = 6


class _Evidence:
    def __init__(self, model: VerifiedModel, spans: SpanIndex, ree: str) -> None:
        self.model = model
        self.spans = spans
        self.events = model.evidence.ordered([e for e in model.evidence.events if e.partition == ree])
        kinds = {source.id: source.kind for source in model.evidence.sources}
        self.journal = [e for e in self.events if kinds.get(e.source) == "journal"]
        self.position = {e.ref: index for index, e in enumerate(self.journal)}
        self.everything = model.evidence.ordered([e for e in model.evidence.events if kinds.get(e.source) == "journal"])
        self.order = {e.ref: index for index, e in enumerate(self.everything)}
        self.store = next(
            (
                str(e.facts[terms.STORE_ID])
                for e in self.journal
                if e.subject == terms.ACTION and e.facts.get(terms.ACTION_NAME) == terms.PROVISION
                if e.facts.get(terms.STORE_ID)
            ),
            None,
        )
        own = {e.source for e in self.events if e.subject == terms.REE}
        self.git = [e for e in self.events if kinds.get(e.source) == "git" and e.source in own]
        reviewed = (e for e in self.events if kinds.get(e.source) == "git" and e.source not in own)
        self.reviews = len({e.key for e in reviewed if e.subject == terms.ATTEMPT})
        self.origin = min((timestamp(e.at) for e in self.everything if e.at), default=0.0)
        self.judged = _judged(model.judgements)
        self.flagged = _flagged(model)

    def rel(self, event: Event | None) -> float | None:
        return round(timestamp(event.at) - self.origin, 3) if event is not None and event.at else None

    def at(self, t: float) -> float:
        return round(t - self.origin, 3)

    def rules(self, events: list[Event]) -> tuple[RuleHit, ...]:
        hits = [
            RuleHit(rule=j.rule, verdict=j.verdict, event=j.event, subject=j.subject, key=j.key)
            for ref in dict.fromkeys(e.ref for e in events)
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

    def span_summary(self, events: list[Event], ran: Span | None = None) -> tuple[SpanSummary, ...]:
        found = self.spans.subtree(ran) if ran is not None else self.spans.in_traces(e.trace_id for e in events)
        related = [s for s in found if not any(n in s.name for n in NOISE)]
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
    judged: dict[str, list[Judgement]] = defaultdict(list)
    for judgement in judgements:
        judged[judgement.event].append(judgement)
    return judged


def _flagged(model: VerifiedModel) -> dict[str, str]:
    return {
        ref: rule.rule
        for rule in model.result.rules
        if rule.kind in ("machine", "boundary")
        for finding in rule.findings
        if finding.verdict == "violated"
        for ref in finding.evidence
    }


def rees(model: VerifiedModel) -> list[str]:
    return sorted(model.instances.get(terms.REE, {}))


@dataclass
class _Setup:
    position: int
    run: list[Event]


def _runs(evidence: _Evidence) -> dict[str, list[Event]]:
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


@dataclass(frozen=True)
class _Commit:
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
    commit: _Commit
    key: str
    operation: str
    outcome: str | None
    changes: list[StepChange]
    exchange: list[Event]
    sent: Event | None
    answered: Event | None
    run: list[Event] | None
    ran: Span | None = None

    @classmethod
    def of(cls, evidence: _Evidence, commit: _Commit, run_of_attempt: dict[str, list[Event]]) -> _Capture:
        key = commit.attempt[0].key
        exchange = _command(evidence, key)
        journaled = evidence.position
        run = run_of_attempt.get(key)
        run_id = next((_str(e.facts[terms.RUN_ID]) for e in commit.attempt if e.facts.get(terms.RUN_ID)), None)
        ran = evidence.spans.run(run_id) if run is None and exchange is None and run_id else None
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
            run=run,
            ran=ran if ran is not None and any(invocation(s) for s in evidence.spans.ancestors(ran)) else None,
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
    ran = capture.ran
    return Entry(
        kind="operation",
        name=capture.operation,
        start=evidence.rel(run[0]) if run else evidence.at(ran.start) if ran else None,
        end=evidence.rel(run[-1]) if run else evidence.at(ran.end) if ran else None,
        outcome=capture.outcome,
        run=evidence.machine(run) if run else None,
        dispatch=None
        if capture.sent is None and answered is None
        else Dispatch(
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
        spans=evidence.span_summary(run + capture.exchange, ran),
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
            ran=ran,
        ),
    )


@dataclass
class _Authoring:
    start: float | None
    position: int | None
    end: float | None = None
    operations: Counter[str] = field(default_factory=Counter)
    failed: int = 0
    changes: list[StepChange] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


class _Timeline:
    def __init__(self, evidence: _Evidence, setups: list[_Setup], files: Mapping[str, int]) -> None:
        self.evidence = evidence
        self.pending = deque(setups)
        self.files = files
        self.entries: list[Entry] = []
        self.positions: list[int | None] = []
        self.drawn: set[str] = set()
        self.standing: dict[str, str] = {}
        self.baseline: dict[str, str] | None = None
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
        if capture.run is None and capture.ran is None:
            self._author(capture)
        else:
            self.close_authoring()
        for change in capture.changes:
            self.standing[change.step] = change.after
        if capture.run is not None:
            self.entries.append(_operation_entry(self.evidence, capture, capture.run, self.files))
            self.positions.append(self.evidence.position.get(capture.run[0].ref))
            self.drawn.add(capture.run[0].key)
        elif capture.ran is not None:
            self.entries.append(_operation_entry(self.evidence, capture, [], self.files))
            self.positions.append(None)

    def setups_before(self, position: int | None) -> None:
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


def _timeline(
    model: VerifiedModel, spans: SpanIndex, ree: str, commit_files: Mapping[str, int] | None
) -> tuple[_Evidence, _Timeline]:
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
    return evidence, timeline


def build_trace(
    model: VerifiedModel,
    spans: SpanIndex,
    *,
    ree: str,
    dossier: DossierInfo,
    commit_files: Mapping[str, int] | None = None,
) -> BehaviourTrace:
    evidence, timeline = _timeline(model, spans, ree, commit_files)
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
    claimed = {id(events) for events in named.values()}
    by_id = {
        run_id: events
        for events in runs.values()
        if events[0].facts.get(terms.ACTION_NAME) not in (terms.PROVISION, *terms.READS) and id(events) not in claimed
        for run_id in {_str(e.facts.get(terms.RUN_ID)) for e in events} - {None}
    }
    found: dict[str, list[Event]] = {}
    for key, exchange in _commands(evidence).items():
        request = exchange.request
        if key in named or request is None or request.partition != ree:
            continue
        events = by_id.get(_str(request.facts.get(terms.RUN_ID)) or "")
        if events is not None and id(events) not in claimed:
            found[key] = events
            claimed.add(id(events))
    return found


def _dispatches_by_run(evidence: _Evidence) -> dict[str, list[Event]]:
    journaled = evidence.position
    found: dict[str, list[Event]] = defaultdict(list)
    for exchange in _commands(evidence).values():
        request = exchange.request
        run_id = _str(request.facts.get(terms.RUN_ID)) if request is not None else None
        if request is not None and run_id and request.ref in journaled:
            found[run_id] += [e for e in exchange.events if e.ref in journaled]
    return found


@dataclass(frozen=True)
class _Command:
    events: list[Event]

    @property
    def request(self) -> Event | None:
        return next((event for event in self.events if event.kind == "send"), None)

    @property
    def outcome(self) -> Event | None:
        return next((event for event in reversed(self.events) if event.kind in {"receive", "abandon"}), None)


def _commands(evidence: _Evidence) -> dict[str, _Command]:
    exchanges = evidence.model.exchanges
    keys = {*exchanges.get(terms.START_RUN, {}), *exchanges.get(terms.FOLLOW_RUN, {})}
    return {key: command for key in keys if (command := _command(evidence, key)) is not None}


def _command(evidence: _Evidence, key: str) -> _Command | None:
    parts = [evidence.model.exchanges.get(name, {}).get(key) for name in (terms.START_RUN, terms.FOLLOW_RUN)]
    events = [event for part in parts if part is not None for event in part.events]
    return _Command(events) if events else None


def _loose(evidence: _Evidence, drawn: set[str]) -> list[tuple[int, list[Event]]]:
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


type _Part = tuple[int, Segment, Sequence]


def _told(entry: Entry) -> tuple[str | None, str | None, str | None]:
    told = entry.run.states[-1].state if entry.run and entry.run.states else entry.outcome
    attempt = entry.attempt.outcome if entry.attempt and entry.attempt.outcome != told else None
    dispatch = entry.dispatch.outcome if entry.dispatch and entry.dispatch.outcome != told else None
    return told, attempt, dispatch


def _parts(evidence: _Evidence, timeline: _Timeline, ree: str | None = None) -> list[_Part]:
    placed: list[_Part] = []
    last = -1
    for index, (entry, position) in enumerate(zip(timeline.entries, timeline.positions, strict=True)):
        last = evidence.order[evidence.journal[position].ref] if position is not None else last
        told, attempt, dispatch = _told(entry)
        segment = Segment(
            kind=entry.kind,
            label=entry.name,
            outcome=entry.outcome,
            entry=index,
            ree=ree,
            told=told,
            attempt=attempt,
            dispatch=dispatch,
            first=0,
            last=0,
        )
        if entry.kind == "authoring":
            folded = AuthoringFold(attempts=entry.attempts, failed=entry.failed, operations=entry.operations)
            placed.append((last, segment, fold(entry.start, folded)))
        elif entry.sequence is not None:
            placed.append((last, segment, entry.sequence))
    dispatched = _dispatches_by_run(evidence)
    for position, events in _loose(evidence, timeline.drawn):
        name = _str(events[0].facts.get(terms.ACTION_NAME)) or "action"
        told = events[-1].target_state
        segment = Segment(kind="action", label=name, outcome=told, ree=ree, told=told, first=0, last=0)
        run_ids = {_str(e.facts.get(terms.RUN_ID)) for e in events} - {None}
        exchange = [e for run_id in sorted(r for r in run_ids if r) for e in dispatched.get(run_id, [])]
        sequence = build_sequence(evidence.spans, runs=events, exchange=exchange, origin=evidence.origin)
        placed.append((evidence.order[evidence.journal[position].ref], segment, sequence))
    return placed


def _system(evidence: _Evidence, store: str | None, window: tuple[int, int] | None) -> list[_Part]:
    order = evidence.order
    moves = [
        e
        for e in evidence.everything
        if e.subject == terms.SESSION and e.kind == "transition" and e.target_state != terms.OPENED
        if store is None or e.partition == store
    ]
    returning, renewed = _returning(moves)
    if window is not None:
        low, high = window
        ended = {e.key for e in moves if order[e.ref] < low and e.target_state != "connected"}
        serving = [e for e in moves if order[e.ref] < low and e.target_state == "connected" and e.key not in ended]
        moves = serving[-1:] + [e for e in moves if low <= order[e.ref] <= high]
    parts: list[_Part] = []
    for move in moves:
        segment = Segment(kind="session", label=move.partition or "", first=0, last=0)
        sequence = session_sequence(
            move, evidence.origin, returning=returning.get(move.ref), new_process=move.ref in renewed
        )
        parts.append((order[move.ref], segment, sequence))
    journals = sorted(
        (s for s in evidence.model.evidence.sources if s.kind == "journal" and s.process == "api"),
        key=lambda source: source.rank,
    )
    for index, source in enumerate(journals):
        records = [e for e in evidence.everything if e.source == source.id]
        if not records:
            continue
        marks = [(records[0], False)]
        if not source.closed and index + 1 < len(journals):
            marks.append((records[-1], True))
        for record, crashed in marks:
            position = order[record.ref]
            if (index == 0 and not crashed) or (window is not None and not window[0] <= position <= window[1]):
                continue
            segment = Segment(kind="epoch", label="", first=0, last=0)
            parts.append((position, segment, epoch_sequence(record, source.id, evidence.origin, crashed=crashed)))
    return parts


def _returning(moves: list[Event]) -> tuple[dict[str, str], set[str]]:
    seen: set[str] = set()
    sessions: dict[str, str] = {}
    returning: dict[str, str] = {}
    renewed: set[str] = set()
    for move in moves:
        if move.target_state != "connected":
            continue
        workbench, nonce = str(move.facts.get(terms.WORKBENCH_ID)), str(move.facts.get(terms.NONCE))
        if nonce in sessions:
            returning[move.ref] = sessions[nonce]
        elif workbench in seen:
            renewed.add(move.ref)
        seen.add(workbench)
        sessions[nonce] = move.key
    return returning, renewed


def _joined(parts: list[_Part]) -> Lifecycle:
    parts = sorted(parts, key=lambda part: part[0])
    joined: list[tuple[Segment, Sequence]] = []
    for _, segment, sequence in parts:
        if joined and segment.kind in ("session", "epoch") and joined[-1][0].label == segment.label:
            before = joined[-1][1]
            lanes = tuple({lane.id: lane for lane in (*before.lanes, *sequence.lanes)}.values())
            joined[-1] = (joined[-1][0], Sequence(lanes=lanes, rows=before.rows + sequence.rows, activations=()))
        else:
            joined.append((segment, sequence))
    return build_lifecycle(joined)


def _lifecycle(evidence: _Evidence, timeline: _Timeline) -> Lifecycle:
    parts = _parts(evidence, timeline)
    window = (min(p for p, _, _ in parts), max(p for p, _, _ in parts)) if parts else None
    return _joined(parts + (_system(evidence, evidence.store, window) if evidence.store else []))


def _step(event: Event) -> str:
    return event.key.split("/", 1)[1] if "/" in event.key else event.key


def _str(value: object) -> str | None:
    return None if value is None else str(value)


def build_dossier(
    model: VerifiedModel,
    spans: SpanIndex,
    *,
    dossier: DossierInfo,
    commit_files: Mapping[str, int] | None = None,
) -> BehaviourTrace:
    parts: list[_Part] = []
    evidence: _Evidence | None = None
    for ree in rees(model):
        evidence, timeline = _timeline(model, spans, ree, commit_files)
        parts += _parts(evidence, timeline, ree)
    evidence = evidence or _Evidence(model, spans, "")
    lifecycle = _joined(parts + _system(evidence, None, None))
    result = model.result
    return BehaviourTrace(
        dossier=dossier,
        ree="",
        spec_digest=result.spec_digest,
        verdict=result.verdict,
        sealed=False,
        duration=max((row.t for row in lifecycle.rows), default=0.0),
        sources=tuple(SourceSummary(id=s.id, kind=s.kind, complete=s.complete) for s in result.sources),
        entries=(),
        steps=(),
        lifecycle=lifecycle,
        unreadable_spans=spans.unreadable,
    )
