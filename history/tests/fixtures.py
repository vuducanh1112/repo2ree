"""Test-only builder for structural lifecycle assertions."""

from datetime import UTC, datetime

from repo2ree_history.core.models import (
    Artifact,
    AuthenticationObserved,
    EventPayload,
    ExecutionEnded,
    ExecutionStarted,
    GitCaptureObserved,
    HistoryEvent,
    InteractionObserved,
    OperationCompleted,
    OperationIdentity,
    OperationStarted,
    Producer,
    ProducerCapture,
    Recording,
    Resources,
    SystemExecution,
    TestContext,
)


def make_execution() -> SystemExecution:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    producer = Producer(component="workbench", instance_id="bench-process", epoch="boot-1")
    operation = OperationIdentity(operation_id="operation-1", attempt_id="attempt-1", operation="init-ree")
    resources = Resources(
        ree_id="ree-1",
        scope="author",
        workbench_id="bench-1",
        workbench_instance_id="nonce-1",
        provider_id="provider-1",
        allocation_id="allocation-1",
        location_id="location-1",
        session_id="session-1",
    )
    payloads: tuple[EventPayload, ...] = (
        ExecutionStarted(trigger="connection_attempt"),
        AuthenticationObserved(
            session_id="session-1", outcome="authenticated", principal_id="control-plane", mechanism="example"
        ),
        InteractionObserved(
            session_id="session-1",
            request_id="request-1",
            action="exec_action",
            decision="accepted",
            authentication_event_id="event-2",
        ),
        OperationStarted(),
        OperationCompleted(outcome="succeeded", exit_code=0),
        GitCaptureObserved(
            repository_id="repository-1", selection_version=2, capture_status="pending", operation_status="succeeded"
        ),
        ExecutionEnded(reason="workbench_shutdown"),
    )
    events = tuple(
        HistoryEvent(
            event_id=f"event-{index}",
            execution_id="execution-1",
            producer=producer,
            sequence=index,
            observed_at=now,
            resources=resources,
            operation=operation
            if isinstance(payload, (OperationStarted, OperationCompleted, GitCaptureObserved))
            else None,
            payload=payload,
        )
        for index, payload in enumerate(payloads, 1)
    )
    return SystemExecution(
        execution_id="execution-1",
        origin="synthetic",
        recording=Recording(
            status="closed",
            started_at=now,
            finished_at=now,
            producers=(
                ProducerCapture(producer=producer, first_sequence=1, last_sequence=len(events), delivery="complete"),
            ),
            limitations=("Synthetic illustration; artifact URI is not a real repository.",),
        ),
        tests=(
            TestContext(
                invocation_id="test-invocation-1", runtime="python", suite="example", test_id="example-lifecycle"
            ),
        ),
        artifacts=(
            Artifact(
                artifact_id="repo-copy",
                kind="git_repository",
                uri="rees/workbench",
                repository_id="repository-1",
                resources=resources,
            ),
        ),
        events=events,
    )
