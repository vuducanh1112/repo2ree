from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from repo2ree_protocol.frames import ResultFrame
from repo2ree_workbench.executor_process import LocalExecutor


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
