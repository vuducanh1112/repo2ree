"""A test's REE with files it wrote itself, as if an attempt had recorded them."""

from __future__ import annotations

from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.workspace.drift import derived_changes, lay_out_again
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.history import CompletedOperation
from repo2ree_protocol.result import ActionResult


def as_recorded(layout: ReeLayout) -> ReeLayout:
    """Commit the REE's files as they are, as ree's snapshot, with its workspace laid out from them as ree lays it
    out: a test's setup, which is no drift of the REE it sets up."""
    lay_out_again(layout, list(derived_changes(layout)))
    with open_history(layout) as history:
        history.capture(operation="test_setup", reuse_unchanged=True)
    return layout


def as_attempt(layout: ReeLayout, operation: str) -> str:
    """Commit the files of the REE or review at ``layout`` as a succeeded attempt of ``operation`` publishes them: a
    test's setup of what a command would have done. Its commit."""
    context = ExecutionContext.new()
    result = ActionResult(status="succeeded", outputs={}).model_copy(update={"context": context})
    with open_history(layout) as history:
        before = history.head_snapshot() or history.capture(operation="observe_existing_ree")
        record = CompletedOperation(
            attempt_id=context.attempt_id,
            run_id=f"test-{context.attempt_id[:12]}",
            context=context,
            command={"operation": operation},
            scope=layout.root.name,
            operation_status="succeeded",
            before_snapshot_id=before,
            result=result,
            phases=["pending", "executing", "completed", "captured"],
        )
        commit, _changed = history.commit_operation(operation=operation, record=record.model_dump(mode="json"))
    return commit
