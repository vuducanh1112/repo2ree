"""The operation trace of one REE: setup, the operations that produce evidence, and the authoring between them.

An operation is an author attempt that belongs to a run (acquire_source, build_runtime, …).
Attempts without a run of their own (definition patches, file writes, lints) are authoring and are
collapsed between operations. Every entry is grouped from the verification of the recording (the
verifier's artifact, read back), and carries the verdict of each rule occurrence its events triggered.

Order: attempts keep capture order, which step evidence depends on. Setup and release, which only
the journal records, are merged in by the journal position of each attempt's dispatch, the request
the attempt's record cites, which is how the checker orders Git evidence too. Wall-clock time places
nothing.

Scope: the REE's own history is the Git source that witnesses its Ree transitions. Review histories
of the same REE are not drawn yet (reviews are not specified); they are only counted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from repo2ree_conformance.evidence import Event
from repo2ree_conformance.verification import Judgement, VerifiedModel
from repo2ree_traceview.model import (
    Attempt,
    Dispatch,
    Entry,
    Machine,
    OperationTrace,
    Recording,
    ReeChange,
    RuleHit,
    SourceSummary,
    SpanSummary,
    Standing,
    StateAt,
    StepChange,
)
from repo2ree_traceview.sequence import build_sequence
from repo2ree_traceview.spans import SpanIndex, timestamp

STEP_ORDER = ("source", "evaluation", "hardware", "runtime", "sbom", "sbom_cross_check", "test_activation")
NOISE = ("websocket", "GET ", "HTTP /provider/connect", "HTTP /workbench/connect")
# The author action that sets up an REE's workbench.
PROVISION = "create_ree"
RELEASED = ("released", "failed", "lost")
TOP_SPANS = 6


@dataclass
class _Authoring:
    start: float | None
    end: float | None = None
    operations: Counter[str] = field(default_factory=Counter)
    failed: int = 0
    changes: list[StepChange] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


class _Builder:
    def __init__(self, model: VerifiedModel, spans: SpanIndex, ree: str) -> None:
        self.model = model
        result, judgements = model.result, model.judgements
        self.spans = spans
        self.events = model.evidence.ordered([e for e in model.evidence.events if e.partition == ree])
        kinds = {source.id: source.kind for source in model.evidence.sources}
        self.journal = [e for e in self.events if kinds.get(e.source) == "journal"]
        self.position = {e.ref: index for index, e in enumerate(self.journal)}
        own = {e.source for e in self.events if e.subject == "Ree"}
        self.git = [e for e in self.events if kinds.get(e.source) == "git" and e.source in own]
        self.reviews = len(
            {
                e.key
                for e in self.events
                if kinds.get(e.source) == "git" and e.source not in own and e.subject == "Attempt"
            }
        )
        stamped = [timestamp(e.at) for e in self.journal if e.at]
        self.origin = min(stamped, default=0.0)
        self.judged: dict[str, list[Judgement]] = defaultdict(list)
        for judgement in judgements:
            self.judged[judgement.event].append(judgement)
        self.flagged = {
            ref: rule.rule
            for rule in result.rules
            if rule.kind in ("machine", "boundary")
            for finding in rule.findings
            if finding.verdict == "violated"
            for ref in finding.evidence
        }

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


def rees(model: VerifiedModel) -> list[str]:
    """The REEs a recording holds, each witnessed by its own Git history."""
    return sorted(model.instances.get("Ree", {}))


@dataclass
class _Setup:
    """Journal-only work: an REE's creation with the allocation moves it made, or an allocation's release."""

    position: int
    run: list[Event]
    allocation: list[Event]


def _runs(b: _Builder) -> dict[str, list[Event]]:
    """The author actions the author watched as runs, by action: the long ones, which carry a run_id.

    A synchronous action (an edit, a lint) answers within its request; its attempt is authoring.
    """
    actions: dict[str, list[Event]] = defaultdict(list)
    for event in b.journal:
        if event.subject == "AuthorApiAction" and event.kind == "transition":
            actions[event.key].append(event)
    return {key: events for key, events in actions.items() if any(e.facts.get("run_id") for e in events)}


def _setups(b: _Builder) -> list[_Setup]:
    runs = _runs(b)
    allocations = [e for e in b.journal if e.subject == "Allocation" and e.kind == "transition"]
    setups: list[_Setup] = []
    claimed: set[str] = set()
    for events in runs.values():
        if events[0].facts.get("action") != PROVISION:
            continue
        first, last = b.position[events[0].ref], b.position[events[-1].ref]
        moved = [e for e in allocations if first <= b.position[e.ref] <= last]
        claimed |= {e.ref for e in moved}
        setups.append(_Setup(first, events, moved))
    rest: dict[str, list[Event]] = defaultdict(list)
    for event in allocations:
        if event.ref not in claimed:
            rest[event.key].append(event)
    setups += [_Setup(b.position[events[0].ref], [], events) for events in rest.values()]
    return sorted(setups, key=lambda setup: setup.position)


def build_trace(
    model: VerifiedModel,
    spans: SpanIndex,
    *,
    ree: str,
    recording: Recording,
    commit_files: Mapping[str, int] | None = None,
) -> OperationTrace:
    """One REE's operation trace, drawn from a verification: its verdicts are the verifier's, never redrawn."""
    b = _Builder(model, spans, ree)
    result = model.result
    files = commit_files or {}
    entries: list[Entry] = []
    standings: list[Standing] = []

    runs = _runs(b)
    run_of_attempt = {
        str(e.facts["attempt_id"]): key for key, events in runs.items() for e in events if e.facts.get("attempt_id")
    }
    pending = _setups(b)
    standing: dict[str, str] = {}
    ree_state: str | None = None
    authoring: _Authoring | None = None

    def close_authoring() -> None:
        nonlocal authoring
        if authoring is None:
            return
        entries.append(
            Entry(
                kind="authoring",
                name="authoring",
                start=authoring.start,
                end=authoring.end,
                changes=tuple(authoring.changes),
                rules=b.rules(authoring.events),
                operations=dict(authoring.operations),
                attempts=sum(authoring.operations.values()),
                failed=authoring.failed,
            )
        )
        changed = tuple(dict.fromkeys(change.step for change in authoring.changes))
        standings.append(
            Standing(
                label="authoring",
                kind="authoring",
                states=dict(standing),
                changed=changed,
                sealed=ree_state == "sealed",
            )
        )
        authoring = None

    def emit_setups(before: int | None) -> None:
        """Journal-only entries the journal places before ``before`` (all of them when None)."""
        while pending and (before is None or pending[0].position < before):
            close_authoring()
            entries.append(_setup_entry(b, pending.pop(0)))

    by_commit: dict[str, list[Event]] = defaultdict(list)
    for event in b.git:
        by_commit[event.locator or event.source].append(event)
    for events in by_commit.values():
        attempt_events = [e for e in events if e.subject == "Attempt"]
        step_events = [e for e in events if e.subject == "Step"]
        ree_events = [e for e in events if e.subject == "Ree"]
        for event in step_events:
            if event.facts.get("cause") == "baseline" or not attempt_events:
                standing[_step(event)] = event.target_state or ""
        reached = ree_events[-1].target_state if ree_events else ree_state
        if not attempt_events:
            ree_state = reached
            continue
        if not standings:
            standings.append(
                Standing(label="created", kind="baseline", states=dict(standing), changed=(), sealed=False)
            )

        key = attempt_events[0].key
        exchange = b.model.exchanges.get("dispatch", {}).get(key)
        exchange_events = [e for e in exchange.events if e.ref in b.position] if exchange else []
        sent = exchange.request if exchange and exchange.request and exchange.request.ref in b.position else None
        answered = exchange.outcome if exchange and exchange.outcome and exchange.outcome.ref in b.position else None
        if sent is not None:
            emit_setups(b.position[sent.ref])
        operation = str(attempt_events[0].facts.get("operation"))
        outcome = next((str(e.facts.get("outcome")) for e in attempt_events if e.target_state == "completed"), None)
        changes = [
            StepChange(
                step=_step(e),
                before=e.source_state,
                after=e.target_state or "",
                cause=_str(e.facts.get("cause")),
                ref=e.ref,
            )
            for e in step_events
            if e.facts.get("cause") != "baseline"
        ]
        checked = attempt_events + step_events + ree_events + exchange_events
        run_key = run_of_attempt.get(key)

        if run_key is None:
            if authoring is None:
                authoring = _Authoring(start=b.rel(sent))
            authoring.operations[operation] += 1
            authoring.failed += outcome != "succeeded"
            authoring.changes += changes
            authoring.events += checked
            authoring.end = b.rel(answered) if answered else authoring.end
            ree_state = reached
            for change in changes:
                standing[change.step] = change.after
            continue

        close_authoring()
        ree_state = reached
        for change in changes:
            standing[change.step] = change.after
        run = runs[run_key]
        commit = next((str(e.facts["commit"]) for e in attempt_events if e.facts.get("commit")), None)
        changed = next((bool(e.facts.get("changed")) for e in attempt_events if e.target_state == "captured"), None)
        ree_change = (
            ReeChange(before=ree_events[0].source_state, after=ree_events[0].target_state or "") if ree_events else None
        )
        size = files.get(commit) if commit else None
        entries.append(
            Entry(
                kind="operation",
                name=operation,
                start=b.rel(run[0]),
                end=b.rel(run[-1]),
                outcome=outcome,
                run=b.machine(run),
                dispatch=Dispatch(
                    sent=sent.ref if sent else None,
                    received=answered.ref if answered else None,
                    outcome=(
                        _str(answered.facts.get("status"))
                        if answered and answered.kind == "receive"
                        else (answered.kind if answered else None)
                    ),
                    start=b.rel(sent),
                    end=b.rel(answered),
                ),
                attempt=Attempt(
                    key=key,
                    states=tuple(e.target_state or "" for e in attempt_events),
                    outcome=outcome,
                    commit=commit,
                    changed=changed,
                    files=size,
                ),
                ree=ree_change,
                changes=tuple(changes),
                rules=b.rules(run + checked),
                spans=b.span_summary(run + exchange_events),
                sequence=build_sequence(
                    spans,
                    runs=run,
                    exchange=exchange_events,
                    attempt=attempt_events,
                    changes=changes,
                    ree=ree_change,
                    commit=commit,
                    files=size,
                ),
            )
        )
        standings.append(
            Standing(
                label=operation,
                kind="operation",
                states=dict(standing),
                changed=tuple(c.step for c in changes),
                sealed=ree_state == "sealed",
            )
        )
    close_authoring()
    emit_setups(None)

    steps = [s for s in STEP_ORDER if s in standing] + sorted(s for s in standing if s not in STEP_ORDER)
    instance = b.model.instances.get("Ree", {}).get(ree)
    return OperationTrace(
        recording=recording,
        ree=ree,
        spec_digest=result.spec_digest,
        verdict=result.verdict,
        sealed=instance is not None and instance.current == "sealed",
        duration=max((entry.end or 0 for entry in entries), default=0.0),
        sources=tuple(SourceSummary(id=s.id, kind=s.kind, complete=s.complete) for s in result.sources),
        entries=tuple(entries),
        steps=tuple(steps),
        standings=tuple(standings),
        reviews=b.reviews,
    )


def _setup_entry(b: _Builder, setup: _Setup) -> Entry:
    if setup.run:
        run, moved = setup.run, setup.allocation
        start, end = b.rel(run[0]), b.rel(run[-1])
        return Entry(
            kind="setup",
            name="provision",
            start=start,
            end=end,
            outcome=run[-1].target_state,
            run=b.machine(run),
            allocation=b.machine(moved) if moved else None,
            rules=b.rules(run + moved),
            spans=b.span_summary(run + moved),
            sequence=build_sequence(b.spans, runs=run, allocations=moved),
        )
    moved = setup.allocation
    released = moved[-1].target_state in RELEASED
    return Entry(
        kind="setup",
        name="release" if released else "allocation",
        start=b.rel(moved[0]),
        end=b.rel(moved[-1]),
        outcome=moved[-1].target_state,
        allocation=b.machine(moved),
        rules=b.rules(moved),
    )


def _step(event: Event) -> str:
    return event.key.split("/", 1)[1] if "/" in event.key else event.key


def _str(value: object) -> str | None:
    return None if value is None else str(value)
