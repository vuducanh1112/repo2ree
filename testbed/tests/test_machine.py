import os
import shlex
import subprocess
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
    Workspace,
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

# What tells the calls apart: asking for the jobs, claiming a workspace, showing a job, its exit code, and what
# it wrote.
STATES = "|| exit 0\nstates"
CLAIM = "git init -q repo2ree"
SHOW = "tail -n +1 -f"
REPORT = "cat test-artifacts/machine-job/exit"
LIST = "find test-artifacts .receipts"
FURTHER = ".machine-workspaces/1"

type Listing = tuple[str, str] | list[tuple[str, str, str]]


class FakeRunner:
    """A machine whose jobs are listed as ``states`` says in turn (then every one ``fetched``): a ``(state, command)``
    of the clone's job, or ``(workspace, state, command)`` for each workspace. A run claims ``claim``. Its job ended
    with ``code`` having ``written`` those files, and its calls exit as ``codes`` says by a part of what they run."""

    def __init__(
        self,
        *states: Listing,
        code: int | None = 0,
        written: Sequence[str] = WRITTEN,
        codes: dict[str, int | BaseException] | None = None,
        archives: Sequence[tuple[int, str]] = (),
        claim: str = ".",
    ) -> None:
        self.archives = list(archives)
        self.states = list(states)
        self.code = code
        self.written = list(written)
        self.codes = codes or {}
        self.claim = claim
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
        if STATES in argv[-1]:
            if self.codes.get(STATES) == SSH_FAILED:
                return SSH_FAILED, ""
            listing = self.states.pop(0) if self.states else ("fetched", "")
            rows = [(".", *listing)] if isinstance(listing, tuple) else listing
            return 0, "".join(f"{workspace}\t{state}\t{command}\n" for workspace, state, command in rows)
        if CLAIM in argv[-1]:
            return 0, f"{self.claim}\n"
        if "stat -c %Y" in argv[-1]:
            return 0, "".join(f"{stamp}\t{path}\n" for stamp, path in self.archives)
        if REPORT in argv[-1]:
            return 0, ("" if self.code is None else str(self.code)) + "\n"
        assert LIST in argv[-1]
        return 0, "".join(f"{path}\n" for path in self.written)

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        self.piped.append((list(producer), list(consumer)))
        if "dist/images" in producer[-1]:
            # What an archive set unpacks to: its platform's directory, under the consumer's -C.
            name = shlex.split(_on_host(producer))[-1]
            (Path(consumer[-1]) / name).mkdir(parents=True)
            (Path(consumer[-1]) / name / "manifest.json").write_text(f"{name}\n")
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

    # A plain clone in the SSH user's home, which HEAD is pushed to by the host's Git; the run claims its first
    # workspace, the clone itself, and records the job there before anything else can take it.
    [claim] = runner.ran(CLAIM)
    assert "test -d repo2ree/.git || git init -q repo2ree" in claim
    assert f"printf '%s\\n' {shlex.quote(GATE)} > \"$dir/test-artifacts/machine-job\"/command" in claim
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
    # The dev container comes up from the clone as it does here, once its user is set up; rebuilt only while no
    # other job is busy.
    [up] = runner.ran("up -d --build")
    assert f"{COMPOSE} up -d --build --quiet-pull --wait" in up
    assert 'if test -n "$(busy .)"' in up
    # The job runs detached in it, in a process group of its own, in the clone's .envrc and knowing the machine's
    # name, its log and exit code in the clone.
    [start] = runner.ran("exec -d")
    body = (
        "echo $$ > /repo2ree/test-artifacts/machine-job/pid;"
        " REPO2REE_MACHINE=vm direnv exec . just assurance-gate 4 > /repo2ree/test-artifacts/machine-job/log 2>&1;"
        " echo $? > /repo2ree/test-artifacts/machine-job/exit"
    )
    assert f"{COMPOSE} exec -d --user nixuser --workdir /repo2ree dev setsid bash -lc {shlex.quote(body)}" in start
    # Shown until it ends: its exit code is written, or its process is gone.
    [show] = runner.ran(SHOW)
    assert "tail -n +1 -f test-artifacts/machine-job/log & shown=$!" in show
    assert "while ! test -f test-artifacts/machine-job/exit && alive /repo2ree; do" in show
    # What it wrote since it started, its run, the receipt, and its timings alike, empty folders too, comes straight
    # from the clone on the host into this checkout, leaving experiment environment tarballs, archives and kept REE
    # histories there; then the job is fetched.
    [(fetch, unpack)] = runner.piped
    assert _on_host(fetch) == (
        "cd repo2ree && { find test-artifacts .receipts logs \\( -type f -o -type d -empty \\)"
        " -cnewer test-artifacts/machine-job/pid"
        " ! -path 'test-artifacts/machine-job/*' ! -name '*.tar' ! -name '*.tar.gz' ! -name '*.tgz'"
        " ! -path '*/artifacts/archives/*' ! -path '*/artifacts/*/ree*.zip' ! -path '*/artifacts/kept-rees/*'"
        " 2>/dev/null || true; }"
        " | tar -cf - -T -"
    )
    assert runner.ran("mkdir test-artifacts/machine-job/fetching") == [
        "cd repo2ree && mkdir test-artifacts/machine-job/fetching 2>/dev/null"
    ]
    assert unpack == ["tar", "-xf", "-", "-C", str(ROOT)]
    assert runner.ran("touch test-artifacts/machine-job/fetched") == [
        "cd repo2ree && touch test-artifacts/machine-job/fetched"
    ]
    # The connection gives up within a minute, and knows the machine only by the checkout's known hosts.
    assert "ConnectTimeout=20" in SSH_OPTIONS
    assert f"UserKnownHostsFile={ROOT}/.config/known_hosts ~/.ssh/known_hosts" in SSH_OPTIONS
    assert "StrictHostKeyChecking=yes" in SSH_OPTIONS


def test_a_run_beside_a_running_job_runs_in_a_further_workspace_and_brings_back_from_it() -> None:
    beside = [(".", "running", SYSTEM)]
    runner = FakeRunner(beside, [*beside, (FURTHER, "ended", GATE)], claim=FURTHER)

    assert gate(Machine("vm", VM, runner), None) == 0

    # The other job is neither shown nor waited for.
    assert not runner.ran("alive /repo2ree;")
    # Its commit goes to a ref of its own in the clone, which the workspace fetches from.
    assert any(call[-1] == f"{REVISION}:refs/testbed/workspace-1" for call in runner.calls if "push" in call)
    assert runner.ran("git fetch") == [
        (
            f"cd repo2ree && cd {FURTHER} && {{ test -d .git || git init -q; }}"
            " && git fetch -q --no-tags ../.. refs/testbed/workspace-1"
            f" && git checkout -q --detach --force {REVISION} && git clean -fdq"
        )
    ]
    [up] = runner.ran("up -d")
    assert f"busy {FURTHER}" in up
    [start] = runner.ran("exec -d")
    assert f"--workdir /repo2ree/{FURTHER} dev setsid bash -lc" in start
    assert f"/repo2ree/{FURTHER}/test-artifacts/machine-job/exit" in start
    assert f": > {FURTHER}/test-artifacts/machine-job/log" in start
    [show] = runner.ran(SHOW)
    assert f"alive /repo2ree/{FURTHER};" in show
    [(fetch, _)] = runner.piped
    assert _on_host(fetch).startswith(f"cd repo2ree/{FURTHER} && {{ find test-artifacts")
    assert runner.ran("touch") == [f"cd repo2ree/{FURTHER} && touch test-artifacts/machine-job/fetched"]


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
    assert runner.ran("touch test-artifacts/machine-job/fetched")


def test_the_local_machine_runs_here_and_moves_nothing() -> None:
    runner = FakeRunner()
    machine = Machine(LOCAL, MachineConfig(), runner)

    assert gate(machine, None) == 0
    assert run_recipe(machine, ["test-e2e-system"]) == 0

    assert runner.calls == [["just", "assurance-gate", "4"], ["just", "test-e2e-system"]]
    assert runner.piped == []


def test_a_running_job_is_shown_and_brought_back_instead_of_starting_again() -> None:
    runner = FakeRunner([(FURTHER, "running", GATE)], [(FURTHER, "ended", GATE)])
    assert gate(Machine("vm", VM, runner), None) == 0
    assert not _pushed(runner)
    assert not _started(runner)
    assert not runner.ran(CLAIM)
    [show] = runner.ran(SHOW)
    assert f"alive /repo2ree/{FURTHER};" in show
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


def test_a_dead_job_is_brought_back_and_gives_way_to_a_new_one(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("dead", SYSTEM), ("ended", GATE), code=None)
    assert gate(Machine("vm", VM, runner), None) == 1
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
    runner = FakeRunner(codes={STATES: SSH_FAILED})
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
            case ["git", "show", "-s", "--format=%cd", "--date=raw", "HEAD"]:
                return "1763424000 +0100"
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


def test_a_working_tree_commit_is_dated_as_head_so_the_same_tree_is_the_same_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = WorkingTree()
    monkeypatch.setattr(machine_mod, "capture", tree)
    run_recipe(Machine("vm", VM, FakeRunner(("fetched", ""))), ["test-e2e-system"], wip=True)
    env = next(env for call, env in tree.calls if call[:2] == ["git", "commit-tree"])
    assert env["GIT_AUTHOR_DATE"] == env["GIT_COMMITTER_DATE"] == "1763424000 +0100"


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


def test_cancelling_stops_the_jobs_process_group_and_cleans_up_what_the_job_left() -> None:
    runner = FakeRunner(("running", GATE))
    Machine("vm", VM, runner).cancel()
    [cancel] = runner.ran("kill -TERM")
    assert "pid=$(cat /repo2ree/test-artifacts/machine-job/pid) && kill -TERM -- -$pid" in cancel
    assert "kill -KILL -- -$pid" in cancel
    assert "restart" not in cancel
    assert "test -f test-artifacts/machine-job/exit || echo 130 > test-artifacts/machine-job/exit" in cancel
    assert "just stack-clean; just clean-workbenches" in cancel


def test_cancelling_one_of_several_jobs_leaves_the_others_and_their_stacks_alone() -> None:
    jobs = [(".", "running", SYSTEM), (FURTHER, "running", GATE)]
    runner = FakeRunner(jobs)
    Machine("vm", VM, runner).cancel("assurance-gate")
    [cancel] = runner.ran("kill -TERM")
    assert f"/repo2ree/{FURTHER}/test-artifacts/machine-job/pid" in cancel
    assert f"echo 130 > {FURTHER}/test-artifacts/machine-job/exit" in cancel
    assert "workbench-cleanup --orphans" in cancel
    assert "clean-workbenches" not in cancel


def test_cancelling_asks_which_when_several_jobs_run() -> None:
    runner = FakeRunner([(".", "running", SYSTEM), (FURTHER, "running", GATE)])
    with pytest.raises(SystemExit, match="several jobs"):
        Machine("vm", VM, runner).cancel()
    assert not runner.ran("kill -TERM")


def test_cancelling_without_a_running_job_changes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(("ended", GATE))
    Machine("vm", VM, runner).cancel()
    assert "running no job" in capsys.readouterr().out
    assert not runner.ran("kill -TERM")


def test_removing_takes_the_container_down_and_deletes_the_clone() -> None:
    runner = FakeRunner(("fetched", GATE))
    Machine("vm", VM, runner).remove()
    [removal] = runner.ran("down")
    assert "just stack-clean; just clean-workbenches" in removal
    assert f"{COMPOSE} down --volumes --remove-orphans --rmi local || exit 1; cd && rm -rf repo2ree" in removal


def test_removing_refuses_while_a_job_runs() -> None:
    runner = FakeRunner([(".", "fetched", SYSTEM), (FURTHER, "starting", GATE)])
    with pytest.raises(SystemExit, match="vm is running a job; let it end, or: just machine cancel vm"):
        Machine("vm", VM, runner).remove()
    assert not runner.ran("down")


def test_collecting_garbage_prunes_the_workspaces_then_bounds_dockers_cache_and_images() -> None:
    runner = FakeRunner()
    Machine("vm", VM, runner).gc()
    [collection] = runner.ran("builder prune")
    locked, idle, clone, further, cache, images = (
        collection.index(part)
        for part in (
            "flock 9",
            'busy=$(busy ""',
            "just prune",
            "for dir in .machine-workspaces/*",
            "builder prune",
            "image prune",
        )
    )
    assert locked < idle < clone < further < cache < images
    assert "docker builder prune -a -f --filter until=24h" in collection
    assert "docker image prune -a -f --filter until=168h" in collection
    assert "nix-collect-garbage" in collection


def test_collecting_garbage_leaves_a_machine_running_a_job_alone() -> None:
    runner = FakeRunner()
    Machine("vm", VM, runner).gc()
    [collection] = runner.ran("builder prune")
    assert 'if test -n "$busy"; then' in collection
    assert "collecting nothing while they run" in collection


def test_tidying_prunes_a_machines_runs_to_the_newest_three_per_tier_once_their_results_are_here() -> None:
    runner = FakeRunner([(".", "fetched", SYSTEM), (FURTHER, "none", "")])
    Machine("vm", VM, runner).tidy()
    tidied = runner.ran("repo2ree_testbed prune")
    assert len(tidied) == 2
    assert all("prune --keep-runs 3 --keep-suite 3" in tidy for tidy in tidied)
    assert f"--workdir /repo2ree/{FURTHER} dev" in tidied[1]


@pytest.mark.parametrize("state", ["starting", "running", "ended"])
def test_tidying_prunes_nothing_while_a_jobs_results_are_not_here(state: str) -> None:
    runner = FakeRunner([(".", state, SYSTEM), (FURTHER, "fetched", GATE)])
    Machine("vm", VM, runner).tidy()
    [tidied] = runner.ran("repo2ree_testbed prune")
    assert f"--workdir /repo2ree/{FURTHER} dev" in tidied


def test_a_run_itself_neither_collects_garbage_nor_prunes() -> None:
    runner = FakeRunner(("none", ""), ("ended", SYSTEM))
    assert run_recipe(Machine("vm", VM, runner), ["test-e2e-system"]) == 0
    assert not runner.ran("builder prune")
    assert not runner.ran("repo2ree_testbed prune")


def test_here_there_is_nothing_to_collect_or_tidy() -> None:
    runner = FakeRunner()
    local = Machine(LOCAL, MachineConfig(), runner)
    local.gc()
    local.tidy()
    assert runner.calls == []


def test_results_another_run_is_already_bringing_back_are_not_copied_twice() -> None:
    runner = FakeRunner(("ended", SYSTEM), codes={"mkdir test-artifacts/machine-job/fetching": 1})

    code = Machine("vm", VM, runner).run(REVISION, ["just", "test-e2e-system"])

    assert code == 0
    assert runner.piped == []
    assert runner.ran("touch") == []


def test_a_machines_newest_archive_sets_replace_this_checkouts_set_for_each_platform_it_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(machine_mod, "ROOT", tmp_path)
    stale = tmp_path / "dist/images/linux-amd64"
    stale.mkdir(parents=True)
    (stale / "old.tar").write_text("old")
    kept = tmp_path / "dist/images/linux-arm64"
    kept.mkdir()
    archives = [(100, "dist/images/linux-amd64"), (200, f"{FURTHER}/dist/images/linux-amd64")]
    runner = FakeRunner(archives=archives)

    assert Machine("vm", VM, runner).fetch_archives() == 0

    [(producer, _)] = runner.piped
    assert _on_host(producer) == f"cd repo2ree && tar -cf - -C {FURTHER}/dist/images linux-amd64"
    assert sorted(path.name for path in stale.iterdir()) == ["manifest.json"]
    assert kept.is_dir()
    assert sorted(path.name for path in (tmp_path / "dist/images").iterdir()) == ["linux-amd64", "linux-arm64"]


def test_a_machine_without_archive_sets_says_so() -> None:
    assert Machine("vm", VM, FakeRunner(archives=[])).fetch_archives() == 1


# The stub engine of a host: `exec` greps the command lines in $HOME/processes as the dev container's /proc;
# anything else is recorded in $HOME/docker.log.
DOCKER = """#!/bin/sh
for last; do :; done
case " $* " in
  *" exec "*) exec sh -c "$(printf '%s' "$last" | sed "s#/proc/\\\\[0-9\\\\]\\\\*/cmdline#$HOME/processes#")" ;;
  *) echo "$*" >> "$HOME/docker.log" ;;
esac
"""


class Host:
    """A host the scripts really run on, in a home of their own, with the stub engine."""

    def __init__(self, home: Path) -> None:
        self.home = home
        (home / "bin").mkdir(parents=True)
        (home / "bin/docker").write_text(DOCKER)
        (home / "bin/docker").chmod(0o755)
        (home / "processes").write_text("")

    def _run(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        script = _on_host(argv)
        env = {**os.environ, "HOME": str(self.home), "PATH": f"{self.home / 'bin'}:{os.environ['PATH']}"}
        return subprocess.run(
            ["bash", "-c", script], cwd=self.home, env=env, text=True, capture_output=True, check=False
        )

    def call(self, argv: Sequence[str]) -> int:
        return self._run(argv).returncode

    def capture(self, argv: Sequence[str]) -> tuple[int, str]:
        done = self._run(argv)
        return done.returncode, done.stdout

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        raise AssertionError("nothing is brought back here")

    def job(self, workspace: str) -> Path:
        return self.home / "repo2ree" / Workspace(workspace).path("test-artifacts/machine-job")

    def alive(self, workspace: str) -> None:
        with (self.home / "processes").open("a") as processes:
            processes.write(f"bash -lc echo $$ > {Workspace(workspace).inside}/test-artifacts/machine-job/exit\n")


def _states(machine: Machine) -> list[tuple[str, str, str]]:
    return [(job.workspace.directory, job.state, job.command) for job in machine.jobs()]


def test_each_job_beside_a_busy_one_claims_a_workspace_of_its_own_and_a_free_one_is_reused(tmp_path: Path) -> None:
    host = Host(tmp_path)
    machine = Machine("vm", VM, host)
    assert machine.jobs() == []

    assert machine._claim(GATE) == Workspace(".")
    assert (tmp_path / "repo2ree/.git").is_dir()
    # Claimed, it is starting until its process group is there.
    assert _states(machine) == [(".", "starting", GATE)]
    assert machine._claim(SYSTEM) == Workspace(FURTHER)
    assert _states(machine) == [(".", "starting", GATE), (FURTHER, "starting", SYSTEM)]

    # A started job runs while its process does, and is dead once it is gone without an exit code.
    (host.job(".") / "pid").write_text("7\n")
    host.alive(".")
    (host.job(FURTHER) / "pid").write_text("8\n")
    assert _states(machine) == [(".", "running", GATE), (FURTHER, "dead", SYSTEM)]

    # A third job, while the others are neither free nor brought back, makes another workspace.
    assert machine._claim("third") == Workspace(".machine-workspaces/2")

    # Ended, then brought back: the clone is free again and the next job takes it first.
    (host.job(".") / "exit").write_text("0\n")
    assert _states(machine)[0] == (".", "ended", GATE)
    (host.job(".") / "fetched").touch()
    assert machine._claim("fourth") == Workspace(".")
    assert not (host.job(".") / "pid").exists()


def test_the_dev_container_is_rebuilt_only_while_no_other_job_is_busy(tmp_path: Path) -> None:
    host = Host(tmp_path)
    machine = Machine("vm", VM, host)
    machine._claim(GATE)
    machine._up(Workspace("."))
    machine._claim(SYSTEM)
    machine._up(Workspace(FURTHER))
    built, kept = (tmp_path / "docker.log").read_text().splitlines()
    assert built.endswith("up -d --build --quiet-pull --wait")
    assert kept.endswith("up -d --no-recreate --wait")


def test_fetching_brings_back_every_job_that_ended_unseen_and_starts_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    jobs = [(".", "ended", SYSTEM), (FURTHER, "running", GATE), (".machine-workspaces/2", "dead", "other")]
    runner = FakeRunner(jobs, code=1)

    assert Machine("vm", VM, runner).fetch() == 1

    assert len(runner.piped) == 2
    assert [_on_host(fetch).split(" && ")[0] for fetch, _ in runner.piped] == [
        "cd repo2ree",
        "cd repo2ree/.machine-workspaces/2",
    ]
    assert not _pushed(runner)
    assert not _started(runner)
    assert f"`{SYSTEM}` ended with exit code 1" in capsys.readouterr().out


def test_fetching_with_nothing_ended_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    assert Machine("vm", VM, FakeRunner([(".", "running", GATE)])).fetch() == 0
    assert "no ended job" in capsys.readouterr().out
