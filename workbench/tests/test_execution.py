from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from repo2ree_workbench.cli_process import LocalCli, ScriptBackend
from repo2ree_workbench.tools import tool_environment


@pytest.fixture
def fake_executor(tmp_path: Path) -> Path:
    (tmp_path / "bin").mkdir()
    path = tmp_path / "bin" / "ree"
    path.write_text(
        "#!/bin/sh\n"
        'while [ $# -gt 0 ]; do case "$1" in -C|--run-id|--context) shift 2 ;; '
        "--json) shift ;; *) break ;; esac; done\n"
        'case "$1" in\n'
        "  query) printf query-result ;;\n"
        "  echo) cat ;;\n"
        "  fail) echo failed >&2; exit 7 ;;\n"
        '  build-info) printf \'%s\\n\' \'{"version":"0.1.0","revision":"executor-revision"}\' ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_local_executor_runs_queries(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalCli(tmp_path / "ree", str(fake_executor))
    assert b"".join(executor.exec_query_stream(["query"], ree_id="ree")) == b"query-result"


def test_a_query_reads_what_it_is_given_on_stdin(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalCli(tmp_path / "ree", str(fake_executor))
    assert b"".join(executor.exec_query_stream(["echo"], ree_id="ree", stdin=b"set -eu\n")) == b"set -eu\n"


def test_a_query_written_to_a_file_never_passes_through_memory_and_fails_loudly(
    fake_executor: Path, tmp_path: Path
) -> None:
    executor = LocalCli(tmp_path / "ree", str(fake_executor))
    target = tmp_path / "out.bin"

    executor.exec_query_to_file(["query"], target, ree_id="ree")
    assert target.read_bytes() == b"query-result"

    with pytest.raises(RuntimeError, match="exit 7"):
        executor.exec_query_to_file(["fail"], tmp_path / "failed.bin", ree_id="ree")


def test_local_executor_reports_a_failed_run(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalCli(tmp_path / "ree", str(fake_executor))
    with pytest.raises(RuntimeError, match="exit 7"):
        executor.run(executor.ree_root("ree"), ["fail"], 60)


def test_local_executor_reads_executor_build(fake_executor: Path, tmp_path: Path) -> None:
    build = LocalCli(tmp_path / "ree", str(fake_executor)).build_info()

    assert build.revision == "executor-revision"


def test_copy_in_is_atomic_and_confined(fake_executor: Path, tmp_path: Path) -> None:
    root = tmp_path / "ree"
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    executor = LocalCli(root, str(fake_executor))
    executor.copy_in(str(source), "/ree/upload-staging/input.bin", ree_id="ree")
    assert (root / "ree" / "upload-staging/input.bin").read_bytes() == b"payload"
    with pytest.raises(ValueError, match=r"escapes|must not"):
        executor.copy_in(str(source), "../outside", ree_id="ree")


def test_a_store_runs_each_command_against_the_ree_it_names(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalCli(tmp_path / "store", str(fake_executor))

    assert executor.ree_root("ree-1") == (tmp_path / "store" / "ree-1").resolve()
    root = executor.ree_root("ree-1")
    assert executor.at(root, ["show"]) == [str(fake_executor), "-C", os.fspath(root), "show"]
    assert "REPO2REE_WORKBENCH_ROOT" not in executor.environment(root)
    for refused in ("..", "a/b", "", "-x"):
        with pytest.raises(ValueError):
            executor.ree_root(refused)


def test_the_tools_a_bundle_names_reach_every_executor(fake_executor: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "tools"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        json.dumps({"tools": {"git-lfs": "/nix/store/x/bin/git-lfs"}, "bin_dir": "/nix/store/y/bin", "env": {"A": "1"}})
    )
    executor = LocalCli(tmp_path / "root", str(fake_executor), environment=tool_environment(bundle))

    observed = executor.environment(executor.root)

    assert observed["REPO2REE_TOOL_GIT_LFS"] == "/nix/store/x/bin/git-lfs"
    assert observed["REPO2REE_TOOLS_BIN"] == "/nix/store/y/bin"
    assert observed["A"] == "1"
    assert tool_environment(None) == {}


def test_a_container_workbench_tells_ree_its_engine_and_runs_no_scripts_on_its_host(
    fake_executor: Path, tmp_path: Path
) -> None:
    scripts = ScriptBackend("container", "podman", "socket", ("/repo2ree", "/home/me/repo2ree"), owner="/store")
    executor = LocalCli(tmp_path / "store", str(fake_executor), scripts=scripts)

    environment = executor.environment(executor.root)

    assert {name: environment[name] for name in scripts.environment()} == {
        "REPO2REE_ENGINE": "podman",
        "REPO2REE_HOST_SCRIPTS": "refused",
        "REPO2REE_SCRIPT_ENGINE": "socket",
        "REPO2REE_JOB_OWNER": "/store",
        "REPO2REE_ENGINE_PATH": "/repo2ree=/home/me/repo2ree",
    }


def test_a_host_workbench_tells_ree_it_has_no_engine() -> None:
    assert ScriptBackend("host").environment() == {"REPO2REE_ENGINE": "none", "REPO2REE_HOST_SCRIPTS": "allowed"}


def test_leftover_jobs_go_but_those_of_adopted_executions_stay(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    removed = tmp_path / "removed"
    engine.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  ps) printf 'c1 a1\\nc2 a2\\nc3 \\n' ;;\n"
        f'  rm) shift; echo "$@" > {removed} ;;\n'
        "esac\n"
    )
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)

    ScriptBackend("container", str(engine), owner="store").remove_leftover_jobs(frozenset({"a1"}))

    assert removed.read_text().split() == ["-f", "c2", "c3"]


def test_a_bench_set_up_for_one_ree_says_nothing_of_where_scripts_run(fake_executor: Path, tmp_path: Path) -> None:
    executor = LocalCli(tmp_path / "root", str(fake_executor))
    assert "REPO2REE_ENGINE" not in executor.environment(executor.root)


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
