"""OpenTelemetry spans as recorded by the e2e stack's console exporter, and an index to find them.

Spans are context. Nothing here decides a verdict or an order: they explain where time went and
show hops no owner journals yet.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue


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


def _documents(text: str) -> Iterator[dict[str, Any]]:
    """The console exporter writes pretty-printed JSON objects back to back, not one per line."""
    decoder, index = json.JSONDecoder(), 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        document, index = decoder.raw_decode(text, index)
        if isinstance(document, dict):
            yield document


def _hex(value: object) -> str:
    return str(value or "").removeprefix("0x")


def parse_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for raw in _documents(text):
        context = raw.get("context") or {}
        resource = (raw.get("resource") or {}).get("attributes") or {}
        spans.append(
            Span(
                id=_hex(context.get("span_id")),
                trace=_hex(context.get("trace_id")),
                parent=_hex(raw.get("parent_id")) or None,
                name=str(raw.get("name", "")),
                service=str(resource.get("service.name", "?")).removeprefix("repo2ree-"),
                kind=str(raw.get("kind", "")).removeprefix("SpanKind."),
                start=timestamp(raw["start_time"]),
                end=timestamp(raw["end_time"]),
                attributes=raw.get("attributes") or {},
                events=tuple(
                    SpanEvent(
                        name=event["name"], at=timestamp(event["timestamp"]), attributes=event.get("attributes") or {}
                    )
                    for event in raw.get("events") or []
                ),
                status=str((raw.get("status") or {}).get("status_code", "UNSET")),
            )
        )
    return spans


class SpanIndex:
    def __init__(self, spans: Iterable[Span] = ()) -> None:
        self.spans = sorted(spans, key=lambda span: span.start)
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
