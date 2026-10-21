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

DispatchResponse = Literal["result", "unavailable", "error"]
AuthorApiActionState = Literal["requested", "running", "canceling", "succeeded", "failed", "canceled"]
# What an author can ask of one REE through the API, by group.
AuthorApiActionName = Literal[
    # workbench
    "create_ree",
    "release_workbench",
    # source
    "acquire_source",
    "upload_source",
    "remove_source",
    # editing
    "edit_definition",
    "write_file",
    "delete_file",
    # assistance
    "suggest_scripts",
    "lint_scripts",
    # evidence
    "evaluate_reproducibility",
    "observe_hardware",
    "build_runtime",
    "generate_sbom",
    "cross_check_sbom",
    "test_activation",
    "run_experiment",
    # lifecycle
    "seal_ree",
    "load_ree_bundle",
    # reading
    "view_ree",
    "view_ree_state",
    "read_file",
    "list_receipts",
    "view_history",
    "view_evaluation_report",
    "download_ree",
    "list_actions",
    "view_action",
    "view_action_log",
    "watch_action",
]


class AllocationFacts(TypedDict, total=False):
    provider_id: str | None
    workbench_id: str | None
    location_id: str | None
    detail: str | None


class AuthorApiActionFacts(TypedDict, total=False):
    # The attempt the workbench reported, for an action that ran a command in the REE.
    attempt_id: str | None
    # The workbench's allocation, for create_ree and release_workbench.
    allocation_id: str | None
    run_id: str | None
    experiment: str | None
    path: str | None
    about_action_id: str | None
    http_status: int | None
    failure_category: str | None


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


def author_api_action(
    key: str,
    current: AuthorApiActionState | None,
    target: AuthorApiActionState,
    *,
    action: AuthorApiActionName,
    partition: str,
    facts: AuthorApiActionFacts,
) -> None:
    """What an author asked of one REE through the API moved on; the API owns it."""
    recorded: dict[str, Fact] = {"action": action, **_facts(facts)}
    journal().transition("api", "AuthorApiAction", key, current, target, partition=partition, facts=recorded)


def dispatch_sent(key: str, *, partition: str, facts: ExecActionFacts) -> str | None:
    """The supervisor is about to send a command; returns the record's reference for the attempt to cite."""
    return journal().send("supervisor", "dispatch", "exec_action", key, partition=partition, facts=_facts(facts))


def dispatch_received(key: str, message: DispatchResponse, *, partition: str, facts: ResultFacts | None = None) -> None:
    """The supervisor observed the workbench's one outcome for a command."""
    journal().receive("supervisor", "dispatch", message, key, partition=partition, facts=_facts(facts or {}))


def dispatch_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped waiting for a command's outcome without receiving one."""
    journal().abandon("supervisor", "dispatch", key, partition=partition, reason=reason)
