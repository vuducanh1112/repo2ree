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

DispatchResponse = Literal["result", "unavailable", "error"]
CancelRunResponse = Literal["done", "error"]
ExecutionState = Literal["started", "exited", "stopped"]
ExecutionCause = Literal["cancel", "caller_gone"]
WorkbenchSessionState = Literal["opened", "connected", "refused", "lost"]
WorkbenchSessionReason = Literal["bad_token", "store_claimed", "closed", "send_failed", "superseded", "shutdown"]
AuthorApiActionState = Literal["requested", "running", "canceling", "succeeded", "failed", "canceled"]
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


class ExecActionFacts(TypedDict):
    operation: str
    run_id: str
    # The WorkbenchSession the command is sent on.
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


class WorkbenchSessionFacts(TypedDict, total=False):
    workbench_id: str
    nonce: str
    store_id: str
    backend: str
    slots: int
    version: str | None
    reason: WorkbenchSessionReason
    close_code: int | None


class ResultFacts(TypedDict):
    status: str
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


def dispatch_sent(key: str, *, partition: str, facts: ExecActionFacts) -> str | None:
    """The supervisor is about to send a command; returns the record's reference for the attempt to cite."""
    return journal().send("supervisor", "dispatch", "exec_action", key, partition=partition, facts=_facts(facts))


def dispatch_received(key: str, message: DispatchResponse, *, partition: str, facts: ResultFacts | None = None) -> None:
    """The supervisor observed the workbench's one outcome for a command."""
    journal().receive("supervisor", "dispatch", message, key, partition=partition, facts=_facts(facts or {}))


def dispatch_abandoned(key: str, *, partition: str, reason: str) -> None:
    """The supervisor stopped waiting for a command's outcome without receiving one."""
    journal().abandon("supervisor", "dispatch", key, partition=partition, reason=reason)


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
