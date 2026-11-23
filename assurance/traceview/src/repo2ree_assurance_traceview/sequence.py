from __future__ import annotations

from collections.abc import Sequence as Seq

from repo2ree_assurance_checker.evidence import Event
from repo2ree_assurance_traceview import terms
from repo2ree_assurance_traceview.model import (
    Activation,
    Activity,
    AuthoringFold,
    JournalMark,
    Lane,
    Lifecycle,
    Provenance,
    ReeChange,
    Row,
    Segment,
    Sequence,
    SessionMove,
    StepChange,
    Tone,
)
from repo2ree_assurance_traceview.spans import Span, SpanIndex, timestamp

LANES = (
    Lane(id="client", label="Client", process="browser or terminal"),
    Lane(id="api", label="API", process="api process"),
    Lane(id="supervisor", label="Supervisor", process="api process"),
    Lane(id="workbench", label="Workbench", process="workbench"),
    Lane(id="cli", label="CLI · ree", process="ree"),
    Lane(id="core", label="Core · Git", process="ree"),
)
QUIET = 0.1
MINOR = 0.05
STAGING = ("copy_open", "copy_chunk", "copy_close")
UNINTERESTING = ("GET", "OPTIONS", "HTTP")
EPSILON = 0.0005


def invocation(span: Span) -> bool:
    return span.service == "cli" and (span.name == "ree" or span.name.startswith("ree "))


def _start(span: Span) -> float:
    return span.start


def route(name: str) -> str:
    method, _, path = name.partition(" ")
    return f"{method} {path.replace('/api/v1', '').replace('{ree_id}', '{id}')}"


def milliseconds(span: Span) -> str:
    return f"{span.duration * 1000:.0f} ms"


class _Builder:
    def __init__(self, origin: float | None = None) -> None:
        self.origin = origin
        self.rows: list[Row] = []
        self.activations: list[Activation] = []

    def message(
        self,
        t: float | None,
        source: str,
        target: str,
        label: str,
        provenance: Provenance,
        *,
        ref: str | None = None,
        detail: str | None = None,
        session: str | None = None,
    ) -> None:
        if t is not None:
            self.rows.append(
                Row(
                    t=t,
                    lane=source,
                    to=target,
                    label=label,
                    provenance=provenance,
                    ref=ref,
                    detail=detail,
                    session=session,
                )
            )

    def note(
        self,
        t: float | None,
        lane: str,
        label: str,
        provenance: Provenance,
        *,
        ref: str | None = None,
        detail: str | None = None,
        tone: Tone | None = None,
        said: AuthoringFold | SessionMove | JournalMark | None = None,
    ) -> None:
        if t is not None:
            self.rows.append(
                Row(t=t, lane=lane, label=label, provenance=provenance, ref=ref, detail=detail, tone=tone, said=said)
            )

    def activate(self, lane: str, start: float, end: float, label: str, provenance: Provenance = "span") -> None:
        self.activations.append(Activation(lane=lane, start=start, end=end, label=label, provenance=provenance))

    def build(self) -> Sequence:
        if not self.rows:
            return Sequence(lanes=(), rows=(), activations=())
        origin = (
            self.origin
            if self.origin is not None
            else min([r.t for r in self.rows] + [a.start for a in self.activations])
        )
        rows = sorted(
            (row.model_copy(update={"t": round(row.t - origin, 4)}) for row in self.rows), key=lambda row: row.t
        )
        activations = tuple(
            a.model_copy(update={"start": round(a.start - origin, 4), "end": round(a.end - origin, 4)})
            for a in self.activations
        )
        used = {row.lane for row in rows} | {row.to for row in rows if row.to} | {a.lane for a in activations}
        return Sequence(
            lanes=tuple(lane for lane in LANES if lane.id in used), rows=tuple(rows), activations=activations
        )


def build_sequence(
    spans: SpanIndex,
    *,
    runs: Seq[Event] = (),
    exchange: Seq[Event] = (),
    attempt: Seq[Event] = (),
    changes: Seq[StepChange] = (),
    ree: ReeChange | None = None,
    commit: str | None = None,
    files: int | None = None,
    origin: float | None = None,
    ran: Span | None = None,
) -> Sequence:
    builder = _Builder(origin)
    related = spans.in_traces(event.trace_id for event in (*runs, *exchange))
    if ran is not None:
        above = [span for span in spans.ancestors(ran) if invocation(span)]
        related = sorted({span.id: span for span in (*related, *above, *spans.subtree(ran))}.values(), key=_start)
    background = any(event.facts.get(terms.RUN_ID) for event in runs)
    request = _request(builder, spans, related, background=background)
    invoked = any(invocation(span) for span in related)

    for event in runs:
        category = event.facts.get(terms.FAILURE_CATEGORY)
        detail = f"failure {category}" if category else None
        label = f"{_fact(event, terms.ACTION_NAME, 'action')} → {event.target_state}"
        builder.note(_at(event), "api", label, "journal", ref=event.ref, detail=detail)
    for event in exchange:
        if event.kind == "send":
            named = _fact(event, terms.OPERATION, "")
            label = f"{event.message} · {named}" if named else str(event.message)
            session = event.facts.get(terms.SESSION_FACT)
            on = str(session) if session else None
            builder.message(_at(event), "supervisor", "workbench", label, "journal", ref=event.ref, session=on)
        elif event.kind == "receive":
            status = event.facts.get(terms.STATUS)
            label = f"{event.message} · {status}" if status is not None else str(event.message)
            builder.message(_at(event), "workbench", "supervisor", label, "journal", ref=event.ref)
        else:
            label = f"abandoned · {_fact(event, 'reason')}"
            builder.message(_at(event), "workbench", "supervisor", label, "journal", ref=event.ref)

    staged: list[Span] = []
    captured = False
    for span in related:
        if "websocket" in span.name or span.kind == "SERVER" or span is request:
            continue
        operation = span.attribute("repo2ree.operation")
        if span.service == "api" and span.name.startswith("run."):
            builder.activate("api", span.start, span.end, f"{span.name} worker")
            for mark in span.events:
                if mark.attributes.get("repo2ree.boundary") == "api.finalized":
                    status = str(mark.attributes.get("repo2ree.status"))
                    builder.note(mark.at, "api", "result finalized", "span", detail=status)
        elif span.service == "api" and span.name in ("workbench.dispatch_action", "workbench.provision"):
            builder.activate("supervisor", span.start, span.end, span.name.split(".", 1)[1])
        elif span.service == "workbench" and span.name == "workbench.request":
            if operation in STAGING:
                staged.append(span)
                if operation == "copy_close":
                    _staging(builder, staged)
            elif operation in ("start_run", "follow_run"):
                _command(builder, spans, span, operation)
            else:
                builder.message(
                    span.start, "supervisor", "workbench", operation or span.name, "span", detail=milliseconds(span)
                )
        elif invocation(span):
            parent = spans.parent(span)
            caller = "workbench" if parent is not None and parent.service == "workbench" else "client"
            builder.message(span.start, caller, "cli", span.name, "span")
            builder.activate("cli", span.start, span.end, span.name)
            status = span.attribute("repo2ree.status")
            code = span.attribute("repo2ree.exit_code")
            builder.message(
                span.end,
                "cli",
                caller,
                status or "ended",
                "span",
                detail=f"exit {code}" if code is not None else None,
            )
        elif span.service == "cli" and span.name.startswith("executor.") and not invoked:
            builder.message(span.start, "workbench", "cli", "start ree", "span", detail=span.name)
            builder.activate("cli", span.start, span.end, span.name)
            for mark in span.events:
                if mark.attributes.get("repo2ree.boundary") == "executor.completed":
                    label = f"completed · {mark.attributes.get('repo2ree.status')}"
                    detail = f"exit {mark.attributes.get('repo2ree.exit_code')}"
                    builder.message(mark.at, "cli", "workbench", label, "span", detail=detail)
        elif span.service == "cli" and span.name.startswith("command."):
            builder.activate("core", span.start, span.end, f"{span.name} · capture_command")
            _capture(
                builder,
                _Bracket(span.start, span.end, spans.children(span)),
                span,
                attempt,
                changes,
                ree,
                commit,
                files,
            )
            captured = True
        elif span.service == "cli" and span.name == "process.exec":
            detail = f"exit {span.attribute('repo2ree.exit_code')} · {milliseconds(span)}"
            builder.note(span.start, "cli", f"$ {span.attribute('repo2ree.exec.argv')}", "span", detail=detail)
    _staging(builder, staged)
    if attempt and not captured:
        sent = next((e for e in exchange if e.kind == "send"), None)
        outcome = next((e for e in reversed(exchange) if e.kind != "send"), None)
        start, end = _at(sent) if sent else None, _at(outcome) if outcome else None
        if start is not None and end is not None:
            _capture(builder, _Bracket(start, end, []), None, attempt, changes, ree, commit, files)

    return builder.build()


def _at(event: Event) -> float | None:
    return timestamp(event.at) if event.at else None


def _fact(event: Event, name: str, missing: str = "?") -> str:
    value = event.facts.get(name)
    return missing if value is None else str(value)


def _request(builder: _Builder, spans: SpanIndex, related: list[Span], *, background: bool) -> Span | None:
    request = next((s for s in related if s.kind == "SERVER" and not s.name.startswith(UNINTERESTING)), None)
    if request is None:
        return None
    target = request.attribute("http.target") or ""
    parts = target.split("/")
    ree = parts[4] if len(parts) > 4 else None
    for span in spans.spans:
        before = request.start - 3 < span.start < request.start
        if (
            before
            and span.kind == "SERVER"
            and span.trace != request.trace
            and ree
            and not span.name.startswith(UNINTERESTING)
            and ree in (span.attribute("http.target") or "")
        ):
            detail = f"{span.attribute('http.status_code') or ''} · separate trace".strip(" ·")
            builder.message(span.start, "client", "api", route(span.name), "time", detail=detail)
    builder.message(request.start, "client", "api", route(request.name), "span")
    status = next(
        (c.attribute("http.status_code") for c in spans.children(request) if c.attribute("http.status_code")), ""
    )
    after = "the run continues in the background" if background else None
    builder.message(request.end, "api", "client", f"{status} response".strip(), "span", detail=after)
    builder.activate("api", request.start, request.end, "request")
    return request


def _staging(builder: _Builder, staged: list[Span]) -> None:
    if not staged:
        return
    chunks = sum(span.attribute("repo2ree.operation") == "copy_chunk" for span in staged)
    detail = f"copy_open · {chunks} chunk{'s' if chunks != 1 else ''} · copy_close"
    builder.message(staged[0].start, "supervisor", "workbench", "stage upload into workbench", "span", detail=detail)
    staged.clear()


def _command(builder: _Builder, spans: SpanIndex, span: Span, operation: str) -> None:
    builder.activate("workbench", span.start, span.end, operation)
    executor = next((c for c in spans.children(span) if c.service == "cli"), None)
    if executor is not None and executor.start - span.start > QUIET:
        label = f"{(executor.start - span.start) * 1000:.0f} ms without spans"
        builder.note(span.start + EPSILON, "workbench", label, "gap", detail="before ree's span opens", tone="gap")


class _Bracket:
    def __init__(self, start: float, end: float, inner: list[Span]) -> None:
        width = end - start
        self.start, self.end = start, end
        self.first = min((c.start for c in inner), default=start + width * 0.2)
        self.last = max((c.end for c in inner), default=start + width * 0.6)
        self.margin = min(EPSILON, width / 20)


def _capture(
    builder: _Builder,
    bracket: _Bracket,
    command: Span | None,
    attempt: Seq[Event],
    changes: Seq[StepChange],
    ree: ReeChange | None,
    commit: str | None,
    files: int | None,
) -> None:
    m = bracket.margin
    placed = {
        terms.PENDING: bracket.start + m / 2,
        terms.EXECUTING: bracket.first - m,
        terms.COMPLETED: bracket.last + m,
        terms.CAPTURED: bracket.end - 2 * m,
        terms.CAPTURE_FAILED: bracket.end - 2 * m,
    }
    before = command.attribute("repo2ree.history.before_snapshot_id") if command is not None else None
    for event in attempt:
        detail = None
        if event.target_state == terms.EXECUTING and before:
            detail = f"before-snapshot {before[:8]}"
        elif event.target_state == terms.COMPLETED:
            detail = f"outcome {_fact(event, terms.OUTCOME)}"
        t = placed.get(event.target_state or "", bracket.end - 2 * m)
        builder.note(t, "core", f"Attempt → {event.target_state}", "inferred", ref=event.ref, detail=detail)
    if commit is None:
        return
    ref = f"git@{commit[:12]}"
    detail = f"tree changed · {files} files" if files else "tree unchanged"
    builder.note(bracket.end - m * 1.6, "core", f"commit {commit[:8]}", "git", ref=ref, detail=detail, tone="commit")
    if changes:
        label = ", ".join(f"{c.step} → {c.after}" for c in changes)
        builder.note(bracket.end - m * 1.4, "core", label, "git", ref=ref, detail="step evidence", tone="effect")
    if ree is not None:
        tone: Tone | None = "effect" if ree.after != ree.before else None
        builder.note(bracket.end - m * 1.2, "core", f"REE {ree.before} → {ree.after}", "git", ref=ref, tone=tone)


def build_lifecycle(parts: Seq[tuple[Segment, Sequence]]) -> Lifecycle:
    rows: list[Row] = []
    activities: list[Activity] = []
    segments: list[Segment] = []
    used: set[str] = set()
    for segment, sequence in parts:
        own = [row for row in sequence.rows if row.provenance != "time"]
        if not own:
            continue
        offset = len(rows)
        rows += own
        used |= {lane.id for lane in sequence.lanes}
        segments.append(segment.model_copy(update={"first": offset, "last": len(rows) - 1}))
        for activation in sequence.activations:
            if activation.provenance == "time":
                continue
            inside = [i for i, row in enumerate(own) if activation.start - EPSILON <= row.t <= activation.end + EPSILON]
            if inside:
                activities.append(
                    Activity(
                        lane=activation.lane,
                        first=offset + inside[0],
                        last=offset + inside[-1],
                        label=activation.label,
                        duration=round(activation.end - activation.start, 4),
                        provenance=activation.provenance,
                    )
                )
    return Lifecycle(
        lanes=tuple(lane for lane in LANES if lane.id in used),
        rows=tuple(rows),
        activations=tuple(activities),
        segments=tuple(segments),
    )


def fold(t: float | None, fold: AuthoringFold) -> Sequence:
    builder = _Builder(0.0)
    builder.note(t, "api", "", "journal", tone="fold", said=fold)
    return builder.build()


def session_sequence(
    event: Event, origin: float, *, returning: str | None = None, new_process: bool = False
) -> Sequence:
    facts = event.facts
    state = event.target_state or ""
    code = facts.get(terms.CLOSE_CODE)
    move = SessionMove(
        session=event.key,
        state=state,
        workbench=_text(facts.get(terms.WORKBENCH_ID)),
        nonce=_text(facts.get(terms.NONCE)),
        reason=_text(facts.get(terms.REASON)),
        close_code=code if isinstance(code, int) else None,
        returning=returning,
        new_process=new_process,
    )
    builder = _Builder(origin)
    tone: Tone | None = "gap" if state == terms.LOST else None
    builder.note(_at(event), "supervisor", "", "journal", ref=event.ref, tone=tone, said=move)
    return builder.build()


def epoch_sequence(event: Event, journal: str, origin: float, *, crashed: bool) -> Sequence:
    builder = _Builder(origin)
    mark = JournalMark(journal=journal, mark="crashed" if crashed else "opened")
    builder.note(_at(event), "api", "", "journal", ref=event.ref, tone="gap" if crashed else None, said=mark)
    return builder.build()


def _text(value: object) -> str | None:
    return None if value is None else str(value)
