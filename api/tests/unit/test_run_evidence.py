"""API post-processing must not discard the executor's published evidence."""

import pytest

from repo2ree_api.control import run_orchestration as orchestration
from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.command import SealReeCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, HistoryReference


@pytest.mark.parametrize("postprocessing_fails", [False, True])
def test_postprocessing_retains_execution_evidence(online_ree, monkeypatch, postprocessing_fails):
    context = ExecutionContext.new(ree_id=online_ree.ree_id)
    history = HistoryReference(
        selection_version=1,
        attempt_id=context.attempt_id,
        scope=".",
        capture_status="captured",
        operation_status="succeeded",
        after_snapshot_id="published",
        before_snapshot_id="before",
        changed=True,
    )
    completed = ActionResult(status="succeeded", context=context, history=history, outputs={"sealed": True})
    monkeypatch.setattr(workbench_manager, "dispatch_action", lambda *args: completed)
    monkeypatch.setattr(orchestration, "is_cancel_requested", lambda *args: False)
    results = []

    def start(ree_id, operation, request_payload, prefix, runner, **kwargs):
        results.append(runner(ree_id, "run"))
        return {}

    def after_success(handle, result):
        if postprocessing_fails:
            raise RuntimeError("index unavailable")
        return ActionResult(status="succeeded", outputs={"indexed": True})

    monkeypatch.setattr(orchestration, "start_background_run", start)
    orchestration.start_single_command_run(
        online_ree.ree_id,
        operation="seal",
        action="seal_ree",
        command=SealReeCommand(),
        run_id_prefix="seal",
        request_payload={},
        canceled_message="canceled",
        after_success=after_success,
    )
    result = results[0]
    assert result.context == context
    assert result.history == history
    assert result.history.operation_status == "succeeded"
    assert result.status == ("failed" if postprocessing_fails else "succeeded")
