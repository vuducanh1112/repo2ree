"""Operation failures and capture failures remain separate evidence."""

from dataclasses import replace

from history.tests.test_core import snapshot

from repo2ree_history.core.assembly import assemble
from repo2ree_history.core.evidence import GitDocument, SourceDocument
from repo2ree_history.core.models import (
    Artifact,
    GitCaptureObserved,
    OperationCompleted,
    RecordLocator,
    SourceReference,
)


def failure():
    return {
        "category": "execution",
        "origin": "core",
        "message": "build failed",
        "retryable": False,
        "details": {"code": "build_exit"},
    }


def captured(operation_status="failed", capture_status="captured"):
    recording = snapshot()
    ref = SourceReference(artifact_id="repo", locator=RecordLocator(path=".git/repo2ree/operations/attempt.json"))
    record = {
        "context": {"operation_id": "op", "attempt_id": "attempt", "ree_id": "ree"},
        "command": {"operation": "build"},
        "selection_version": 2,
        "operation_status": operation_status,
        "capture_status": capture_status,
        "operation_failure": failure() if operation_status == "failed" else None,
        "capture_error": "disk full" if capture_status == "failed" else None,
    }
    return replace(
        recording,
        artifacts=(
            *recording.artifacts,
            Artifact(artifact_id="repo", kind="git_repository", uri="repo", repository_id="repo"),
        ),
        operations=(GitDocument(record, ref, "repo", "author"),),
    )


def test_git_failure_details_survive_assembly():
    result = assemble(captured())
    event = next(e for e in result.events if e.payload.kind == "git_capture.observed")
    assert isinstance(event.payload, GitCaptureObserved)
    assert event.payload.operation_failure is not None
    assert event.payload.operation_failure.details is not None
    assert event.payload.operation_failure.message == "build failed"
    assert event.payload.operation_failure.details.document == {"code": "build_exit"}


def test_successful_operation_and_failed_capture_stay_distinct():
    result = assemble(captured("succeeded", "failed"))
    event = next(e for e in result.events if e.payload.kind == "git_capture.observed")
    assert isinstance(event.payload, GitCaptureObserved)
    assert event.payload.operation_status == "succeeded"
    assert event.payload.operation_failure is None
    assert event.payload.capture_status == "failed"
    assert event.payload.capture_error == "disk full"


def test_span_failure_projection_and_partial_failure():
    recording = snapshot()
    document = recording.spans[0].document
    document["attributes"]["repo2ree.status"] = "failed"
    document["attributes"].update(
        {f"repo2ree.failure.{key}": value for key, value in failure().items() if key != "details"}
    )
    result = assemble(recording)
    completed = next(e for e in result.events if e.payload.kind == "operation.completed")
    assert isinstance(completed.payload, OperationCompleted)
    assert completed.payload.failure is not None
    assert completed.payload.failure.message == "build failed"
    document["attributes"].pop("repo2ree.failure.origin")
    result = assemble(recording)
    completed = next(e for e in result.events if e.payload.kind == "operation.completed")
    assert isinstance(completed.payload, OperationCompleted)
    assert completed.payload.outcome == "failed"
    assert completed.payload.failure is None
    assert any(d.code == "partial_failure" and d.source_refs for d in result.diagnostics)


def test_cancellation_has_no_failure():
    recording = snapshot()
    doc = {
        **recording.spans[0].document,
        "attributes": {**recording.spans[0].document["attributes"], "repo2ree.status": "canceled"},
    }
    result = assemble(replace(recording, spans=(SourceDocument(doc, recording.spans[0].source),)))
    completed = next(e for e in result.events if e.payload.kind == "operation.completed")
    assert isinstance(completed.payload, OperationCompleted)
    assert completed.payload.outcome == "canceled"
    assert completed.payload.failure is None
