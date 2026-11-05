from __future__ import annotations

import json
import os
import stat
import subprocess
import threading
import time
from pathlib import Path

import pytest

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ResultFrame
from repo2ree_workbench.executor_process import LocalExecutor, ScriptBackend, declared_environment
from repo2ree_workbench.tools import tool_environment


def test_local_executor_passes_explicit_context_over_process_boundary(tmp_path):
    script = tmp_path / "context-executor"
    script.write_text(
        "#!/bin/sh\ncat >/dev/null\n"
        'test "$6" = --execution-context || exit 1\n'
        'printf \'{"status":"succeeded","context":%s}\\n\' "$7"\n'
    )
    script.chmod(0o700)
    context = ExecutionContext.new(ree_id="ree-1")
    frames = list(LocalExecutor(tmp_path, str(script)).exec_action("{}", "reused-run", {}, context, ree_id="ree"))
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
    frames = list(executor.exec_action(json.dumps({"operation": "test"}), "run-1", {}, ree_id="ree"))
    assert frames == [ResultFrame.model_validate({"result": {"status": "succeeded", "outputs": {}}})]
    assert b"".join(executor.exec_query_stream(["query"], ree_id="ree")) == b"query-result"


def test_a_query_written_to_a_file_never_passes_through_memory_and_fails_loudly(
    fake_executor: Path, tmp_path: Path
) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(fake_executor))
    target = tmp_path / "out.bin"

    executor.exec_query_to_file(["query"], target, ree_id="ree")
    assert target.read_bytes() == b"query-result"

    with pytest.raises(RuntimeError, match="exit 7"):
        executor.exec_query_to_file(["fail"], tmp_path / "failed.bin", ree_id="ree")


def test_local_executor_reports_simple_failure(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "ree", str(fake_executor))
    with pytest.raises(RuntimeError, match="exit 7"):
        executor.exec_simple(["fail"], ree_id="ree")


def test_local_executor_reads_executor_build(fake_executor: Path, tmp_path: Path) -> None:
    build = LocalExecutor(tmp_path / "ree", str(fake_executor)).build_info()

    assert build.revision == "executor-revision"


def test_copy_in_is_atomic_and_confined(fake_executor: Path, tmp_path: Path) -> None:
    root = tmp_path / "ree"
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    executor = LocalExecutor(root, str(fake_executor))
    executor.copy_in(str(source), "/ree/upload-staging/input.bin", ree_id="ree")
    assert (root / "ree" / "upload-staging/input.bin").read_bytes() == b"payload"
    with pytest.raises(ValueError, match=r"escapes|must not"):
        executor.copy_in(str(source), "../outside", ree_id="ree")


def test_a_store_runs_each_command_against_the_ree_it_names(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "store", str(fake_executor))

    assert executor.ree_root("ree-1") == (tmp_path / "store" / "ree-1").resolve()
    observed = executor._environment(executor.ree_root("ree-1"))
    assert observed["REPO2REE_WORKBENCH_ROOT"] == os.fspath((tmp_path / "store" / "ree-1").resolve())
    for refused in ("..", "a/b", "", "-x"):
        with pytest.raises(ValueError):
            executor.ree_root(refused)


def test_a_store_deletes_an_ree_only_when_none_of_its_runs_is_active(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "store", str(fake_executor))
    (tmp_path / "store" / "ree-1" / "workspace").mkdir(parents=True)
    executor._runs[(executor.ree_root("ree-1"), "run-1")] = subprocess.Popen(["sleep", "5"], text=True)
    try:
        with pytest.raises(RuntimeError, match="in progress"):
            executor.delete_ree("ree-1")
    finally:
        executor._runs.pop((executor.ree_root("ree-1"), "run-1")).kill()

    executor.delete_ree("ree-1")
    executor.delete_ree("ree-2")  # Nothing there is nothing to delete.
    assert not (tmp_path / "store" / "ree-1").exists()


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
    running = threading.Thread(target=lambda: frames.extend(executor.exec_action("{}", "run-1", {}, ree_id="ree")))
    running.start()
    while (executor.ree_root("ree"), "run-1") not in executor._runs:
        time.sleep(0.01)
    started = time.monotonic()
    executor.cancel_run("run-1", ree_id="ree")
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


def test_the_tools_a_bundle_names_reach_every_executor(fake_executor: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "tools"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        json.dumps({"tools": {"git-lfs": "/nix/store/x/bin/git-lfs"}, "bin_dir": "/nix/store/y/bin", "env": {"A": "1"}})
    )
    executor = LocalExecutor(tmp_path / "root", str(fake_executor), environment=tool_environment(bundle))

    observed = executor._environment(executor.root)

    assert observed["REPO2REE_TOOL_GIT_LFS"] == "/nix/store/x/bin/git-lfs"
    assert observed["REPO2REE_TOOLS_BIN"] == "/nix/store/y/bin"
    assert observed["A"] == "1"
    assert tool_environment(None) == {}


def test_two_rees_in_a_store_run_the_same_run_id_side_by_side(tmp_path: Path) -> None:
    # The API's quick commands share fixed run ids (patch-definition); a run id names a run within one REE.
    executor = LocalExecutor(tmp_path / "store", str(cancellable_executor(tmp_path, "cooperative")))
    for ree_id in ("ree-1", "ree-2"):
        executor.ree_root(ree_id).mkdir(parents=True)
    threads = [
        threading.Thread(target=lambda ree_id=ree_id: list(executor.exec_action("{}", "patch", {}, ree_id=ree_id)))
        for ree_id in ("ree-1", "ree-2")
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + 5
    while len(executor._runs) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert set(executor._runs) == {(executor.ree_root("ree-1"), "patch"), (executor.ree_root("ree-2"), "patch")}
    (tmp_path / "marker").touch()
    for thread in threads:
        thread.join(timeout=5)


def test_a_container_workbench_runs_each_ree_in_the_image_it_declares(fake_executor: Path, tmp_path: Path) -> None:
    scripts = ScriptBackend("container", "podman", "socket", ("/repo2ree", "/home/me/repo2ree"))
    executor = LocalExecutor(tmp_path / "store", str(fake_executor), scripts=scripts)
    root = executor.ree_root("ree-1")
    root.mkdir(parents=True)
    environment = {"kind": "image", "image": "python:3.12-slim", "needs_container_engine": True}
    (root / "ree.json").write_text(json.dumps({"subject": {"definition": {"environment": environment}}}))

    choice = json.loads(executor._environment(root)["REPO2REE_SCRIPT_RUNNER"])

    assert choice == {
        "backend": "container",
        "engine": "podman",
        "image": "python:3.12-slim",
        "script_engine": "socket",
        "engine_path": {"local": "/repo2ree", "engine": "/home/me/repo2ree"},
        "owner": "",
        "refused": None,
    }
    assert declared_environment(executor.ree_root("ree-2")) == {}


@pytest.mark.parametrize(
    ("backend", "script_engine", "environment", "refused"),
    [
        ("container", "socket", {}, "declare the image"),
        ("container", "socket", {"kind": "host"}, "declare the image"),
        ("host", "socket", {"kind": "image", "image": "python:3.12"}, "cannot run them in python:3.12"),
        ("container", "none", {"kind": "image", "image": "docker:29", "needs_container_engine": True}, "engine"),
        ("host", "socket", {"kind": "host"}, None),
        ("host", "socket", {}, None),
    ],
)
def test_a_store_workbench_refuses_an_environment_it_cannot_give(
    backend: str, script_engine: str, environment: dict[str, object], refused: str | None
) -> None:
    refusal = ScriptBackend(backend, "docker", script_engine).refusal(environment)
    assert (refusal is None) == (refused is None)
    if refused:
        assert refused in (refusal or "")


def test_a_bench_set_up_for_one_ree_says_nothing_of_where_scripts_run(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalExecutor(tmp_path / "root", str(fake_executor))
    assert "REPO2REE_SCRIPT_RUNNER" not in executor._environment(executor.root)


def journaled(directory: Path) -> list[dict[str, object]]:
    (path,) = directory.glob("*.ndjson")
    return [json.loads(line) for line in path.read_text().splitlines()]


def executions(directory: Path) -> list[tuple[object, ...]]:
    return [
        (record["key"], record["from"], record["to"], record["facts"])
        for record in journaled(directory)
        if record.get("subject") == "Execution"
    ]


def test_the_workbench_journals_each_executor_it_starts_and_how_it_ended(fake_executor: Path, tmp_path: Path) -> None:
    from repo2ree_workbench.journal import store_journal

    store = tmp_path / "store"
    context = ExecutionContext.new(ree_id="ree").model_copy(update={"dispatch_record": "api-000001#7"})
    with store_journal(store, "lab-1") as directory:
        list(
            LocalExecutor(store, str(fake_executor)).exec_action(
                '{"operation": "lint_scripts"}', "r1", {}, context, ree_id="ree"
            )
        )
    assert executions(directory) == [
        (
            context.attempt_id,
            None,
            "started",
            {"operation": "lint_scripts", "run_id": "r1", "dispatched_by": "api-000001#7"},
        ),
        (context.attempt_id, "started", "exited", {"exit_code": 0}),
    ]
    assert journaled(directory)[0]["instance"] == "lab-1"


@pytest.mark.parametrize(("cause", "record"), [("cancel", "api-000001#9"), ("caller_gone", None)])
def test_a_stopped_executor_is_journaled_with_why_it_was_asked_to_stop(
    tmp_path: Path, cause: str, record: str | None
) -> None:
    from repo2ree_workbench.journal import store_journal

    store = tmp_path / "store"
    executor = LocalExecutor(store, str(cancellable_executor(tmp_path, "cooperative")), cancel_grace=0.3)
    frames: list[object] = []
    with store_journal(store, "lab-1") as directory:
        running = threading.Thread(target=lambda: frames.extend(executor.exec_action("{}", "run-1", {}, ree_id="ree")))
        running.start()
        while (executor.ree_root("ree"), "run-1") not in executor._runs:
            time.sleep(0.01)
        executor.cancel_run("run-1", ree_id="ree", cause=cause, record=record)  # type: ignore[arg-type]
        executor.cancel_run("run-1", ree_id="ree", cause="caller_gone")
        running.join(timeout=10)
    (_, _, target, facts) = executions(directory)[-1]
    assert (target, facts) == ("stopped", {"exit_code": 0, "cause": cause, "canceled_by": record})


def test_a_second_workbench_process_cannot_hold_a_held_store(tmp_path: Path) -> None:
    from repo2ree_workbench.journal import StoreHeldError, store_journal

    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from repo2ree_workbench.journal import store_journal\n"
        "with store_journal(Path(sys.argv[1]), 'lab-1'):\n"
        "    print('held', flush=True)\n"
        "    time.sleep(30)\n"
    )
    holder = subprocess.Popen(
        [os.environ.get("PYTHON", "python"), "-c", script, str(tmp_path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(StoreHeldError), store_journal(tmp_path, "lab-1"):
            pass
    finally:
        holder.kill()
        holder.wait()
