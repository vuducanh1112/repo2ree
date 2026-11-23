from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, NotRequired, TypedDict, cast

from repo2ree_telemetry.behaviour.writer import Fact, journal

StartRunResponse = Literal["accepted", "busy", "unavailable", "error"]
FollowRunResponse = Literal["settled", "unknown", "error"]
CancelRunResponse = Literal["done", "error"]
ExecutionState = Literal["started", "adopted", "exited", "stopped", "lost"]
ExecutionCause = Literal["cancel"]
CommandStatus = Literal["succeeded", "failed", "canceled", "interrupted"]
WorkbenchSessionState = Literal["opened", "connected", "refused", "lost"]
WorkbenchSessionReason = Literal["bad_token", "store_claimed", "closed", "send_failed", "superseded", "shutdown"]
AuthorApiActionState = Literal["requested", "running", "canceling", "resumed", "succeeded", "failed", "canceled"]
AuthorApiActionName = Literal[
    "create_ree",
    "delete_ree",
    "initialize_ree",
    "acquire_source",
    "upload_source",
    "remove_source",
    "patch_ree_definition",
    "write_script",
    "suggest_scripts",
    "lint_scripts",
    "evaluate_reproducibility",
    "observe_hardware",
    "build_experiment_environment",
    "generate_sbom",
    "cross_check_sbom",
    "activate_experiment_environment",
    "check_working_environment",
    "materialize_workspace",
    "run_experiment",
    "seal_ree",
    "sign_ree",
    "sign_review",
    "load_ree_bundle",
    "view_ree",
    "view_ree_state",
    "read_file",
    "list_receipts",
    "view_history",
    "view_reproducibility_report",
    "download_ree",
    "list_actions",
    "view_action",
    "view_action_log",
    "watch_action",
]


class AuthorApiActionFacts(TypedDict, total=False):
    attempt_id: str | None
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
    arch: str
    slots: int
    version: str | None
    reason: WorkbenchSessionReason
    close_code: int | None


class SettledFacts(TypedDict):
    status: CommandStatus
    commit: NotRequired[str | None]
    record: NotRequired[str | None]


def _facts(facts: Mapping[str, object]) -> dict[str, Fact]:
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
    journal().transition(
        "supervisor", "WorkbenchSession", key, current, target, partition=partition, facts=_facts(facts)
    )


def start_run_sent(key: str, *, partition: str, facts: StartRunFacts) -> str | None:
    return journal().send("supervisor", "start_run", "start_run", key, partition=partition, facts=_facts(facts))


def start_run_received(key: str, message: StartRunResponse, *, partition: str) -> None:
    journal().receive("supervisor", "start_run", message, key, partition=partition)


def start_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    journal().abandon("supervisor", "start_run", key, partition=partition, reason=reason)


def follow_run_sent(key: str, *, partition: str, facts: FollowRunFacts) -> None:
    journal().send("supervisor", "follow_run", "follow_run", key, partition=partition, facts=_facts(facts))


def follow_run_received(
    key: str, message: FollowRunResponse, *, partition: str, facts: SettledFacts | None = None
) -> None:
    journal().receive("supervisor", "follow_run", message, key, partition=partition, facts=_facts(facts or {}))


def follow_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    journal().abandon("supervisor", "follow_run", key, partition=partition, reason=reason)


def execution(
    key: str,
    current: ExecutionState | None,
    target: ExecutionState,
    *,
    partition: str,
    facts: ExecutionFacts,
) -> None:
    journal().transition("workbench", "Execution", key, current, target, partition=partition, facts=_facts(facts))


def cancel_run_sent(key: str, *, partition: str, facts: CancelRunFacts) -> str | None:
    return journal().send("supervisor", "cancel_run", "cancel_run", key, partition=partition, facts=_facts(facts))


def cancel_run_received(key: str, message: CancelRunResponse, *, partition: str) -> None:
    journal().receive("supervisor", "cancel_run", message, key, partition=partition)


def cancel_run_abandoned(key: str, *, partition: str, reason: str) -> None:
    journal().abandon("supervisor", "cancel_run", key, partition=partition, reason=reason)
