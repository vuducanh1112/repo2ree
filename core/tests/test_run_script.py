import subprocess
from pathlib import Path

import pytest

from repo2ree_core.container import run_script as rs
from repo2ree_core.container.run_script import (
    ContainerScriptRun,
    build_exec_command,
    run_script_in_container,
)


# --- build_exec_command (pure) ---------------------------------------------


def test_exec_command_without_label_does_not_echo_script():
    payload = build_exec_command(
        Path("/workspace/sub/run.sh"), "sub/run.sh", echo_label=None
    )

    assert payload == "set -e; cd /workspace/sub; sh /workspace/sub/run.sh"


def test_exec_command_with_label_echoes_and_cats_script():
    payload = build_exec_command(
        Path("/workspace/sub/run.sh"), "sub/run.sh", echo_label="build_runtime_script"
    )

    segments = payload.split("; ")
    assert segments[0] == "set -e"
    assert segments[1] == "cd /workspace/sub"
    assert "--- build_runtime_script (sub/run.sh) ---" in segments[2]
    assert segments[3] == "cat /workspace/sub/run.sh"
    assert "--- end build_runtime_script ---" in segments[4]
    assert segments[-1] == "sh /workspace/sub/run.sh"


def test_exec_command_quotes_paths_with_spaces():
    payload = build_exec_command(
        Path("/workspace/a b/run.sh"), "a b/run.sh", echo_label=None
    )

    assert "cd '/workspace/a b'" in payload
    assert "sh '/workspace/a b/run.sh'" in payload


# --- run_script_in_container (imperative shell) ----------------------------


class FakeDocker:
    """Records docker invocations and returns canned results per subcommand."""

    def __init__(self, fail_on=None, returncode=1, stdout="", stderr=""):
        self.calls: list[list[str]] = []
        self._fail_on = fail_on
        self._fail_rc = returncode
        self._fail_stdout = stdout
        self._fail_stderr = stderr

    def run(self, command, capture_output=False, text=False):
        self.calls.append(list(command))
        subcmd = command[1]
        if subcmd == self._fail_on:
            return subprocess.CompletedProcess(
                command, self._fail_rc, self._fail_stdout, self._fail_stderr
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    def subcommands(self) -> list[str]:
        return [c[1] for c in self.calls]


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "run.sh").write_text("echo hi\n")
    return tmp_path


def _install(monkeypatch, fake: FakeDocker):
    monkeypatch.setattr(rs.subprocess, "run", fake.run)
    monkeypatch.setattr(rs.shutil, "which", lambda _: "docker")


def _spec(workspace, **kw):
    return ContainerScriptRun(
        workspace_path=workspace,
        script_rel_path="sub/run.sh",
        container_name="repo2ree-test",
        **kw,
    )


def test_happy_path_runs_full_pipeline(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace), log=lambda *_: None, is_canceled=lambda: False
    )

    assert outcome.status == "succeeded"
    assert outcome.exit_code == 0
    assert fake.subcommands() == ["create", "cp", "start", "exec", "rm"]


def test_sync_workspace_back_adds_copy_out_before_cleanup(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace, sync_workspace_back=True),
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert outcome.status == "succeeded"
    # Two cp calls: workspace in, then workspace back out.
    assert fake.subcommands() == ["create", "cp", "start", "exec", "cp", "rm"]


def test_provision_failure_marks_failed_and_cleans_up(workspace, monkeypatch):
    fake = FakeDocker(fail_on="create", returncode=125)
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace), log=lambda *_: None, is_canceled=lambda: False
    )

    assert outcome.status == "failed"
    assert outcome.exit_code == 125
    # No start/exec after a failed create, but cleanup still runs.
    assert fake.subcommands() == ["create", "rm"]


def test_script_failure_reports_exec_exit_code(workspace, monkeypatch):
    fake = FakeDocker(fail_on="exec", returncode=2)
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace), log=lambda *_: None, is_canceled=lambda: False
    )

    assert outcome.status == "failed"
    assert outcome.exit_code == 2
    assert fake.subcommands() == ["create", "cp", "start", "exec", "rm"]


def test_sync_back_failure_marks_failed(workspace, monkeypatch):
    # Fail the second cp (sync back); the first cp (copy in) succeeds because
    # the failure is keyed on a returncode the copy-in path won't hit.
    class SyncFailDocker(FakeDocker):
        def __init__(self):
            super().__init__()
            self._cp_seen = 0

        def run(self, command, capture_output=False, text=False):
            self.calls.append(list(command))
            if command[1] == "cp":
                self._cp_seen += 1
                if self._cp_seen == 2:
                    return subprocess.CompletedProcess(command, 1, "", "boom")
            return subprocess.CompletedProcess(command, 0, "", "")

    fake = SyncFailDocker()
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace, sync_workspace_back=True),
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert outcome.status == "failed"
    assert fake.subcommands() == ["create", "cp", "start", "exec", "cp", "rm"]


def test_cancel_before_start_returns_canceled_without_provisioning(
    workspace, monkeypatch
):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    outcome = run_script_in_container(
        _spec(workspace), log=lambda *_: None, is_canceled=lambda: True
    )

    assert outcome.status == "canceled"
    assert outcome.exit_code is None
    # Nothing provisioned; only the cleanup rm fires.
    assert fake.subcommands() == ["rm"]


def test_logs_command_and_streams_output(workspace, monkeypatch):
    fake = FakeDocker(
        fail_on="exec", returncode=1, stdout="out line", stderr="err line"
    )
    _install(monkeypatch, fake)

    logged: list[tuple[str, str, str]] = []
    run_script_in_container(
        _spec(workspace),
        log=lambda stream, level, msg: logged.append((stream, level, msg)),
        is_canceled=lambda: False,
    )

    assert ("stdout", "info", "out line") in logged
    assert ("stderr", "warn", "err line") in logged
    assert any(msg.startswith("$ docker exec") for _, _, msg in logged)


def test_missing_script_raises_file_not_found(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with pytest.raises(FileNotFoundError):
        run_script_in_container(
            ContainerScriptRun(
                workspace_path=workspace,
                script_rel_path="sub/missing.sh",
                container_name="repo2ree-test",
            ),
            log=lambda *_: None,
            is_canceled=lambda: False,
        )


def test_path_escaping_workspace_raises_value_error(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with pytest.raises(ValueError):
        run_script_in_container(
            ContainerScriptRun(
                workspace_path=workspace,
                script_rel_path="../escape.sh",
                container_name="repo2ree-test",
            ),
            log=lambda *_: None,
            is_canceled=lambda: False,
        )
