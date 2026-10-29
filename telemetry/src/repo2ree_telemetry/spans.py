"""The `repo2ree.*` span vocabulary, and the trace context carried across processes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from opentelemetry import context, trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import Link, Span, StatusCode

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, Failure, HistoryReference

_ATTR_OPERATION = "repo2ree.operation"
_ATTR_RUN_ID = "repo2ree.run_id"
_ATTR_REE_ID = "repo2ree.ree_id"
_ATTR_STATUS = "repo2ree.status"
# Shared outcome keys: the same fact carries the same key on every span type
# (command, dispatch, exec, runnable), so one query filters them all.
_ATTR_EXIT_CODE = "repo2ree.exit_code"
_ATTR_CANCELED = "repo2ree.canceled"


@dataclass(frozen=True, slots=True)
class CommandSpanAttrs:
    """Identity attributes for a command/dispatch span.

    Owns the ``repo2ree.*`` attribute namespace so call sites pass typed fields
    instead of stringly-keyed ``set_attribute`` calls. Status is recorded
    separately via ``record_command_status`` once the command completes.

    ``run_id`` is optional: background runs and workbench dispatches carry one,
    but synchronous REE commands have no run and omit it.
    """

    operation: str
    run_id: str | None = None
    ree_id: str | None = None
    execution: ExecutionContext | None = None

    def apply(self, span: Span) -> None:
        span.set_attribute(_ATTR_OPERATION, self.operation)
        if self.run_id is not None:
            span.set_attribute(_ATTR_RUN_ID, self.run_id)
        if self.ree_id is not None:
            span.set_attribute(_ATTR_REE_ID, self.ree_id)
        record_execution_context(span, self.execution)


def record_execution_context(span: Span, execution: ExecutionContext | None) -> None:
    if execution is not None:
        span.set_attribute("repo2ree.operation_id", execution.operation_id)
        span.set_attribute("repo2ree.attempt_id", execution.attempt_id)
        if execution.ree_id is not None:
            span.set_attribute(_ATTR_REE_ID, execution.ree_id)


def record_result_boundary(span: Span, boundary: str, result: ActionResult) -> None:
    """Observe a local result boundary; sending does not assert remote receipt."""
    attributes: dict[str, str | int] = {
        "repo2ree.boundary": boundary,
        "repo2ree.status": result.status,
        "repo2ree.exit_code": result.exit_code,
    }
    if result.context is not None:
        attributes.update(
            {
                "repo2ree.operation_id": result.context.operation_id,
                "repo2ree.attempt_id": result.context.attempt_id,
            }
        )
    span.add_event("repo2ree.result", attributes)


def record_result_evidence(span: Span, result: ActionResult) -> None:
    """Write identity/evidence links last so bulky domain facts cannot evict them."""
    record_execution_context(span, result.context)
    record_history_reference(span, result.history)


def record_history_reference(span: Span, history: HistoryReference | None) -> None:
    """Record evidence links explicitly, outside bounded domain-fact flattening."""
    if history is None:
        return
    for key, value in history.model_dump(exclude={"operation_failure"}, exclude_none=True).items():
        span.set_attribute(f"repo2ree.history.{key}", value)


def record_command_status(span: Span, status: str) -> None:
    """Record the terminal status of a command on its span.

    Also flips the span to ERROR when the command didn't succeed, so every
    dispatch layer (core ``command.*``, host ``dispatch_action``, the API
    ``run.*`` root) reports failure consistently — error-rate queries keyed on
    span status would otherwise miss any layer that only set the attribute.
    """
    span.set_attribute(_ATTR_STATUS, status)
    if status != "succeeded":
        span.set_status(StatusCode.ERROR, status)


def record_failure(span: Span, failure: Failure | None) -> None:
    """Record *why* a unit of work failed, alongside the fact that it did.

    ``record_command_status`` says only ``failed``. For the failures that
    produce no outputs — a refused precondition being the ordinary case — that
    left the span with no reason on it at all, and the typed ``Failure`` the
    handler had already minted was dropped at the span boundary. Every layer
    that reports a terminal ActionResult calls this next to the status, so
    ``repo2ree.failure.category`` and ``.origin`` are groupable without parsing
    a message.

    None is accepted and ignored: succeeded and canceled results carry no
    failure, so call sites need no guard of their own.
    """
    if failure is None:
        return
    record_span_facts(span, failure.model_dump(exclude_none=True), namespace="failure")


def record_ree_id(span: Span, ree_id: str) -> None:
    """Tag a span with the REE it operates on."""
    span.set_attribute(_ATTR_REE_ID, ree_id)


# Bounds for record_span_facts. Wide events want every useful scalar on the
# span, but payload-sized values (file contents, full reports) belong in the
# workspace, not the trace: values are truncated and the attribute count per
# call is capped so a pathological dict cannot bloat a span past collector
# limits. Output tails get a larger budget — they are the only evidence of a
# failed workbench command once its container is gone.
_FACT_MAX_ATTRS = 64
_FACT_STR_LIMIT = 256
_TAIL_LIMIT = 2048
# Never recorded: secrets have no place on a span, in any form.
_SECRET_FACT_KEYS = frozenset({"upload_token"})
# Recorded as `<key>.size` only: bulk payloads whose presence/magnitude is the
# queryable fact, not their bytes.
_SIZE_ONLY_FACT_KEYS = frozenset({"content", "patch", "report"})


def record_span_facts(span: Span, facts: Mapping[str, object], *, namespace: str = "") -> None:
    """Flatten *facts* onto *span* as ``repo2ree.*`` attributes (wide-event style).

    The span is the primary record of its unit of work, so callers hand over
    whatever structured facts they have (command args, result outputs, receipt
    dumps) and this owns the shaping: None values are skipped, nested mappings
    flatten to dotted keys, lists record only their length as ``<key>.count``,
    long strings are truncated, secrets are dropped, and bulk payload keys
    record only their size. ``namespace`` scopes the keys (e.g. ``"arg"`` →
    ``repo2ree.arg.origin_url``).
    """
    prefix = f"repo2ree.{namespace}." if namespace else "repo2ree."
    attrs: dict[str, str | bool | int | float] = {}
    _flatten_facts(facts, prefix, attrs)
    for key, value in attrs.items():
        span.set_attribute(key, value)


def _flatten_facts(
    facts: Mapping[str, object],
    prefix: str,
    out: dict[str, str | bool | int | float],
) -> None:
    for key, value in facts.items():
        if len(out) >= _FACT_MAX_ATTRS:
            return
        if value is None or key in _SECRET_FACT_KEYS:
            continue
        full = f"{prefix}{key}"
        if key in _SIZE_ONLY_FACT_KEYS:
            out[f"{full}.size"] = len(value) if isinstance(value, str) else len(json.dumps(value, default=str))
        elif isinstance(value, Mapping):
            _flatten_facts(value, f"{full}.", out)
        elif isinstance(value, list | tuple):
            out[f"{full}.count"] = len(value)
        elif isinstance(value, bool | int | float):
            out[full] = value
        else:
            text = value if isinstance(value, str) else str(value)
            out[full] = text if len(text) <= _FACT_STR_LIMIT else text[: _FACT_STR_LIMIT - 1] + "…"


def record_current_span_facts(facts: Mapping[str, object], *, namespace: str = "") -> None:
    """Record facts on the active span, if one is recording.

    For code that runs inside someone else's span (handlers under the
    ``command.*`` span, steps under a run span) and has facts worth surfacing
    without plumbing the span object through its signature.
    """
    span = trace.get_current_span()
    if span.is_recording():
        record_span_facts(span, facts, namespace=namespace)


def record_exit_code(span: Span, exit_code: int | None) -> None:
    """Record the exit code of the span's unit of work under the shared key.

    Every layer that owns an exit code (command, dispatch, exec, runnable)
    records it through here, so ``repo2ree.exit_code`` is one queryable fact
    across all span types. None (process never returned a code) is skipped.
    """
    if exit_code is not None:
        span.set_attribute(_ATTR_EXIT_CODE, exit_code)


class _SpanFactCarrier:
    """Shared apply plumbing for the typed attribute dataclasses below."""

    _namespace: ClassVar[str] = ""

    def _facts(self) -> Mapping[str, object]:
        raise NotImplementedError

    def apply(self, span: Span) -> None:
        record_span_facts(span, self._facts(), namespace=self._namespace)

    def apply_current(self) -> None:
        """Apply to the active span, if one is recording."""
        record_current_span_facts(self._facts(), namespace=self._namespace)


@dataclass(frozen=True, slots=True)
class ExecSpanAttrs(_SpanFactCarrier):
    """Identity of one subprocess execution (the ``process.exec`` span)."""

    argv: str
    cwd: str | None = None

    def _facts(self) -> Mapping[str, object]:
        return {"exec.argv": self.argv, "exec.cwd": self.cwd}


@dataclass(frozen=True, slots=True)
class ScriptSpanAttrs(_SpanFactCarrier):
    """Identity of a workspace-script run (``script.run``, runnable spans)."""

    path: str

    def _facts(self) -> Mapping[str, object]:
        return {"script.path": self.path}


@dataclass(frozen=True, slots=True)
class WorkbenchSpanAttrs(_SpanFactCarrier):
    """Which workbench and provider a span operates on.

    ``reference_hash`` is a safe correlation key for opaque references: spans
    can be joined without exporting the reference token or its private runtime
    payload. It belongs on spans, never metrics, because it is high-cardinality.
    """

    container: str | None = None
    image: str | None = None
    workbench_id: str | None = None
    runtime: str | None = None
    reference_hash: str | None = None

    def _facts(self) -> Mapping[str, object]:
        return {
            "workbench.container": self.container,
            "workbench.image": self.image,
            "workbench_id": self.workbench_id,
            "workbench.runtime": self.runtime,
            "workbench.reference_hash": self.reference_hash,
        }


@dataclass(frozen=True, slots=True)
class ReviewStepAttrs(_SpanFactCarrier):
    """One review step's identity, and what it settled.

    Recorded on the ``command.review_*`` span rather than on a span of its own:
    a review step *is* the whole command, so a nested span would be 1:1 with it
    and add a level without adding a fact. What was missing was never the span,
    it was these attributes — an attempt could be traced end to end without the
    trace ever saying which attempt it was or what it concluded.

    Applied twice per step: identity as soon as the step is marked running, so
    a step killed mid-run is still attributable, and the terminal facts when it
    settles. ``verdict`` is what the step *found* (a build closure that differs,
    a runtime that would not come up) and is independent of ``status``, which is
    whether the step could run at all — collapsing the two is exactly the
    conflation the review record refuses to make.
    """

    _namespace: ClassVar[str] = "review"

    review_id: str | None = None
    step: str | None = None
    basis: str | None = None
    status: str | None = None
    verdict: str | None = None
    runtime_digest: str | None = None

    def _facts(self) -> Mapping[str, object]:
        return {
            "review_id": self.review_id,
            "step": self.step,
            "basis": self.basis,
            "status": self.status,
            "verdict": self.verdict,
            "runtime_digest": self.runtime_digest,
        }


def record_exec_outcome(
    span: Span,
    *,
    exit_code: int | None,
    canceled: bool,
    stdout: str,
    stderr: str,
) -> None:
    """Record a subprocess's terminal facts on its ``process.exec`` span.

    Output sizes are always recorded; the actual tails only on failure or
    cancellation — success output belongs to the log stream, but a failed
    workbench command must be debuggable from the trace alone, because the
    container (and its logs) may be gone by the time anyone investigates.
    """
    record_exit_code(span, exit_code)
    span.set_attribute(_ATTR_CANCELED, canceled)
    record_span_facts(
        span,
        {
            "exec.stdout_chars": len(stdout),
            "exec.stderr_chars": len(stderr),
        },
    )
    if canceled or exit_code != 0:
        if stdout:
            span.set_attribute("repo2ree.exec.stdout_tail", stdout[-_TAIL_LIMIT:])
        if stderr:
            span.set_attribute("repo2ree.exec.stderr_tail", stderr[-_TAIL_LIMIT:])
        span.set_status(StatusCode.ERROR, "canceled" if canceled else f"exit {exit_code}")


def command_metric_attrs(operation: str, *, status: str | None = None) -> dict[str, str]:
    """Build a metric attribute dict using the canonical ``repo2ree.*`` keys.

    Keeps call sites from hardcoding the attribute strings, so the namespace
    owned here stays the single source of truth for metrics as well as spans.
    """
    attrs = {_ATTR_OPERATION: operation}
    if status is not None:
        attrs[_ATTR_STATUS] = status
    return attrs


def current_span_link() -> Link | None:
    """Capture the active span as a Link, or None when there's no valid span.

    Used to bridge two traces that shouldn't share a root — e.g. the HTTP
    request span and a background run span that outlives the response: the run
    anchors its own trace but links back to the request that started it.
    """
    ctx = trace.get_current_span().get_span_context()
    return Link(ctx) if ctx.is_valid else None


def current_trace_context() -> tuple[str, str] | None:
    """Return ``(trace_id, span_id)`` as zero-padded hex for the active span.

    Stamps structured logs with the active trace so logs and traces are
    joinable in the collector. Returns None when there is no recording span
    (e.g. logs emitted outside any request/run). Keeps the OpenTelemetry import
    behind this module so ``log.py`` need not depend on it directly.
    """
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"


def current_traceparent() -> str | None:
    """Serialise the active span context as a W3C traceparent, or None."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


def remote_context(traceparent: str | None) -> context.Context | None:
    """Deserialize a W3C traceparent into a Context for explicit span parenting.

    Pass the result as ``context=`` to ``start_as_current_span`` so the new
    span parents to the remote caller. Returns None when there is nothing to
    extract — which the tracer treats as "use the current context", so call
    sites need no branching.
    """
    if not traceparent:
        return None
    return extract({"traceparent": traceparent})


def attach_remote_context(traceparent: str | None) -> object | None:
    """Make the remote traceparent the current context; return a detach token.

    Pass the token to ``detach_context`` when the unit of work completes. Returns
    None when there is nothing to attach.
    """
    if not traceparent:
        return None
    ctx = extract({"traceparent": traceparent})
    return context.attach(ctx)


def detach_context(token: object | None) -> None:
    """Detach a context previously attached via ``attach_remote_context``."""
    if token is not None:
        context.detach(token)  # type: ignore[arg-type]
