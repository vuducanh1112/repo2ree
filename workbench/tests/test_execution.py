from __future__ import annotations

import json
import os
import stat
import threading
import time
from pathlib import Path

import pytest

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ResultFrame
from repo2ree_workbench.executor_process import LocalExecutor


def test_local_executor_passes_explicit_context_over_process_boundary(tmp_path):
    script = tmp_path / "context-executor"
    script.write_text(
        "#!/bin/sh\ncat >/dev/null\n"
        'test "$6" = --execution-context || exit 1\n'
        'printf \'{"status":"succeeded","context":%s}\\n\' "$7"\n'
    )
    script.chmod(0o700)
    context = ExecutionContext.new(ree_id="ree-1")
    frames = list(LocalExecutor(tmp_path, str(script)).exec_action("{}", "reused-run", {}, context))
    assert isinstance(frames[-1], ResultFrame)
    assert frames[-1].result.context == context


@pytest.fixture
def fake_executor(tmp_path: Path) -> Path:
    path = tmp_path / "repo2ree-exec"
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  execute) cat >/dev/null; printf \'%s\\n\' \'{"status":"succeeded","outputs":{}}\' ;;\n'
        "  query) printf query-result ;;\n"
        "  fail) echo failed >&2; exit 7 ;;\n"
        '  build-info) printf \'%s\\n\' \'{"version":"0.1.0","revision":"executor-revision"}\' ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_local_executor_runs_actions_and_queries(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(fake_executor))
    frames = list(executor.exec_action(json.dumps({"operation": "test"}), "run-1", {}))
    assert frames == [ResultFrame.model_validate({"result": {"status": "succeeded", "outputs": {}}})]
    assert b"".join(executor.exec_query_stream(["query"])) == b"query-result"


def test_a_query_written_to_a_file_never_passes_through_memory_and_fails_loudly(
    fake_executor: Path, tmp_path: Path
) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(fake_executor))
    target = tmp_path / "out.bin"

    executor.exec_query_to_file(["query"], target)
    assert target.read_bytes() == b"query-result"

    with pytest.raises(RuntimeError, match="exit 7"):
        executor.exec_query_to_file(["fail"], tmp_path / "failed.bin")


def test_local_executor_reports_simple_failure(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(fake_executor))
    with pytest.raises(RuntimeError, match="exit 7"):
        executor.exec_simple(["fail"])


def test_local_executor_reads_executor_build(fake_executor: Path, tmp_path: Path) -> None:
    build = LocalExecutor(tmp_path / "ree", str(fake_executor)).build_info()

    assert build.revision == "executor-revision"


def test_copy_in_is_atomic_and_confined(fake_executor: Path, tmp_path: Path) -> None:
    root = tmp_path / "ree"
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    executor = LocalExecutor(root, str(fake_executor))
    executor.copy_in(str(source), "/ree/upload-staging/input.bin")
    assert (root / "upload-staging/input.bin").read_bytes() == b"payload"
    with pytest.raises(ValueError, match=r"escapes|must not"):
        executor.copy_in(str(source), "../outside")


def test_action_receives_configured_root(fake_executor: Path, tmp_path: Path) -> None:
    root = tmp_path / "custom-root"
    executor = LocalExecutor(root, str(fake_executor))
    observed = executor._environment()
    assert observed["REPO2REE_WORKBENCH_ROOT"] == os.fspath(root.resolve())


def cancellable_executor(tmp_path: Path, on_term: str) -> Path:
    """An executor whose run waits for the cancel marker (``cooperative``), or ignores it.

    ``on_term`` is what it does on SIGTERM: report canceled (``report``), or nothing (``ignore``).
    """
    path = tmp_path / "repo2ree-exec"
    marker = tmp_path / "marker"
    trap = {"report": 'trap \'echo {\\"status\\":\\"canceled\\"}; exit 0\' TERM', "ignore": "trap '' TERM"}
    wait = (
        f'while [ ! -e "{marker}" ]; do sleep 0.05; done; echo \'{{"status":"canceled"}}\''
        if on_term == "cooperative"
        else "while :; do sleep 0.05; done"
    )
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"  execute) cat >/dev/null; {trap.get(on_term, '')}\n    {wait} ;;\n"
        f'  cancel-run) touch "{marker}" ;;\n'
        "esac\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def cancel_while_running(executor: LocalExecutor) -> tuple[list[object], float]:
    frames: list[object] = []
    running = threading.Thread(target=lambda: frames.extend(executor.exec_action("{}", "run-1", {})))
    running.start()
    while "run-1" not in executor._runs:
        time.sleep(0.01)
    started = time.monotonic()
    executor.cancel_run("run-1")
    returned = time.monotonic() - started
    running.join(timeout=10)
    assert not running.is_alive()
    return frames, returned


@pytest.mark.parametrize("on_term", ["cooperative", "report", "ignore"])
def test_cancel_lets_the_executor_stop_itself_and_forces_only_one_that_does_not(tmp_path: Path, on_term: str) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(cancellable_executor(tmp_path, on_term)), cancel_grace=0.3)
    executor.cancel_kill = 0.3
    frames, returned = cancel_while_running(executor)
    assert returned < 0.3, "cancel_run waits for the grace period instead of returning"
    result = frames[-1]
    assert isinstance(result, ResultFrame)
    if on_term == "ignore":
        assert result.result.status == "failed"  # Killed: it could not report.
    else:
        assert result.result.status == "canceled"
