import shlex
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import LOCAL, MachineConfig, load_machines
from repo2ree_testbed.runs import machine as machine_mod
from repo2ree_testbed.runs.machine import (
    INTERRUPTED,
    SSH_FAILED,
    SSH_OPTIONS,
    WIP_IDENTITY,
    Machine,
    gate,
    run_recipe,
)

REVISION = "0123456789abcdef0123456789abcdef01234567"
VM = MachineConfig(host="vm")
COMPOSE = "docker compose --project-name repo2ree-dev -f docker-compose.dev.yml -f docker/dev/machine.compose.yml"
GATE = f"{REVISION} just assurance-gate 4"
SYSTEM = f"{REVISION} just test-e2e-system"
# What a gate writes: a run, and the receipt for the tree.
WRITTEN = (
    "test-artifacts/e2e/e2e-system-20261027-120000/run.json",
    "test-artifacts/e2e/e2e-system-20261027-120000/tests/a/verdict.json",
    ".receipts/assurance-gate.json",
)

# What tells the calls apart: asking for the job, showing it, its exit code, and what it wrote.
STATE = "test -f test-artifacts/machine-job/command"
SHOW = "tail -n +1 -f"
REPORT = "cat test-artifacts/machine-job/exit"
LIST = "find test-artifacts .receipts"


class FakeRunner:
    """A machine whose job is in ``states`` in turn (then ``fetched``), whose job ended with
    ``code`` having ``written`` those files, and whose calls exit as ``codes`` says by a part of what they run."""

    def __init__(
        self,
        *states: tuple[str, str],
        code: int | None = 0,
        written: Sequence[str] = WRITTEN,
        codes: dict[str, int | BaseException] | None = None,
    ) -> None:
        self.states = list(states)
        self.code = code
        self.written = list(written)
        self.codes = codes or {}
        self.calls: list[list[str]] = []
        self.piped: list[tuple[list[str], list[str]]] = []

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
        if REPORT in argv[-1]:
            return 0, ("" if self.code is None else str(self.code)) + "\n"
        assert LIST in argv[-1]
        return 0, "".join(f"{path}\n" for path in self.written)

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
    # The job runs detached in it, in the clone's .envrc and knowing the machine's name, its log
    # and exit code in the clone.
    [start] = runner.ran("exec -d")
    assert f"printf '%s\\n' {shlex.quote(GATE)} > test-artifacts/machine-job/command" in start
    body = (
        "REPO2REE_MACHINE=vm direnv exec . just assurance-gate 4 > test-artifacts/machine-job/log 2>&1;"
        " echo $? > test-artifacts/machine-job/exit"
    )
    assert f"{COMPOSE} exec -d --user nixuser dev bash -lc {shlex.quote(body)}" in start
    # Shown until it ends: its exit code is written, or its process is gone.
    [show] = runner.ran(SHOW)
    assert show.startswith("cd repo2ree || exit 1; tail -n +1 -f test-artifacts/machine-job/log & shown=$!")
    assert "while ! test -f test-artifacts/machine-job/exit && " in show
    # What it wrote since it started, its run, the receipt, and its timings alike, comes straight from the clone on the
    # host into this checkout, leaving runtime tarballs and archives there; then the job is fetched.
    [(fetch, unpack)] = runner.piped
    assert _on_host(fetch) == (
        "cd repo2ree && { find test-artifacts .receipts logs -type f -cnewer test-artifacts/machine-job/command"
        " ! -path 'test-artifacts/machine-job/*' ! -name '*.tar' ! -name '*.tar.gz' ! -name '*.tgz'"
        " ! -path '*/artifacts/archives/*' 2>/dev/null || true; } | tar -cf - -T -"
    )
    assert unpack == ["tar", "-xf", "-", "-C", str(ROOT)]
    assert runner.ran("touch") == ["cd repo2ree && touch test-artifacts/machine-job/fetched"]
    # The connection gives up within a minute, and knows the machine only by the checkout's known hosts.
    assert "ConnectTimeout=20" in SSH_OPTIONS
    assert f"UserKnownHostsFile={ROOT}/.config/known_hosts ~/.ssh/known_hosts" in SSH_OPTIONS
    assert "StrictHostKeyChecking=yes" in SSH_OPTIONS


def test_a_failed_job_still_brings_back_what_it_wrote(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("none", ""), ("ended", GATE), code=1)
    assert gate(Machine("vm", VM, runner), None) == 1
    assert len(runner.piped) == 1
    # Each run once, and each other file as it is.
    out = capsys.readouterr().out
    assert ">> from vm: test-artifacts/e2e/e2e-system-20261027-120000\n>> from vm: .receipts/assurance-gate.json" in out


def test_any_recipe_brings_back_what_it_wrote_and_a_job_that_wrote_nothing_moves_nothing() -> None:
    coverage = ["test-artifacts/python/coverage/data/integration-parts/core/.coverage"]
    runner = FakeRunner(("fetched", GATE), ("ended", SYSTEM), written=coverage)
    assert run_recipe(Machine("vm", VM, runner), ["test-backend-integration"]) == 0
    assert len(runner.piped) == 1

    runner = FakeRunner(("fetched", GATE), ("ended", SYSTEM), written=[])
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0
    assert runner.piped == []
    assert runner.ran("touch")


def test_the_local_machine_runs_here_and_moves_nothing() -> None:
    runner = FakeRunner()
    machine = Machine(LOCAL, MachineConfig(), runner)

    assert gate(machine, None) == 0
    assert run_recipe(machine, ["test-e2e-system"]) == 0

    assert runner.calls == [["just", "assurance-gate", "4"], ["just", "test-e2e-system"]]
    assert runner.piped == []


def test_a_running_job_is_shown_and_brought_back_instead_of_starting_again() -> None:
    runner = FakeRunner(("running", GATE), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert not _pushed(runner)
    assert not _started(runner)
    assert runner.ran(SHOW)
    assert len(runner.piped) == 1


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
    assert len(runner.piped) == 1


def test_an_ended_job_of_another_command_is_brought_back_before_this_one_starts() -> None:
    runner = FakeRunner(("ended", SYSTEM), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert _pushed(runner)
    assert _started(runner)
    # What the tier wrote, then what the gate wrote.
    assert len(runner.piped) == 2


def test_a_dead_job_gives_way_to_a_new_one(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("dead", SYSTEM), ("ended", GATE))
    assert gate(Machine("vm", VM, runner), None) == 0
    assert "died on vm without an exit code" in capsys.readouterr().out
    assert _started(runner)


def test_a_job_that_dies_while_shown_ends_the_run_as_failed(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("none", ""), ("dead", GATE), code=None)
    assert gate(Machine("vm", VM, runner), None) == 1
    assert "died on vm without an exit code" in capsys.readouterr().out
    # What it wrote before it died comes back.
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
    assert "just machine cancel vm" in out
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


WIP = "fedcba9876543210fedcba9876543210fedcba98"


class WorkingTree:
    """A checkout with uncommitted changes: what each git call was given, and its answer."""

    def __init__(self, *, email: str = "") -> None:
        self.email = email
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None, check: bool = False) -> str:
        self.calls.append((list(argv), dict(env or {})))
        match list(argv):
            case ["git", "status", "--porcelain"]:
                return " M core/x.py\n?? notes.txt"
            case ["git", "write-tree"]:
                return "tree-of-the-working-tree"
            case ["git", "config", "user.email"]:
                return self.email
            case ["git", "commit-tree", *_]:
                return WIP
        return ""

    def env_of(self, *argv: str) -> dict[str, str]:
        return next(env for call, env in self.calls if call == list(argv))


def _shipped(runner: FakeRunner) -> list[str]:
    return [call[-1].removesuffix(":refs/testbed/head") for call in runner.calls if "push" in call]


def test_a_working_tree_runs_as_a_commit_beside_the_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = WorkingTree()
    monkeypatch.setattr(machine_mod, "capture", tree)
    runner = FakeRunner(("fetched", ""), ("ended", f"{WIP} just test-e2e-system"))

    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"], wip=True) == 0

    assert _shipped(runner) == [WIP]
    # Staged into an index of its own, so neither the branch nor the developer's index moves.
    index = tree.env_of("git", "add", "-A")["GIT_INDEX_FILE"]
    assert index == tree.env_of("git", "read-tree", "HEAD")["GIT_INDEX_FILE"]
    assert index == tree.env_of("git", "write-tree")["GIT_INDEX_FILE"]
    assert not index.startswith(str(ROOT))
    commit = next(call for call, _env in tree.calls if call[:2] == ["git", "commit-tree"])
    assert commit[2:5] == ["tree-of-the-working-tree", "-p", "HEAD"]
    assert not any(call[:2] in (["git", "commit"], ["git", "stash"]) for call, _env in tree.calls)


def test_a_working_tree_commit_is_authored_by_the_developer_or_else_the_testbed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def author(email: str) -> dict[str, str]:
        tree = WorkingTree(email=email)
        monkeypatch.setattr(machine_mod, "capture", tree)
        run_recipe(Machine("vm", VM, FakeRunner(("fetched", ""))), ["test-e2e-system"], wip=True)
        return next(env for call, env in tree.calls if call[:2] == ["git", "commit-tree"])

    assert WIP_IDENTITY.items() <= author("").items()
    assert author("someone@example.org").get("GIT_AUTHOR_EMAIL") != WIP_IDENTITY["GIT_AUTHOR_EMAIL"]


def test_a_clean_working_tree_runs_as_head() -> None:
    runner = FakeRunner(("fetched", ""), ("ended", SYSTEM))
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"], wip=True) == 0
    assert _shipped(runner) == [REVISION]


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
    with pytest.raises(SystemExit, match="vm is running a job; let it end, or: just machine cancel vm"):
        Machine("vm", VM, runner).remove()
    assert not runner.ran("down")
