from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import cast, get_args
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import ReeBusyError, WorkbenchUnavailableError
from repo2ree_telemetry.behaviour import events
from repo2ree_telemetry.behaviour.events import AuthorApiActionFacts, AuthorApiActionName, AuthorApiActionState

TERMINAL: frozenset[AuthorApiActionState] = frozenset({"succeeded", "failed", "canceled"})
ACTION_NAMES: frozenset[str] = frozenset(get_args(AuthorApiActionName))

RUN_STATES: dict[str, AuthorApiActionState] = {
    "queued": "requested",
    "provisioning": "running",
    "running": "running",
    "canceling": "canceling",
    "succeeded": "succeeded",
    "failed": "failed",
    "canceled": "canceled",
}


@dataclass
class _Open:
    action: AuthorApiActionName
    ree_id: str
    state: AuthorApiActionState
    learned: AuthorApiActionFacts = field(default_factory=lambda: AuthorApiActionFacts())
    detached: bool = False


_open: dict[str, _Open] = {}
_lock = threading.Lock()
_current: ContextVar[str | None] = ContextVar("author_api_action", default=None)


def new_action_id() -> str:
    return f"act-{uuid4().hex}"


def is_open(action_id: str) -> bool:
    with _lock:
        return action_id in _open


def record(
    action_id: str,
    target: AuthorApiActionState,
    *,
    action: AuthorApiActionName,
    ree_id: str,
    previous: AuthorApiActionState | None = None,
    facts: AuthorApiActionFacts | None = None,
) -> None:
    with _lock:
        held = _open.get(action_id)
        source = held.state if held is not None else previous
        if source == target:
            return
        recorded: AuthorApiActionFacts = {**(facts or {})}
        if held is not None and target in TERMINAL:
            recorded = {**held.learned, **recorded}
        events.author_api_action(action_id, source, target, action=action, partition=ree_id, facts=recorded)
        if target in TERMINAL:
            _open.pop(action_id, None)
        elif held is not None:
            held.state = target
        else:
            _open[action_id] = _Open(action, ree_id, target)


def start(action: AuthorApiActionName, ree_id: str, **facts: str | None) -> str:
    action_id = new_action_id()
    record(action_id, "requested", action=action, ree_id=ree_id, facts=_described(facts))
    return action_id


def settle(action_id: str, target: AuthorApiActionState, **facts: str | int | None) -> None:
    with _lock:
        held = _open.get(action_id)
    if held is not None:
        record(action_id, target, action=held.action, ree_id=held.ree_id, facts=_described(facts))


def learn(**facts: str | None) -> None:
    action_id = _current.get()
    if action_id is None:
        return
    with _lock:
        held = _open.get(action_id)
        if held is not None:
            held.learned.update(_described(facts))


def learn_attempt(result: ActionResult) -> None:
    if result.history is not None and result.context is not None:
        learn(attempt_id=result.context.attempt_id)


@contextmanager
def acting(action_id: str) -> Iterator[None]:
    token = _current.set(action_id)
    try:
        yield
    finally:
        _current.reset(token)


@contextmanager
def author_api_action(action: AuthorApiActionName, ree_id: str, **facts: str | None) -> Iterator[str]:
    action_id = start(action, ree_id, **facts)
    try:
        with acting(action_id):
            yield action_id
    except BaseException as exc:
        settle(action_id, "failed", http_status=http_status(exc))
        raise
    settle(action_id, "succeeded")


def http_status(exc: BaseException) -> int:
    if isinstance(exc, HTTPException):
        return exc.status_code
    if isinstance(exc, WorkbenchUnavailableError):
        return 503
    if isinstance(exc, ReeBusyError):
        return 409
    return 500


def refuse(action: AuthorApiActionName, ree_id: str, action_id: str | None, exc: BaseException) -> None:
    if action_id is None or not is_open(action_id):
        action_id = start(action, ree_id)
    settle(action_id, "failed", http_status=http_status(exc))


def follow_run(
    action_id: str,
    action: str,
    ree_id: str,
    previous_status: str | None,
    status: str,
    *,
    run_id: str,
    attempt_id: str | None,
    failure_category: str | None,
) -> None:
    if action not in ACTION_NAMES:
        return
    target = RUN_STATES[status]
    previous = None if previous_status is None else RUN_STATES[previous_status]
    facts = _described(
        {"run_id": run_id}
        | ({"attempt_id": attempt_id, "failure_category": failure_category} if target in TERMINAL else {})
    )
    named = cast("AuthorApiActionName", action)
    record(action_id, target, action=named, ree_id=ree_id, previous=previous, facts=facts)


def resume(action_id: str, action: str, ree_id: str, status: str) -> None:
    if action in ACTION_NAMES:
        named = cast("AuthorApiActionName", action)
        record(action_id, "resumed", action=named, ree_id=ree_id, previous=RUN_STATES[status])


def detach(action_id: str) -> None:
    with _lock:
        held = _open.get(action_id)
        if held is not None:
            held.detached = True


def settle_open(failure_category: str, *, final: bool = False) -> None:
    with _lock:
        held = [action_id for action_id, item in _open.items() if final or not item.detached]
    for action_id in held:
        settle(action_id, "failed", failure_category=failure_category)


def _described(facts: Mapping[str, str | int | None]) -> AuthorApiActionFacts:
    return cast("AuthorApiActionFacts", {name: value for name, value in facts.items() if value is not None})
