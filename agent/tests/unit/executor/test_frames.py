from __future__ import annotations

from repo2ree_agent.executor.frames import executor_line_to_frame, parse_action_result
from repo2ree_protocol.agent import LogFrame, SpanFrame
from repo2ree_protocol.result import ActionResult


def test_executor_line_parses_log_span_and_plain_text() -> None:
    assert executor_line_to_frame('{"type":"log","stream":"stdout","level":"info","message":"hello"}') == LogFrame(
        stream="stdout", level="info", message="hello"
    )
    assert executor_line_to_frame('{"type":"span","payload":"encoded"}') == SpanFrame(payload="encoded")
    assert executor_line_to_frame("not-json") == LogFrame(stream="system", level="info", message="not-json")
    assert executor_line_to_frame('{"type":"future"}') == LogFrame(
        stream="system", level="info", message='{"type":"future"}'
    )


def test_parse_action_result_accepts_valid_result_and_rejects_invalid_output() -> None:
    succeeded = ActionResult(status="succeeded")

    assert parse_action_result(succeeded.model_dump_json(), 0) == succeeded
    malformed = parse_action_result("not-json", 9)
    assert malformed.status == "failed"
    assert malformed.exit_code == 9
    assert malformed.failure is not None
    assert malformed.failure.origin == "agent"


def test_parse_action_result_uses_nonzero_sentinel_without_process_code() -> None:
    result = parse_action_result("", 0)

    assert result.status == "failed"
    assert result.exit_code == 1
