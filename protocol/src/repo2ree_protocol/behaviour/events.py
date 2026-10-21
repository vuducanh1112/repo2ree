"""Typed records of the behaviour vocabulary, for the owners that journal them.

The contract is ``contracts/behaviour/events.schema.json``, which the specification
publishes and the product never edits. This module is the
product's own reading of it: owners call these functions instead of naming subjects,
owners, states, and facts as strings, so a misspelled word or a mistyped fact is a type
error here. Nothing in it is generated, and nothing checks it against the specification
but the journals it writes (``python -m repo2ree_conformance validate-journal``).

Owners may record more than the vocabulary declares; these functions cover what it does.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, NotRequired, TypedDict, cast

from repo2ree_protocol.allocation import AllocationState
from repo2ree_protocol.behaviour.writer import Fact, journal

RunState = Literal["queued", "provisioning", "running", "canceling", "succeeded", "failed", "canceled"]
DispatchResponse = Literal["result", "unavailable", "error"]


class RunFacts(TypedDict, total=False):
    # Required when the run is accepted (``queued``).
    operation: str
    attempt_id: str | None
    failure_category: str | None


class AllocationFacts(TypedDict, total=False):
    provider_id: str | None
    workbench_id: str | None
    location_id: str | None
    detail: str | None


class ExecActionFacts(TypedDict):
    operation: str
    run_id: str


class ResultFacts(TypedDict):
    status: str
    # The commit that captured the attempt, as the result reported it.
    commit: NotRequired[str | None]


def _facts(facts: Mapping[str, object]) -> dict[str, Fact]:
    """The TypedDicts above hold scalars only; the writer takes them as plain facts."""
    return cast("dict[str, Fact]", dict(facts))


def run(key: str, current: RunState | None, target: RunState, *, partition: str, facts: RunFacts) -> None:
    """A background run's status changed; the API's run store owns it."""
    journal().transition("api", "Run", key, current, target, partition=partition, facts=_facts(facts))


def allocation(
    key: str,
    current: AllocationState | None,
    target: AllocationState,
    *,
    partition: str,
    facts: AllocationFacts,
) -> None:
    """An allocation's state changed; the supervisor's allocation store owns it."""
    source = None if current is None else current.value
    journal().transition(
        "supervisor", "Allocation", key, source, target.value, partition=partition, facts=_facts(facts)
    )


def dispatch_sent(key: str, *, partition: str, facts: ExecActionFacts) -> str | None:
    """The supervisor is about to send a command; returns the record's reference for the attempt to cite."""
    return journal().send("supervisor", "dispatch", "exec_action", key, partition=partition, facts=_facts(facts))


def dispatch_received(key: str, message: DispatchResponse, *, partition: str, facts: ResultFacts | None = None) -> None:
    """The supervisor observed the workbench's one outcome for a command."""
    journal().receive("supervisor", "dispatch", message, key, partition=partition, facts=_facts(facts or {}))


def dispatch_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped waiting for a command's outcome without receiving one."""
    journal().abandon("supervisor", "dispatch", key, partition=partition, reason=reason)
