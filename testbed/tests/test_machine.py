import shlex
from collections.abc import Sequence
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import LOCAL, MachineConfig, load_machines
from repo2ree_testbed.runs import machine as machine_mod
from repo2ree_testbed.runs.machine import (
    INTERRUPTED,
    JOB_EXITED,
    JOB_LOST,
    LOST_JOB,
    OTHER_RUNNING,
    OTHER_UNFETCHED,
    RECEIPT,
    RECONNECT_SECONDS,
    RUN_LINE,
    SSH_FAILED,
    SSH_OPTIONS,
    THIS_JOB,
    Machine,
    gate,
    run_recipe,
)

REVISION = "0123456789abcdef0123456789abcdef01234567"
VM = MachineConfig(host="vm")
COMPOSE = "docker compose --project-name repo2ree-dev -f docker-compose.dev.yml -f docker/dev/machine.compose.yml"


# What tells the calls apart: whether the dev container runs, looking for a job, starting, and cancelling one.
UP = "ps --status running"
STATE = "/fetched || exit 0"
START = "nohup bash -c"
CANCEL = "kill -INT"


class FakeRunner:
    """A machine whose calls exit as ``codes`` says, by a substring of what they run, and whose
    follows answer with ``follows`` in turn: then with ``printed`` and a job that exits ``code``."""

    def __init__(
        self,
        *,
        code: int = 0,
        printed: Sequence[str] = (),
        codes: dict[str, int] | None = None,
        follows: Sequence[tuple[int, list[str]] | BaseException] = (),
    ) -> None:
        self.code = code
        self.printed = list(printed)
        self.codes = codes or {}
        self.follows = list(follows)
        self.calls: list[list[str]] = []
        self.streamed: list[list[str]] = []
        self.piped: list[tuple[list[str], list[str]]] = []

    def call(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return next((code for part, code in self.codes.items() if part in argv[-1]), 0)

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        self.streamed.append(list(argv))
        if argv[0] != "ssh":
            return self.code, self.printed
        if self.follows:
            follow = self.follows.pop(0)
            if isinstance(follow, BaseException):
                raise follow
            return follow
        return 0, [*self.printed, f"{JOB_EXITED}{self.code}"]

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        self.piped.append((list(producer), list(consumer)))
        return 0


def _git(argv: Sequence[str]) -> str:
    """A committed checkout."""
    match list(argv):
        case ["git", "status", "--porcelain"]:
            return ""
        case ["git", "rev-parse", "HEAD"]:
            return REVISION
    raise AssertionError(argv)


@pytest.fixture(autouse=True)
def committed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(machine_mod, "capture", _git)


def _on_host(call: Sequence[str]) -> str:
    """What an ssh call runs on the host, once its login shell has unquoted it."""
    assert call[:-1] == ["ssh", *SSH_OPTIONS, "vm"]
    return shlex.split(call[-1])[-1]


def _in_clone(call: Sequence[str]) -> str:
    """What an ssh call runs in the host's clone."""
    host = _on_host(call)
    assert host.startswith("cd repo2ree && ")
    return host.removeprefix("cd repo2ree && ")


def _in_container(call: Sequence[str]) -> str:
    """What an ssh call runs in the dev container, as its user, once both login shells have unquoted it."""
    words = shlex.split(_in_clone(call))
    assert words[:-1] == [*shlex.split(COMPOSE), "exec", "-T", "--user", "nixuser", "dev", "bash", "-lc"]
    return words[-1]


def test_this_checkout_is_always_a_machine_and_the_file_adds_machines(tmp_path: Path) -> None:
    assert set(load_machines(tmp_path / "absent.toml")) == {LOCAL}
    listed = tmp_path / "machines.toml"
    listed.write_text('[machines.vm]\nhost = "vm"\njobs = 6\n')
    machines = load_machines(listed)
    assert machines[LOCAL].host is None
    assert machines["vm"] == MachineConfig(host="vm", jobs=6)
    # Every other machine runs in its dev container, the Compose project repo2ree-dev.
    assert machines["vm"].container == "repo2ree-dev"


@pytest.mark.parametrize(
    "text",
    ['[machines.local]\nhost = "vm"\n', "[machines.vm]\njobs = 2\n", '[machines.vm]\nhost = "vm"\ncolour = "red"\n'],
)
def test_a_machines_file_cannot_redefine_this_checkout_omit_a_host_or_add_settings(tmp_path: Path, text: str) -> None:
    listed = tmp_path / "machines.toml"
    listed.write_text(text)
    with pytest.raises(SystemExit):
        load_machines(listed)


def test_a_remote_gate_runs_in_the_dev_container_of_a_clone_and_brings_back_runs_and_receipt() -> None:
    remote_run = "/repo2ree/test-artifacts/e2e/e2e-system-20261027-120000"
    runner = FakeRunner(printed=["building", f"{RUN_LINE}{remote_run}", ">> passed"])

    assert gate(Machine("vm", MachineConfig(host="vm", jobs=6), runner), None) == 0

    up_check, state, init, push, checkout, up, start, done = runner.calls
    assert f'cd repo2ree 2>/dev/null && test -n "$({COMPOSE} {UP} --quiet dev 2>/dev/null)"' == _on_host(up_check)
    assert f"= {shlex.quote(REVISION + ' just assurance-gate 6')} && this=1" in _in_container(state)
    # A plain clone in the SSH user's home, which HEAD is pushed to by the host's Git.
    assert _on_host(init) == "test -d repo2ree/.git || git init -q repo2ree"
    assert push == [
        "git",
        "-c",
        f"core.sshCommand={shlex.join(['ssh', *SSH_OPTIONS])}",
        "push",
        "-q",
        "--force",
        "vm:repo2ree",
        f"{REVISION}:refs/testbed/head",
    ]
    # The push reaches the machine as every other call does: by the checkout's known hosts, never asking.
    assert f"UserKnownHostsFile={ROOT}/.config/known_hosts ~/.ssh/known_hosts" in SSH_OPTIONS
    assert "StrictHostKeyChecking=yes" in SSH_OPTIONS
    assert _in_clone(checkout) == f"git checkout -q --detach --force {REVISION} && git clean -fdq"
    # The dev container comes up from the clone as it does here, built from the Nix dev image.
    # Once it is healthy: its user set up, the Docker group among its groups, which a run keeps from its start.
    assert _in_clone(up) == f"{COMPOSE} up -d --build --quiet-pull --wait"
    # The gate runs detached, in its own process group, logging to the clone's test-artifacts.
    starting = _in_container(start)
    assert "set -m\nnohup bash -c" in starting
    # In the checkout's own .envrc, which the image trusts at /repo2ree: the dev shell and its venv.
    assert "nohup bash -c 'direnv exec . just assurance-gate 6 >" in starting
    assert "/repo2ree/test-artifacts/machine-job/log 2>&1; echo $? >" in starting
    [follow] = runner.streamed
    assert "tail -n +1 -f" in _in_container(follow)
    assert "touch /repo2ree/test-artifacts/machine-job/fetched" in _in_container(done)

    # Runs and the receipt come straight from the clone on the host.
    (run_fetch, run_unpack), (receipt_fetch, _) = runner.piped
    assert _on_host(run_fetch) == (
        "tar -cf - --exclude=*.tar --exclude=*.tar.gz --exclude=*.tgz --exclude=*/artifacts/archives"
        " -C repo2ree/test-artifacts/e2e e2e-system-20261027-120000"
    )
    assert run_unpack == ["tar", "-xf", "-", "-C", str(ROOT / "test-artifacts/e2e")]
    assert _on_host(receipt_fetch) == f"tar -cf - -C repo2ree {RECEIPT}"


def test_a_failed_remote_gate_brings_back_its_runs_but_not_a_receipt() -> None:
    remote_run = "/repo2ree/test-artifacts/e2e/e2e-gui-instant-20261027-120000"
    runner = FakeRunner(code=1, printed=[f"{RUN_LINE}{remote_run}"])

    assert gate(Machine("vm", MachineConfig(host="vm", fetch="full"), runner), 2) == 1

    [(run_fetch, _)] = runner.piped
    assert "--exclude" not in run_fetch[-1]
    assert "just assurance-gate 2" in _in_container(runner.calls[6])


def test_the_local_machine_runs_here_and_moves_nothing() -> None:
    runner = FakeRunner(printed=[f"{RUN_LINE}{ROOT}/test-artifacts/e2e/e2e-system-20261027-120000"])
    machine = Machine(LOCAL, MachineConfig(shell=()), runner)

    assert gate(machine, None) == 0
    assert run_recipe(machine, ["test-e2e-system"]) == 0

    assert runner.calls == []
    assert runner.piped == []
    assert runner.streamed == [["just", "assurance-gate", "4"], ["just", "test-e2e-system"]]
    with pytest.raises(SystemExit, match="nothing to remove"):
        machine.remove()


def test_a_machine_without_a_running_dev_container_has_no_job_and_gets_the_container_up() -> None:
    runner = FakeRunner(codes={UP: 1})
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0
    assert not any(STATE in call[-1] for call in runner.calls)
    assert any(
        _on_host(call).endswith("up -d --build --quiet-pull --wait") for call in runner.calls if call[0] == "ssh"
    )


def test_an_unreachable_machine_is_refused_with_how_to_reach_it() -> None:
    runner = FakeRunner(codes={UP: SSH_FAILED})
    with pytest.raises(SystemExit, match=r"could not reach vm as vm over SSH.*tools/ssh/setup-vm.sh"):
        run_recipe(Machine("vm", VM, runner), ["test-e2e-system"])
    assert len(runner.calls) == 1


def test_removing_cleans_up_inside_the_container_then_takes_it_down_and_deletes_the_clone() -> None:
    runner = FakeRunner()

    Machine("vm", VM, runner).remove()

    _up_check, _state, cleanup, removal = runner.calls
    assert "just stack-clean; just clean-workbenches 1" in _in_container(cleanup)
    assert _on_host(removal) == (
        f"if test -d repo2ree; then (cd repo2ree && {COMPOSE} down --volumes --remove-orphans --rmi local)"
        " || exit 1; rm -rf repo2ree; fi"
    )


def test_removing_a_stopped_container_skips_the_cleanup_inside_it() -> None:
    runner = FakeRunner(codes={UP: 1})
    Machine("vm", VM, runner).remove()
    _up_check, removal = runner.calls
    assert "down --volumes" in _on_host(removal)


def test_a_machine_runs_only_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(machine_mod, "capture", lambda argv: " M core/x.py")
    with pytest.raises(SystemExit, match="commit first"):
        gate(Machine("vm", VM, FakeRunner()), None)


def _started(runner: FakeRunner) -> bool:
    return any(START in call[-1] for call in runner.calls)


def _pushed(runner: FakeRunner) -> bool:
    return any(call[:4:3] == ["git", "push"] for call in runner.calls)


def test_a_dropped_connection_reconnects_and_follows_the_log_from_where_it_left_off() -> None:
    remote_run = "/repo2ree/test-artifacts/e2e/e2e-system-20261027-120000"
    runner = FakeRunner(
        follows=[
            (SSH_FAILED, ["one", "two"]),
            (SSH_FAILED, []),
            (0, ["three", f"{RUN_LINE}{remote_run}", f"{JOB_EXITED}1"]),
        ]
    )
    slept: list[float] = []

    assert run_recipe(Machine("vm", VM, runner, sleep=slept.append), ["test-e2e-system"]) == 1

    assert _started(runner)
    assert "tail -n +1 -f" in _in_container(runner.streamed[0])
    assert "tail -n +3 -f" in _in_container(runner.streamed[1])
    assert "tail -n +3 -f" in _in_container(runner.streamed[2])
    # The wait grows while the machine stays unreachable.
    assert slept == [5, 10]
    [(run_fetch, _)] = runner.piped
    assert "e2e-system-20261027-120000" in _on_host(run_fetch)


def test_a_machine_unreachable_for_long_leaves_the_job_to_the_same_command_again() -> None:
    runner = FakeRunner(follows=[(SSH_FAILED, [])] * 100)
    with pytest.raises(SystemExit, match="the job keeps running there: rerun the same command"):
        run_recipe(Machine("vm", VM, runner, sleep=lambda _: None), ["test-e2e-system"])
    assert 5 < len(runner.streamed) < 100
    assert RECONNECT_SECONDS == 30 * 60


def test_the_output_lost_otherwise_is_not_waited_for() -> None:
    runner = FakeRunner(follows=[(1, ["one"])])
    with pytest.raises(SystemExit, match=r"lost the job's output on vm \(exit 1\)"):
        run_recipe(Machine("vm", VM, runner, sleep=lambda _: pytest.fail("slept")), ["test-e2e-system"])


def test_the_same_command_again_picks_its_job_back_up_without_shipping_or_starting() -> None:
    runner = FakeRunner(codes={STATE: THIS_JOB}, printed=["three"])

    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0

    assert not _pushed(runner)
    assert not _started(runner)
    # From the log's first line, since nothing of it was shown here yet.
    assert "tail -n +1 -f" in _in_container(runner.streamed[0])


def test_another_running_job_is_refused_before_anything_is_shipped() -> None:
    runner = FakeRunner(codes={STATE: OTHER_RUNNING})
    with pytest.raises(SystemExit, match=r"vm is running the job above.*just cancel-e2e-on vm"):
        run_recipe(Machine("vm", VM, runner), ["test-e2e-system"])
    assert not _pushed(runner)
    assert runner.streamed == []


@pytest.mark.parametrize(
    ("state", "note"), [(OTHER_UNFETCHED, "never brought back"), (LOST_JOB, "without an exit code")]
)
def test_an_ended_or_lost_job_gives_way_to_a_new_one(state: int, note: str, capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(codes={STATE: state})
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0
    assert note in capsys.readouterr().out
    assert _pushed(runner)
    assert _started(runner)


def test_a_job_that_died_without_an_exit_code_ends_the_run() -> None:
    runner = FakeRunner(follows=[(0, ["one", JOB_LOST])])
    with pytest.raises(SystemExit, match="died without an exit code"):
        run_recipe(Machine("vm", VM, runner), ["test-e2e-system"])


def test_ctrl_c_on_a_run_cancels_its_job() -> None:
    runner = FakeRunner(follows=[KeyboardInterrupt()])

    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == INTERRUPTED

    [cancel] = [call for call in runner.calls if CANCEL in call[-1]]
    cancelling = _in_container(cancel)
    # The whole process group, as Ctrl-C would, then whatever outlives two minutes.
    assert 'kill -INT -- "-$pid"' in cancelling
    assert 'kill -KILL -- "-$pid"' in cancelling
    assert runner.piped == []


def test_removing_refuses_while_a_job_runs() -> None:
    runner = FakeRunner(codes={STATE: OTHER_RUNNING})
    with pytest.raises(SystemExit, match="vm is running the job above, so this will not remove its container"):
        Machine("vm", VM, runner).remove()
    assert not any("down --volumes" in call[-1] for call in runner.calls)
