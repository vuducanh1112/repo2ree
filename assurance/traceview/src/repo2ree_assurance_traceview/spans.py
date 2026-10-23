"""OpenTelemetry spans as recorded by the e2e stack's console exporter, and an index to find them.

Spans are context. Nothing here decides a verdict or an order: they explain where time went and
show hops no owner journals yet. So a record that cannot be read (a process killed mid-write
leaves half of one) is counted and passed over; it never costs the page.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import datetime

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError


class SpanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpanEvent(SpanModel):
    name: str
    at: float
    attributes: dict[str, JsonValue] = {}


class Span(SpanModel):
    id: str
    trace: str
    parent: str | None
    name: str
    service: str
    kind: str
    start: float
    end: float
    attributes: dict[str, JsonValue] = {}
    events: tuple[SpanEvent, ...] = ()
    status: str = "UNSET"

    @property
    def duration(self) -> float:
        return self.end - self.start

    def attribute(self, name: str) -> str | None:
        value = self.attributes.get(name)
        return None if value is None else str(value)


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


# The console exporter's record, as far as the views read it.


class _Exported(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class _Context(_Exported):
    span_id: str
    trace_id: str


class _Resource(_Exported):
    attributes: dict[str, JsonValue] | None = None


class _Status(_Exported):
    status_code: str = "UNSET"


class _Event(_Exported):
    name: str
    timestamp: datetime
    attributes: dict[str, JsonValue] | None = None


class _Record(_Exported):
    name: str = ""
    context: _Context
    parent_id: str | None = None
    kind: str = ""
    start_time: datetime
    end_time: datetime
    attributes: dict[str, JsonValue] | None = None
    events: list[_Event] | None = None
    resource: _Resource | None = None
    status: _Status | None = None

    def span(self) -> Span:
        service = (self.resource.attributes or {}).get("service.name") if self.resource else None
        return Span(
            id=_hex(self.context.span_id),
            trace=_hex(self.context.trace_id),
            parent=_hex(self.parent_id) or None,
            name=self.name,
            service=str(service or "?").removeprefix("repo2ree-"),
            kind=self.kind.removeprefix("SpanKind."),
            start=self.start_time.timestamp(),
            end=self.end_time.timestamp(),
            attributes=self.attributes or {},
            events=tuple(
                SpanEvent(name=event.name, at=event.timestamp.timestamp(), attributes=event.attributes or {})
                for event in self.events or ()
            ),
            status=self.status.status_code if self.status else "UNSET",
        )


def _hex(value: str | None) -> str:
    return (value or "").removeprefix("0x")


def _documents(text: str) -> Iterator[object | None]:
    """The exporter's records, pretty-printed back to back; None for one that is not JSON.

    Each record starts on a line of its own with ``{``, so after a broken one reading resumes there.
    """
    decoder, index = json.JSONDecoder(), 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        try:
            document, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            yield None
            resume = text.find("\n{", index + 1)
            if resume < 0:
                return
            index = resume + 1
            continue
        yield document


def parse_spans(text: str) -> tuple[list[Span], int]:
    """The spans in one exported file, and how many of its records could not be read."""
    spans: list[Span] = []
    unreadable = 0
    for document in _documents(text):
        try:
            spans.append(_Record.model_validate(document).span())
        except ValidationError:
            unreadable += 1
    return spans, unreadable


class SpanIndex:
    def __init__(self, spans: Iterable[Span] = (), unreadable: int = 0) -> None:
        self.spans = sorted(spans, key=lambda span: span.start)
        self.unreadable = unreadable  # Records passed over; the page says how many.
        self._by_trace: dict[str, list[Span]] = defaultdict(list)
        self._children: dict[str, list[Span]] = defaultdict(list)
        for span in self.spans:
            self._by_trace[span.trace].append(span)
            if span.parent:
                self._children[span.parent].append(span)

    def in_traces(self, traces: Iterable[str | None]) -> list[Span]:
        found = [span for trace in set(traces) if trace for span in self._by_trace.get(trace, [])]
        return sorted(found, key=lambda span: span.start)

    def children(self, span: Span) -> list[Span]:
        return self._children.get(span.id, [])
