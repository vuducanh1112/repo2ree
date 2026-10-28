import shlex
from collections.abc import Sequence
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import LOCAL, MachineConfig, load_machines
from repo2ree_testbed.runs import machine as machine_mod
from repo2ree_testbed.runs.machine import (
    INTERRUPTED,
    RECEIPT,
    RUN_LINE,
    SSH_FAILED,
    SSH_OPTIONS,
    Machine,
    gate,
    run_recipe,
)

REVISION = "0123456789abcdef0123456789abcdef01234567"
VM = MachineConfig(host="vm")
COMPOSE = "docker compose --project-name repo2ree-dev -f docker-compose.dev.yml -f docker/dev/machine.compose.yml"
GATE = f"{REVISION} just assurance-gate 4"
SYSTEM = f"{REVISION} just test-e2e-system"
RUN = "/repo2ree/test-artifacts/e2e/e2e-system-20261027-120000"

# What tells the calls apart: asking for the job, showing it, and reading its results.
STATE = "test -f test-artifacts/machine-job/command"
SHOW = "tail -n +1 -f"
REPORT = "cat test-artifacts/machine-job/exit"


class FakeRunner:
    """A machine whose job is in ``states`` in turn (then ``fetched``), whose job ended with
    ``code`` and reported ``runs``, and whose calls exit as ``codes`` says by a part of what they run."""

    def __init__(
        self,
        *states: tuple[str, str],
        code: int | None = 0,
        runs: Sequence[str] = (RUN,),
        codes: dict[str, int | BaseException] | None = None,
    ) -> None:
        self.states = list(states)
        self.code = code
        self.runs = list(runs)
        self.codes = codes or {}
        self.calls: list[list[str]] = []
        self.piped: list[tuple[list[str], list[str]]] = []
        self.streamed: list[list[str]] = []

    def call(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        for part, code in self.codes.items():
            if part in argv[-1]:
                if isinstance(code, BaseException):
                    raise code
                return code
        return 0

    def capture(self, argv: Sequence[str]) -> tuple[int, str]:
        self.calls.append(list(argv))
        if STATE in argv[-1]:
            if self.codes.get(STATE) == SSH_FAILED:
                return SSH_FAILED, ""
            state, command = self.states.pop(0) if self.states else ("fetched", "")
            return 0, f"{state}\n{command}\n"
        assert REPORT in argv[-1]
        exit_line = "" if self.code is None else str(self.code)
        return 0, "\n".join([exit_line, *(f"{RUN_LINE}{run}" for run in self.runs)]) + "\n"

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        self.streamed.append(list(argv))
        return self.code or 0, [f"{RUN_LINE}{run}" for run in self.runs]

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        self.piped.append((list(producer), list(consumer)))
        return 0

    def ran(self, part: str) -> list[str]:
        """What the calls containing ``part`` ran on the host."""
        return [_on_host(call) for call in self.calls if call[0] == "ssh" and part in call[-1]]


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


def _pushed(runner: FakeRunner) -> bool:
    return any("push" in call for call in runner.calls)


def _started(runner: FakeRunner) -> bool:
    return bool(runner.ran("exec -d"))


def test_this_checkout_is_always_a_machine_and_the_file_adds_machines(tmp_path: Path) -> None:
    assert set(load_machines(tmp_path / "absent.toml")) == {LOCAL}
    listed = tmp_path / "machines.toml"
    listed.write_text('[machines.vm]\nhost = "vm"\njobs = 6\n')
    machines = load_machines(listed)
    assert machines[LOCAL].host is None
    assert machines["vm"] == MachineConfig(host="vm", jobs=6)
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


def test_a_remote_gate_runs_detached_in_the_dev_container_of_a_clone_and_brings_its_results_back() -> None:
    runner = FakeRunner(("none", ""), ("ended", GATE))

    assert gate(Machine("vm", VM, runner), None) == 0

    # A plain clone in the SSH user's home, which HEAD is pushed to by the host's Git.
    assert runner.ran("git init") == ["test -d repo2ree/.git || git init -q repo2ree"]
    ssh = shlex.join(["ssh", *SSH_OPTIONS])
    push = [
        "git",
        "-c",
        f"core.sshCommand={ssh}",
        "push",
        "-q",
        "--force",
        "vm:repo2ree",
        f"{REVISION}:refs/testbed/head",
    ]
    assert push in runner.calls
    assert runner.ran("checkout") == [f"cd repo2ree && git checkout -q --detach --force {REVISION} && git clean -fdq"]
    # The dev container comes up from the clone as it does here, once its user is set up.
    assert runner.ran(" up -d") == [f"cd repo2ree && {COMPOSE} up -d --build --quiet-pull --wait"]
    # The job runs detached in it, in the clone's .envrc, its log and exit code in the clone.
    [start] = runner.ran("exec -d")
    assert f"printf '%s\\n' {shlex.quote(GATE)} > test-artifacts/machine-job/command" in start
    body = (
        "direnv exec . just assurance-gate 4 > test-artifacts/machine-job/log 2>&1;"
        " echo $? > test-artifacts/machine-job/exit"
    )
    assert f"{COMPOSE} exec -d --user nixuser dev bash -lc {shlex.quote(body)}" in start
    # Shown until it ends: its exit code is written, or its process is gone.
    [show] = runner.ran(SHOW)
    assert show.startswith("cd repo2ree || exit 1; tail -n +1 -f test-artifacts/machine-job/log & shown=$!")
    assert "while ! test -f test-artifacts/machine-job/exit && " in show
    # Its runs and the receipt come straight from the clone on the host, and the job is then fetched.
    (run_fetch, run_unpack), (receipt_fetch, _) = runner.piped
    assert _on_host(run_fetch) == (
        "tar -cf - --exclude=*.tar --exclude=*.tar.gz --exclude=*.tgz --exclude=*/artifacts/archives"
        " -C repo2ree/test-artifacts/e2e e2e-system-20261027-120000"
    )
    assert run_unpack == ["tar", "-xf", "-", "-C", str(ROOT / "test-artifacts/e2e")]
    assert _on_host(receipt_fetch) == f"tar -cf - -C repo2ree {RECEIPT}"
    assert runner.ran("touch") == ["cd repo2ree && touch test-artifacts/machine-job/fetched"]
    # The connection gives up within a minute, and knows the machine only by the checkout's known hosts.
    assert "ConnectTimeout=20" in SSH_OPTIONS
    assert f"UserKnownHostsFile={ROOT}/.config/known_hosts ~/.ssh/known_hosts" in SSH_OPTIONS
    assert "StrictHostKeyChecking=yes" in SSH_OPTIONS


def test_a_failed_gate_brings_back_its_runs_but_not_a_receipt() -> None:
    runner = FakeRunner(("none", ""), ("ended", GATE), code=1)
    assert gate(Machine("vm", MachineConfig(host="vm", fetch="full"), runner), None) == 1
    [(run_fetch, _)] = runner.piped
    assert "--exclude" not in run_fetch[-1]


def test_a_tier_brings_back_its_runs_and_no_receipt_even_when_it_passed() -> None:
    runner = FakeRunner(("fetched", GATE), ("ended", SYSTEM))
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0
    assert len(runner.piped) == 1


def test_the_local_machine_runs_here_and_moves_nothing() -> None:
    runner = FakeRunner(runs=[f"{ROOT}/test-artifacts/e2e/e2e-system-20261027-120000"])
    machine = Machine(LOCAL, MachineConfig(shell=()), runner)

    assert gate(machine, None) == 0
    assert run_recipe(machine, ["test-e2e-system"]) == 0

    assert runner.calls == []
    assert runner.piped == []
    assert runner.streamed == [["just", "assurance-gate", "4"], ["just", "test-e2e-system"]]


def test_a_running_job_is_shown_and_brought_back_instead_of_starting_again() -> None:
    runner = FakeRunner(("running", GATE), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert not _pushed(runner)
    assert not _started(runner)
    assert runner.ran(SHOW)
    assert len(runner.piped) == 2


def test_another_running_job_is_shown_and_brought_back_but_does_not_start_this_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = FakeRunner(("running", SYSTEM), ("ended", SYSTEM))
    assert gate(Machine("vm", VM, runner), None) == 1
    assert "run yours again" in capsys.readouterr().out
    assert not _pushed(runner)
    assert len(runner.piped) == 1


def test_an_ended_job_is_brought_back_and_then_done_if_it_was_this_one() -> None:
    runner = FakeRunner(("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert not _pushed(runner)
    assert not runner.ran(SHOW)
    assert len(runner.piped) == 2


def test_an_ended_job_of_another_command_is_brought_back_before_this_one_starts() -> None:
    runner = FakeRunner(("ended", SYSTEM), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert _pushed(runner)
    assert _started(runner)
    # The tier's run, then the gate's run and receipt.
    assert len(runner.piped) == 3


def test_a_dead_job_gives_way_to_a_new_one(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("dead", SYSTEM), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert "died on vm without an exit code" in capsys.readouterr().out
    assert _started(runner)


def test_a_job_that_dies_while_shown_ends_the_run_as_failed(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("none", ""), ("dead", GATE), code=None)
    assert gate(Machine("vm", VM, runner), None) == 1
    assert "died on vm without an exit code" in capsys.readouterr().out
    # Its runs come back, never a receipt.
    assert len(runner.piped) == 1


@pytest.mark.parametrize(
    ("stop", "says"), [(KeyboardInterrupt(), "stopped showing"), (SSH_FAILED, "lost the connection")]
)
def test_ctrl_c_or_a_lost_connection_only_stops_the_showing(
    stop: int | BaseException, says: str, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner(("none", ""), codes={SHOW: stop})
    assert gate(Machine("vm", VM, runner), None) == INTERRUPTED
    out = capsys.readouterr().out
    assert says in out
    assert "the job goes on" in out
    assert "just cancel-e2e-on vm" in out
    assert runner.piped == []
    assert not runner.ran("touch")


def test_an_unreachable_machine_is_refused_with_how_to_reach_it() -> None:
    runner = FakeRunner(codes={STATE: SSH_FAILED})
    with pytest.raises(SystemExit, match=r"could not reach vm as vm over SSH.*tools/ssh/setup-vm.sh"):
        gate(Machine("vm", VM, runner), None)
    assert not _pushed(runner)


def test_a_machine_runs_only_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(machine_mod, "capture", lambda argv: " M core/x.py")
    with pytest.raises(SystemExit, match="commit first"):
        gate(Machine("vm", VM, FakeRunner()), None)


def test_cancelling_restarts_the_container_and_cleans_up_what_the_job_left() -> None:
    runner = FakeRunner(("running", GATE))
    Machine("vm", VM, runner).cancel()
    [cancel] = runner.ran("restart")
    assert cancel.startswith(f"cd repo2ree && {COMPOSE} restart dev && {COMPOSE} up -d --wait")
    assert "test -f test-artifacts/machine-job/exit || echo 130 > test-artifacts/machine-job/exit" in cancel
    assert "just stack-clean; just clean-workbenches" in cancel


def test_cancelling_without_a_running_job_changes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("ended", GATE))
    Machine("vm", VM, runner).cancel()
    assert "running no job" in capsys.readouterr().out
    assert not runner.ran("restart")


def test_removing_takes_the_container_down_and_deletes_the_clone() -> None:
    runner = FakeRunner(("fetched", GATE))
    Machine("vm", VM, runner).remove()
    [removal] = runner.ran("down")
    assert "just stack-clean; just clean-workbenches 1" in removal
    assert f"{COMPOSE} down --volumes --remove-orphans --rmi local || exit 1; cd && rm -rf repo2ree" in removal


def test_removing_refuses_while_a_job_runs() -> None:
    runner = FakeRunner(("running", GATE))
    with pytest.raises(SystemExit, match="vm is running a job; let it end, or: just cancel-e2e-on vm"):
        Machine("vm", VM, runner).remove()
    assert not runner.ran("down")
