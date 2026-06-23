"""Tests for DockerWorkingEnvironment lifecycle and exec behaviour."""

import subprocess
from pathlib import Path

import pytest

import repo2ree_core.working_environment.docker_env as docker_mod
import repo2ree_core.working_environment.manager as manager_mod
from repo2ree_core.working_environment.base import (
    ProvisioningCanceledError,
    ScriptStep,
    WorkingEnvironmentSpec,
)
from repo2ree_core.working_environment.docker_env import DockerWorkingEnvironment

# ================================================
# Test infrastructure
# ================================================


class FakeDocker:
    """Records docker CLI invocations and returns canned results per subcommand."""

    def __init__(
        self,
        fail_on: str | None = None,
        returncode: int = 1,
        stdout: str = "",
        stderr: str = "",
    ):
        self.calls: list[list[str]] = []
        self._fail_on = fail_on
        self._fail_rc = returncode
        self._fail_stdout = stdout
        self._fail_stderr = stderr

    def run(self, command, capture_output=False, text=False, input=None):
        self.calls.append(list(command))
        if command[1] == self._fail_on:
            return subprocess.CompletedProcess(command, self._fail_rc, self._fail_stdout, self._fail_stderr)
        return subprocess.CompletedProcess(command, 0, "", "")

    def subcommands(self) -> list[str]:
        return [c[1] for c in self.calls]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "run.sh").write_text("echo hi\n")
    return tmp_path


def _install(monkeypatch, fake: FakeDocker) -> None:
    monkeypatch.setattr(docker_mod.subprocess, "run", fake.run)
    monkeypatch.setattr(docker_mod.shutil, "which", lambda _: "docker")


def _we(
    workspace: Path,
    run_id: str = "test-run",
    *,
    is_canceled=None,
) -> DockerWorkingEnvironment:
    spec = WorkingEnvironmentSpec(
        workspace_path=workspace,
        run_id=run_id,
        log=lambda *_: None,
        is_canceled=is_canceled,
    )
    return DockerWorkingEnvironment(spec)


def _step(**kw) -> ScriptStep:
    return ScriptStep(script_rel_path="sub/run.sh", **kw)


# ================================================
# Lifecycle pipeline order
# ================================================


def test_happy_path_runs_full_pipeline(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        outcome = we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: False)

    assert outcome.status == "succeeded"
    assert outcome.exit_code == 0
    assert fake.subcommands() == ["create", "cp", "start", "exec", "rm"]


def test_sync_out_after_exec_adds_cp_before_rm(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: False)
        we.sync_out(log=lambda *_: None)

    assert fake.subcommands() == ["create", "cp", "start", "exec", "cp", "rm"]


def test_create_failure_raises_without_rm(workspace, monkeypatch):
    fake = FakeDocker(fail_on="create", returncode=125)
    _install(monkeypatch, fake)

    with pytest.raises(RuntimeError, match="docker create failed"):
        with _we(workspace):
            pass

    # Container was never created — no cleanup needed and none should be issued.
    assert fake.subcommands() == ["create"]


def test_cp_in_failure_cleans_up_and_raises(workspace, monkeypatch):
    fake = FakeDocker(fail_on="cp", returncode=1)
    _install(monkeypatch, fake)

    with pytest.raises(RuntimeError, match="docker cp"):
        with _we(workspace):
            pass

    # _cp_in calls _destroy before raising; __exit__ is not reached.
    assert fake.subcommands() == ["create", "cp", "rm"]


def test_start_failure_cleans_up_and_raises(workspace, monkeypatch):
    class StartFailDocker(FakeDocker):
        def run(self, command, capture_output=False, text=False, input=None):
            self.calls.append(list(command))
            if command[1] == "start":
                return subprocess.CompletedProcess(command, 1, "", "start error")
            return subprocess.CompletedProcess(command, 0, "", "")

    fake = StartFailDocker()
    _install(monkeypatch, fake)

    with pytest.raises(RuntimeError, match="docker start failed"):
        with _we(workspace):
            pass

    assert fake.subcommands() == ["create", "cp", "start", "rm"]


def test_cancel_during_provisioning_cleans_up_before_copy(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    cancel_checks = iter([False, True])

    with pytest.raises(ProvisioningCanceledError, match="during provisioning"):
        with _we(workspace, is_canceled=lambda: next(cancel_checks)):
            pass

    assert fake.subcommands() == ["create", "rm"]


# ================================================
# exec_script outcomes
# ================================================


def test_exec_failure_reports_exit_code(workspace, monkeypatch):
    fake = FakeDocker(fail_on="exec", returncode=2)
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        outcome = we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: False)

    assert outcome.status == "failed"
    assert outcome.exit_code == 2
    assert fake.subcommands() == ["create", "cp", "start", "exec", "rm"]


def test_cancel_before_exec_returns_canceled(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        outcome = we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: True)

    assert outcome.status == "canceled"
    assert outcome.exit_code is None
    # Container was provisioned normally; exec was skipped; teardown fires.
    assert fake.subcommands() == ["create", "cp", "start", "rm"]


# ================================================
# exec_script flags
# ================================================


def test_stdin_text_passes_interactive_flag(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(stdin_text="payload"), log=lambda *_: None, is_canceled=lambda: False)

    exec_call = fake.calls[3]  # create, cp, start, exec
    assert exec_call[0:3] == ["docker", "exec", "-i"]


def test_no_stdin_text_omits_interactive_flag(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: False)

    exec_call = fake.calls[3]
    assert "-i" not in exec_call


def test_login_shell_false_uses_sh_c(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(login_shell=False), log=lambda *_: None, is_canceled=lambda: False)

    exec_call = fake.calls[3]
    sh_idx = exec_call.index("sh")
    assert exec_call[sh_idx + 1] == "-c"


def test_login_shell_true_uses_sh_lc(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(login_shell=True), log=lambda *_: None, is_canceled=lambda: False)

    exec_call = fake.calls[3]
    sh_idx = exec_call.index("sh")
    assert exec_call[sh_idx + 1] == "-lc"


# ================================================
# sync_out
# ================================================


def test_sync_out_failure_returns_false(workspace, monkeypatch):
    class SyncFailDocker(FakeDocker):
        def __init__(self):
            super().__init__()
            self._cp_count = 0

        def run(self, command, capture_output=False, text=False, input=None):
            self.calls.append(list(command))
            if command[1] == "cp":
                self._cp_count += 1
                if self._cp_count == 2:
                    return subprocess.CompletedProcess(command, 1, "", "fail")
            return subprocess.CompletedProcess(command, 0, "", "")

    fake = SyncFailDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.exec_script(_step(), log=lambda *_: None, is_canceled=lambda: False)
        ok = we.sync_out(log=lambda *_: None)

    assert not ok
    assert fake.subcommands() == ["create", "cp", "start", "exec", "cp", "rm"]


# ================================================
# Logging
# ================================================


def test_exec_logs_command_and_streams_stdout_stderr(workspace, monkeypatch):
    fake = FakeDocker(fail_on="exec", returncode=1, stdout="out line", stderr="err line")
    _install(monkeypatch, fake)

    logged: list[tuple[str, str, str]] = []

    with _we(workspace) as we:
        we.exec_script(
            _step(),
            log=lambda stream, level, msg: logged.append((stream, level, msg)),
            is_canceled=lambda: False,
        )

    assert ("stdout", "info", "out line") in logged
    assert ("stderr", "warn", "err line") in logged
    assert any(msg.startswith("$ docker exec") for _, _, msg in logged)


# ================================================
# Path safety
# ================================================


def test_exec_script_rejects_path_escaping_workspace(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        with pytest.raises(ValueError, match="escapes workspace"):
            we.exec_script(
                ScriptStep(script_rel_path="../escape.sh"),
                log=lambda *_: None,
                is_canceled=lambda: False,
            )


def test_exec_script_rejects_working_directory_escaping_workspace(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        with pytest.raises(ValueError, match="Working directory path escapes"):
            we.exec_script(
                ScriptStep(
                    script_rel_path="sub/run.sh",
                    working_dir_rel="../escape",
                ),
                log=lambda *_: None,
                is_canceled=lambda: False,
            )


# ================================================
# put_file
# ================================================


def test_put_file_flat_path_uses_single_exec(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.put_file("script.sh", "echo hi")

    # create/cp/start → one exec (cat >); no mkdir needed for flat path
    assert fake.subcommands() == ["create", "cp", "start", "exec", "rm"]


def test_put_file_nested_path_creates_parent_directory(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        we.put_file(".workspace/script.sh", "echo hi")

    exec_calls = [c for c in fake.calls if c[1] == "exec"]
    assert len(exec_calls) == 2
    assert "mkdir" in exec_calls[0]
    assert "cat" in exec_calls[1][-1]


def test_put_file_raises_on_exec_failure(workspace, monkeypatch):
    class CatFailDocker(FakeDocker):
        def run(self, command, capture_output=False, text=False, input=None):
            self.calls.append(list(command))
            # Fail the cat > command (input is provided for cat calls)
            if command[1] == "exec" and input is not None:
                return subprocess.CompletedProcess(command, 1, "", "write error")
            return subprocess.CompletedProcess(command, 0, "", "")

    fake = CatFailDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        with pytest.raises(RuntimeError, match="put_file failed"):
            we.put_file("script.sh", "echo hi")


def test_put_file_rejects_path_escaping_workspace(workspace, monkeypatch):
    fake = FakeDocker()
    _install(monkeypatch, fake)

    with _we(workspace) as we:
        with pytest.raises(ValueError, match="File path escapes workspace"):
            we.put_file("../escape.sh", "echo hi")


def test_run_workspace_script_returns_canceled_when_provisioning_is_canceled(tmp_path, monkeypatch):
    class _CancelOnEnter:
        def __enter__(self):
            raise ProvisioningCanceledError("Run canceled during provisioning")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    monkeypatch.setattr(manager_mod, "acquire", lambda *args, **kwargs: _CancelOnEnter())

    outcome = manager_mod.run_workspace_script(
        workspace=tmp_path,
        script_rel_path="run.sh",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: True,
    )

    assert outcome.status == "canceled"
    assert outcome.exit_code is None


# ================================================
# Machine dispatch gating
# ================================================


def test_localmachine_rejects_apptainer_container_engine(workspace):
    # DockerWorkingEnvironment speaks Docker-CLI verbs Apptainer does not support;
    # the container branch must refuse apptainer rather than emit broken commands.
    from repo2ree_core.working_environment.machine import LocalMachine

    spec = WorkingEnvironmentSpec(
        workspace_path=workspace,
        run_id="test-run",
        log=lambda *_: None,
        engine="apptainer",
    )
    with pytest.raises(NotImplementedError, match="Apptainer"):
        LocalMachine().create_working_environment(spec, kind="container")
