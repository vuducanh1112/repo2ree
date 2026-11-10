"""Typed records of the behaviour vocabulary, for the owners that journal them.

The contract is ``contracts/behaviour/events.schema.json``, which the specification
publishes and the product never edits. This module is the
product's own reading of it: owners call these functions instead of naming subjects,
owners, states, and facts as strings, so a misspelled word or a mistyped fact is a type
error here. Nothing in it is generated, and nothing checks it against the specification
but the journals it writes (``python -m repo2ree_assurance_checker validate-journal``).

Owners may record more than the vocabulary declares; these functions cover what it does.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, NotRequired, TypedDict, cast

from repo2ree_telemetry.behaviour.writer import Fact, journal

StartRunResponse = Literal["accepted", "busy", "unavailable", "error"]
FollowRunResponse = Literal["settled", "unknown", "error"]
CancelRunResponse = Literal["done", "error"]
ExecutionState = Literal["started", "adopted", "exited", "stopped", "lost"]
ExecutionCause = Literal["cancel"]
# How a command ended, as its executor reported it or as the workbench settled it once the executor was lost.
CommandStatus = Literal["succeeded", "failed", "canceled", "interrupted"]
WorkbenchSessionState = Literal["opened", "connected", "refused", "lost"]
WorkbenchSessionReason = Literal["bad_token", "store_claimed", "closed", "send_failed", "superseded", "shutdown"]
AuthorApiActionState = Literal["requested", "running", "canceling", "resumed", "succeeded", "failed", "canceled"]
# What an author can ask of one REE through the API, by group.
AuthorApiActionName = Literal[
    # workbench
    "create_ree",
    "delete_ree",
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
    "build_experiment_environment",
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


class AuthorApiActionFacts(TypedDict, total=False):
    # The attempt the workbench reported, for an action that ran a command in the REE.
    attempt_id: str | None
    # The store, for create_ree and delete_ree of an REE served by one.
    store_id: str | None
    run_id: str | None
    experiment: str | None
    path: str | None
    about_action_id: str | None
    http_status: int | None
    failure_category: str | None


class StartRunFacts(TypedDict):
    operation: str
    run_id: str
    # The WorkbenchSession the command is sent on.
    session: str


class FollowRunFacts(TypedDict):
    run_id: str
    session: str


class CancelRunFacts(TypedDict):
    run_id: str
    session: str


class ExecutionFacts(TypedDict, total=False):
    operation: str
    run_id: str
    dispatched_by: str | None
    exit_code: int
    cause: ExecutionCause
    canceled_by: str | None
    status: CommandStatus
    commit: str | None
    record: str | None
    reason: Literal["vanished"]


class WorkbenchSessionFacts(TypedDict, total=False):
    workbench_id: str
    nonce: str
    store_id: str
    backend: str
    slots: int
    version: str | None
    reason: WorkbenchSessionReason
    close_code: int | None


class SettledFacts(TypedDict):
    status: CommandStatus
    # The commit that captured the attempt, as the result reported it.
    commit: NotRequired[str | None]
    # For an attempt whose capture failed: the digest of its record, as the result reported it.
    record: NotRequired[str | None]


def _facts(facts: Mapping[str, object]) -> dict[str, Fact]:
    """The TypedDicts above hold scalars only; the writer takes them as plain facts."""
    return cast("dict[str, Fact]", dict(facts))


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


def workbench_session(
    key: str,
    current: WorkbenchSessionState | None,
    target: WorkbenchSessionState,
    *,
    partition: str | None,
    facts: WorkbenchSessionFacts,
) -> None:
    """A workbench's connection to its store moved on; the supervisor owns it."""
    journal().transition(
        "supervisor", "WorkbenchSession", key, current, target, partition=partition, facts=_facts(facts)
    )


def start_run_sent(key: str, *, partition: str, facts: StartRunFacts) -> str | None:
    """The supervisor is about to send a command to start; returns the record's reference for the attempt to cite."""
    return journal().send("supervisor", "start_run", "start_run", key, partition=partition, facts=_facts(facts))


def start_run_received(key: str, message: StartRunResponse, *, partition: str) -> None:
    """The supervisor observed the workbench's one answer to starting a command."""
    journal().receive("supervisor", "start_run", message, key, partition=partition)


def start_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped waiting for the answer to starting a command without receiving one."""
    journal().abandon("supervisor", "start_run", key, partition=partition, reason=reason)


def follow_run_sent(key: str, *, partition: str, facts: FollowRunFacts) -> None:
    """The supervisor is about to ask a workbench to watch a started command."""
    journal().send("supervisor", "follow_run", "follow_run", key, partition=partition, facts=_facts(facts))


def follow_run_received(
    key: str, message: FollowRunResponse, *, partition: str, facts: SettledFacts | None = None
) -> None:
    """The supervisor observed how one watch of a command ended."""
    journal().receive("supervisor", "follow_run", message, key, partition=partition, facts=_facts(facts or {}))


def follow_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped watching a command without an outcome: its session ended, or it stopped."""
    journal().abandon("supervisor", "follow_run", key, partition=partition, reason=reason)


def execution(
    key: str,
    current: ExecutionState | None,
    target: ExecutionState,
    *,
    partition: str,
    facts: ExecutionFacts,
) -> None:
    """An executor the workbench started for a command moved on; the workbench owns it."""
    journal().transition("workbench", "Execution", key, current, target, partition=partition, facts=_facts(facts))


def cancel_run_sent(key: str, *, partition: str, facts: CancelRunFacts) -> str | None:
    """The supervisor is about to ask a workbench to stop a command; returns the record's reference."""
    return journal().send("supervisor", "cancel_run", "cancel_run", key, partition=partition, facts=_facts(facts))


def cancel_run_received(key: str, message: CancelRunResponse, *, partition: str) -> None:
    """The supervisor observed the workbench's one answer to a cancel."""
    journal().receive("supervisor", "cancel_run", message, key, partition=partition)


def cancel_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped waiting for a cancel's answer without receiving one."""
    journal().abandon("supervisor", "cancel_run", key, partition=partition, reason=reason)
