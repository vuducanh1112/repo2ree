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
_ATTR_EXIT_CODE = "repo2ree.exit_code"
_ATTR_CANCELED = "repo2ree.canceled"


@dataclass(frozen=True, slots=True)
class CommandSpanAttrs:
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
    record_execution_context(span, result.context)
    record_history_reference(span, result.history)


def record_history_reference(span: Span, history: HistoryReference | None) -> None:
    if history is None:
        return
    for key, value in history.model_dump(exclude={"operation_failure"}, exclude_none=True).items():
        span.set_attribute(f"repo2ree.history.{key}", value)


def record_command_status(span: Span, status: str) -> None:
    span.set_attribute(_ATTR_STATUS, status)
    if status != "succeeded":
        span.set_status(StatusCode.ERROR, status)


def record_failure(span: Span, failure: Failure | None) -> None:
    if failure is None:
        return
    record_span_facts(span, failure.model_dump(exclude_none=True), namespace="failure")


def record_ree_id(span: Span, ree_id: str) -> None:
    span.set_attribute(_ATTR_REE_ID, ree_id)


_FACT_MAX_ATTRS = 64
_FACT_STR_LIMIT = 256
_TAIL_LIMIT = 2048
_SECRET_FACT_KEYS = frozenset({"upload_token"})
_SIZE_ONLY_FACT_KEYS = frozenset({"content", "patch", "report"})


def record_span_facts(span: Span, facts: Mapping[str, object], *, namespace: str = "") -> None:
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
    span = trace.get_current_span()
    if span.is_recording():
        record_span_facts(span, facts, namespace=namespace)


def record_exit_code(span: Span, exit_code: int | None) -> None:
    if exit_code is not None:
        span.set_attribute(_ATTR_EXIT_CODE, exit_code)


class _SpanFactCarrier:
    _namespace: ClassVar[str] = ""

    def _facts(self) -> Mapping[str, object]:
        raise NotImplementedError

    def apply(self, span: Span) -> None:
        record_span_facts(span, self._facts(), namespace=self._namespace)

    def apply_current(self) -> None:
        record_current_span_facts(self._facts(), namespace=self._namespace)


@dataclass(frozen=True, slots=True)
class ExecSpanAttrs(_SpanFactCarrier):
    argv: str
    cwd: str | None = None

    def _facts(self) -> Mapping[str, object]:
        return {"exec.argv": self.argv, "exec.cwd": self.cwd}


@dataclass(frozen=True, slots=True)
class ScriptSpanAttrs(_SpanFactCarrier):
    path: str

    def _facts(self) -> Mapping[str, object]:
        return {"script.path": self.path}


@dataclass(frozen=True, slots=True)
class WorkbenchSpanAttrs(_SpanFactCarrier):
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
    _namespace: ClassVar[str] = "review"

    review_id: str | None = None
    step: str | None = None
    basis: str | None = None
    status: str | None = None
    verdict: str | None = None
    experiment_environment_digest: str | None = None

    def _facts(self) -> Mapping[str, object]:
        return {
            "review_id": self.review_id,
            "step": self.step,
            "basis": self.basis,
            "status": self.status,
            "verdict": self.verdict,
            "experiment_environment_digest": self.experiment_environment_digest,
        }


def record_exec_outcome(
    span: Span,
    *,
    exit_code: int | None,
    canceled: bool,
    stdout: str,
    stderr: str,
) -> None:
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
    attrs = {_ATTR_OPERATION: operation}
    if status is not None:
        attrs[_ATTR_STATUS] = status
    return attrs


def current_span_link() -> Link | None:
    ctx = trace.get_current_span().get_span_context()
    return Link(ctx) if ctx.is_valid else None


def current_trace_context() -> tuple[str, str] | None:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"


def current_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


def remote_context(traceparent: str | None) -> context.Context | None:
    if not traceparent:
        return None
    return extract({"traceparent": traceparent})
