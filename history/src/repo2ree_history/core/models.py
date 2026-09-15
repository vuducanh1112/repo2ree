"""Canonical observed execution model; independent of protocol and OpenTelemetry."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

type Identifier = Annotated[str, Field(min_length=1)]
type Component = Literal["api", "supervisor", "provider", "workbench", "executor", "core", "client", "recorder"]
type Outcome = Literal["succeeded", "failed", "canceled", "unknown"]


class HistoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BuildIdentity(HistoryModel):
    version: str = ""
    revision: str = ""


class Producer(HistoryModel):
    """A sequence belongs to this component/process epoch, never to a whole trace."""

    component: Component
    instance_id: Identifier | None = None
    epoch: Identifier | None = None
    build: BuildIdentity | None = None


class TraceContext(HistoryModel):
    trace_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    span_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]

    @field_validator("trace_id", "span_id")
    @classmethod
    def nonzero_identifier(cls, value: str) -> str:
        if int(value, 16) == 0:
            raise ValueError("trace context identifiers must be nonzero")
        return value


class Resources(HistoryModel):
    """Identities known at this observation; absence means unknown, not absent."""

    ree_id: Identifier | None = None
    scope: Identifier | None = None  # Existing author/review scope string, preserved verbatim.
    review_id: Identifier | None = None
    workbench_id: Identifier | None = None
    workbench_instance_id: Identifier | None = None  # Workbench hello nonce; stable across reconnects.
    provider_id: Identifier | None = None
    allocation_id: Identifier | None = None
    location_id: Identifier | None = None
    session_id: Identifier | None = None  # One connection; a reconnect gets a new session.
    request_id: Identifier | None = None  # Unique within its session.
    transfer_id: Identifier | None = None
    runtime: str | None = None
    reference_hash: str | None = None  # Never the WorkbenchRef token.
    container: str | None = None
    image: str | None = None
    resolved_image: str | None = None
    author_seal_digest: str | None = None


class OperationIdentity(HistoryModel):
    operation_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]
    attempt_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]
    operation: Identifier
    run_id: Identifier | None = None


class Projection(HistoryModel):
    """Schema-identified selected facts; no implicit request/result dumping."""

    schema_id: Identifier
    document: dict[str, JsonValue]


class FailureObservation(HistoryModel):
    category: Literal["validation", "precondition", "conflict", "execution", "timeout", "unavailable", "internal"]
    origin: Component
    message: str
    retryable: bool = False
    details: Projection | None = None


class ExecutionStarted(HistoryModel):
    kind: Literal["execution.started"] = "execution.started"
    trigger: Literal["connection_attempt", "attached_to_existing_workbench"]


class ExecutionEnded(HistoryModel):
    kind: Literal["execution.ended"] = "execution.ended"
    reason: Literal["workbench_shutdown", "connection_failed", "observation_stopped"]
    # No assertion that shutdown sealed or completed the REE.


class ConnectionObserved(HistoryModel):
    kind: Literal["connection.observed"] = "connection.observed"
    session_id: Identifier
    peer: Component
    state: Literal["attempted", "connected", "disconnected", "rejected"]


class AuthenticationObserved(HistoryModel):
    """Decision observed at the receiving boundary; no credentials or tokens."""

    kind: Literal["authentication.observed"] = "authentication.observed"
    session_id: Identifier
    request_id: Identifier | None = None  # None binds authentication to the session.
    outcome: Literal["authenticated", "rejected", "bypassed", "unknown"]
    principal_id: Identifier | None = None
    mechanism: Identifier


class InteractionObserved(HistoryModel):
    kind: Literal["interaction.observed"] = "interaction.observed"
    session_id: Identifier
    request_id: Identifier
    action: Identifier
    decision: Literal["accepted", "rejected"]
    authentication_event_id: Identifier | None = None


class OperationStarted(HistoryModel):
    kind: Literal["operation.started"] = "operation.started"
    inputs: Projection | None = None


class OperationCompleted(HistoryModel):
    """Local outcome; API acknowledgement is not executor completion."""

    kind: Literal["operation.completed"] = "operation.completed"
    outcome: Outcome
    exit_code: int | None = None
    failure: FailureObservation | None = None
    outputs: Projection | None = None

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.outcome == "succeeded" and self.exit_code not in (None, 0):
            raise ValueError("success cannot have a nonzero exit code")
        if self.failure is not None and self.outcome != "failed":
            raise ValueError("failure details require a failed outcome")
        return self


class ProcessObserved(HistoryModel):
    kind: Literal["process.observed"] = "process.observed"
    argv: str  # Existing ExecSpanAttrs representation; producers must redact credentials.
    cwd: str | None = None
    script_path: str | None = None
    exit_code: int | None = None
    canceled: bool | None = None


class ReviewObserved(HistoryModel):
    kind: Literal["review.observed"] = "review.observed"
    step: Identifier
    basis: str | None = None
    status: str | None = None
    verdict: str | None = None
    runtime_digest: str | None = None


class Boundary(HistoryModel):
    """Readiness facts for the existing ree_layout contract, not inferred from success."""

    event: Literal["operation_finished", "initialization_finished"]
    status: Literal["succeeded", "failed", "canceled"]
    scope: Literal["author", "review"]
    mutates_ree: bool
    root_expected: bool
    writers_stopped: bool
    capture_prepared: bool
    locks_held: bool
    history_published: bool
    capture_format: Literal["repository_v2", "legacy", "none"]


class FileEntry(HistoryModel):
    path: Identifier
    kind: Literal["file", "directory", "symlink", "other", "missing", "unreadable"]

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        if value.startswith("/") or "\\" in value or ".." in value.split("/"):
            raise ValueError("file entry must be relative to its observed root")
        return value


class LayoutObserved(HistoryModel):
    kind: Literal["layout.observed"] = "layout.observed"
    boundary: Boundary
    entries: tuple[FileEntry, ...]
    # Only listed paths were inspected. No entry never means the path was missing.
    coverage: Literal["managed_paths", "full_tree"]

    @model_validator(mode="after")
    def unique_entries(self) -> Self:
        if len({entry.path for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate layout path")
        return self


class StateObserved(HistoryModel):
    kind: Literal["state.observed"] = "state.observed"
    projection: Projection
    consistency: Literal["stable_boundary", "unsynchronized"]
    boundary_event_id: Identifier | None = None


class GitCaptureObserved(HistoryModel):
    """HistoryReference plus repository identity; commit IDs are scoped to a repository."""

    kind: Literal["git_capture.observed"] = "git_capture.observed"
    repository_id: Identifier
    selection_version: Annotated[int, Field(ge=1)]
    capture_status: Literal["pending", "captured", "failed"]
    operation_status: Outcome | Literal["not_started"]
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    changed: bool | None = None
    capture_error: str | None = None
    operation_failure: FailureObservation | None = None


class Artifact(HistoryModel):
    artifact_id: Identifier
    kind: Literal["git_repository", "telemetry", "state", "log", "screenshot", "video", "archive", "report"]
    uri: Identifier  # Relative to recording root, or an explicit external URI; never auto-fetched.
    media_type: str | None = None
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    repository_id: Identifier | None = None
    resources: Resources = Field(default_factory=Resources)


class SpanLocator(HistoryModel):
    kind: Literal["span"] = "span"
    trace_id: str
    span_id: str
    line: Annotated[int, Field(ge=1)]


class RecordLocator(HistoryModel):
    kind: Literal["record"] = "record"
    line: Annotated[int, Field(ge=1)] | None = None
    pointer: str = ""
    path: str | None = None  # Relative file within a directory artifact.


class CommitLocator(HistoryModel):
    kind: Literal["commit"] = "commit"
    commit_id: Annotated[str, Field(pattern=r"^[0-9a-f]{40,64}$")]
    path: str | None = None  # None identifies commit metadata.


class SourceReference(HistoryModel):
    artifact_id: Identifier
    locator: Annotated[SpanLocator | RecordLocator | CommitLocator, Field(discriminator="kind")]


class SpanObserved(HistoryModel):
    kind: Literal["span.observed"] = "span.observed"
    name: str
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    parent: TraceContext | None = None
    links: tuple[TraceContext, ...] = ()
    status: str | None = None


type EventPayload = Annotated[
    SpanObserved
    | ExecutionStarted
    | ExecutionEnded
    | ConnectionObserved
    | AuthenticationObserved
    | InteractionObserved
    | OperationStarted
    | OperationCompleted
    | ProcessObserved
    | ReviewObserved
    | LayoutObserved
    | StateObserved
    | GitCaptureObserved,
    Field(discriminator="kind"),
]


class HistoryEvent(HistoryModel):
    schema_version: Literal[4] = 4
    event_id: Identifier
    execution_id: Identifier | None = None  # Unknown or outside a workbench lifecycle.
    producer: Producer
    sequence: Annotated[int, Field(ge=1)] | None = None
    observed_at: AwareDatetime | None = None
    operation: OperationIdentity | None = None
    resources: Resources = Field(default_factory=Resources)
    causes: tuple[Identifier, ...] = ()
    trace_context: TraceContext | None = None
    artifact_ids: tuple[Identifier, ...] = ()
    source_refs: tuple[SourceReference, ...] = ()
    correlations: tuple[Identifier, ...] = ()
    payload: EventPayload

    @model_validator(mode="after")
    def required_context(self) -> Self:
        if (
            isinstance(self.payload, (OperationStarted, OperationCompleted, GitCaptureObserved, LayoutObserved))
            and self.operation is None
        ):
            raise ValueError("operation observation requires operation identity")
        return self


class TestContext(HistoryModel):
    """Many tests can reference a shared execution; one test can drive several."""

    __test__ = False
    invocation_id: Identifier  # Existing REPO2REE_TEST_RUN_ID / artifact execution_id.
    runtime: Literal["python", "node"]
    suite: Identifier
    test_id: Identifier
    attempt: Annotated[int, Field(ge=0)] = 0
    event_ids: tuple[Identifier, ...] = ()  # Explicit attribution; empty means only execution-level association.


class ProducerCapture(HistoryModel):
    producer: Producer
    first_sequence: Annotated[int, Field(ge=1)]
    last_sequence: Annotated[int, Field(ge=1)]
    delivery: Literal["complete", "partial", "unknown"]

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if self.last_sequence < self.first_sequence:
            raise ValueError("invalid producer sequence range")
        return self


class Recording(HistoryModel):
    status: Literal["open", "closed", "interrupted"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    producers: tuple[ProducerCapture, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_times(self) -> Self:
        if (self.status == "open") != (self.finished_at is None):
            raise ValueError("only open recordings omit finished_at")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("recording ends before it starts")
        return self


class SystemExecution(HistoryModel):
    """One observed workbench lifecycle; event tuple is collection order only.

    Reconnects belong to this execution; another workbench lifecycle gets a new
    execution ID even when it continues the same REE. Partial histories are valid.
    """

    schema_version: Literal[4] = 4
    execution_id: Identifier
    origin: Literal["recorded", "synthetic"]
    scope: Literal["workbench_lifecycle"] = "workbench_lifecycle"
    recording: Recording
    tests: tuple[TestContext, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    events: tuple[HistoryEvent, ...] = ()
    related_event_ids: tuple[Identifier, ...] = ()  # Correlations outside this lifecycle.

    @model_validator(mode="after")
    def unique_identity(self) -> Self:
        if any(event.execution_id != self.execution_id for event in self.events):
            raise ValueError("event belongs to another execution")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("duplicate event ID")
        if len({artifact.artifact_id for artifact in self.artifacts}) != len(self.artifacts):
            raise ValueError("duplicate artifact ID")
        return self


class VerificationResult(HistoryModel):
    contract_id: Identifier
    contract_version: Identifier
    execution_id: Identifier
    verdict: Literal["passed", "violated", "inconclusive", "not_applicable"]
    event_ids: tuple[Identifier, ...] = ()
    reasons: tuple[str, ...] = ()
