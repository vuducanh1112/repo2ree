"""What an author asks of one REE through this API, as the behaviour journal records it.

Every request about one REE is one author action: it is ``requested`` when the API
accepts it, a long one is ``running`` while a worker does it, and it settles with the
answer the author is given. Synchronous routes wrap their work in
:func:`author_api_action`; background runs carry their action on the stored run, and
the run store moves it along with the run's status (:func:`follow_run`); an upload
starts its action when its slot is opened and continues it when the upload completes.

This module owns the AuthorApiAction records. It keeps the actions this process has
open, so each record starts where the last one ended, collects the facts a rule needs
from the work done meanwhile (the attempt the workbench reported, the workbench's
allocation), and settles what is still open before the journal closes. It never
touches tracing: spans and metrics stay with the routes and the run registry, so
sampling or switching tracing off cannot change the evidence.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import cast, get_args
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_protocol.behaviour import events
from repo2ree_protocol.behaviour.events import AuthorApiActionFacts, AuthorApiActionName, AuthorApiActionState
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchUnavailableError

TERMINAL: frozenset[AuthorApiActionState] = frozenset({"succeeded", "failed", "canceled"})
ACTION_NAMES: frozenset[str] = frozenset(get_args(AuthorApiActionName))

# How a stored run's status reads as its action's state.
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
    # Facts learned while the action ran, recorded when it settles.
    learned: AuthorApiActionFacts = field(default_factory=lambda: AuthorApiActionFacts())


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
    """Move one action to ``target``; a move to where it already is records nothing.

    ``previous`` says where an action this process does not hold open was, such as a
    run interrupted by an earlier process that this one now settles.
    """
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
    """A request about ``ree_id`` was accepted; returns its action id."""
    action_id = new_action_id()
    record(action_id, "requested", action=action, ree_id=ree_id, facts=_described(facts))
    return action_id


def settle(action_id: str, target: AuthorApiActionState, **facts: str | int | None) -> None:
    """Give an open action its answer; an action this process does not hold is left alone."""
    with _lock:
        held = _open.get(action_id)
    if held is not None:
        record(action_id, target, action=held.action, ree_id=held.ree_id, facts=_described(facts))


def learn(**facts: str | None) -> None:
    """Facts the current action's rules need, recorded when it settles."""
    action_id = _current.get()
    if action_id is None:
        return
    with _lock:
        held = _open.get(action_id)
        if held is not None:
            held.learned.update(_described(facts))


def learn_attempt(result: ActionResult) -> None:
    """The attempt the workbench reported, if it recorded one in the REE's history.

    A command that never reached the workbench, or failed before core opened its
    attempt record, has no attempt to name; naming the id it was sent with would
    point at an attempt that does not exist.
    """
    if result.history is not None and result.context is not None:
        learn(attempt_id=result.context.attempt_id)


@contextmanager
def acting(action_id: str) -> Iterator[None]:
    """Make ``action_id`` the current action, so the work done here can :func:`learn` facts for it."""
    token = _current.set(action_id)
    try:
        yield
    finally:
        _current.reset(token)


@contextmanager
def author_api_action(action: AuthorApiActionName, ree_id: str, **facts: str | None) -> Iterator[str]:
    """One synchronous author action: requested on entry, settled by the answer the route gives."""
    action_id = start(action, ree_id, **facts)
    try:
        with acting(action_id):
            yield action_id
    except BaseException as exc:
        settle(action_id, "failed", http_status=http_status(exc))
        raise
    settle(action_id, "succeeded")


def http_status(exc: BaseException) -> int:
    """The status the author is answered with for ``exc``, as the API's error handlers map it."""
    if isinstance(exc, HTTPException):
        return exc.status_code
    if isinstance(exc, WorkbenchUnavailableError):
        return 503
    return 500


def refuse(action: AuthorApiActionName, ree_id: str, action_id: str | None, exc: BaseException) -> None:
    """A request refused before any work was started for it: its action fails with the refusal."""
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
    """Move a run's action along with the run: the run store calls this after each durable change."""
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


def settle_open(failure_category: str) -> None:
    """Fail every action still open, before the journal closes: an upload never completed, work never answered."""
    with _lock:
        held = list(_open)
    for action_id in held:
        settle(action_id, "failed", failure_category=failure_category)


def _described(facts: Mapping[str, str | int | None]) -> AuthorApiActionFacts:
    """Facts given by name, without the ones that are absent."""
    return cast("AuthorApiActionFacts", {name: value for name, value in facts.items() if value is not None})
