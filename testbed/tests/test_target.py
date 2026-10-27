from collections.abc import Sequence
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs import target as target_mod
from repo2ree_testbed.runs.target import RECEIPT, RUN_LINE, Machine, gate, run_recipe
from repo2ree_testbed.targets import LOCAL, Target, load_targets

REVISION = "0123456789abcdef0123456789abcdef01234567"


class FakeRunner:
    def __init__(self, *, code: int = 0, printed: Sequence[str] = ()) -> None:
        self.code = code
        self.printed = list(printed)
        self.calls: list[list[str]] = []
        self.streamed: list[list[str]] = []
        self.piped: list[tuple[list[str], list[str]]] = []

    def call(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return 0

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        self.streamed.append(list(argv))
        return self.code, self.printed

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        self.piped.append((list(producer), list(consumer)))
        return 0


@pytest.fixture(autouse=True)
def committed(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = {("git", "status", "--porcelain"): "", ("git", "rev-parse", "HEAD"): REVISION}
    monkeypatch.setattr(target_mod, "capture", lambda argv: answers[tuple(argv)])


def test_this_checkout_is_always_a_target_and_the_file_adds_machines(tmp_path: Path) -> None:
    assert set(load_targets(tmp_path / "absent.toml")) == {LOCAL}
    listed = tmp_path / "targets.toml"
    listed.write_text('[targets.vm]\nhost = "vm"\njobs = 6\n')
    targets = load_targets(listed)
    assert targets[LOCAL].host is None
    assert targets["vm"] == Target(host="vm", jobs=6)


@pytest.mark.parametrize(
    "text",
    ['[targets.local]\nhost = "vm"\n', "[targets.vm]\njobs = 2\n", '[targets.vm]\nhost = "vm"\ncolour = "red"\n'],
)
def test_a_targets_file_cannot_redefine_this_checkout_omit_a_host_or_add_settings(tmp_path: Path, text: str) -> None:
    listed = tmp_path / "targets.toml"
    listed.write_text(text)
    with pytest.raises(SystemExit):
        load_targets(listed)


def test_a_remote_gate_ships_the_commit_runs_in_the_dev_shell_and_brings_back_runs_and_receipt() -> None:
    remote_run = "/home/ci/repo2ree/test-artifacts/e2e/e2e-system-20261027-120000"
    runner = FakeRunner(printed=["building", f"{RUN_LINE}{remote_run}", ">> passed"])
    machine = Machine("vm", Target(host="vm", path="repo2ree", jobs=6), runner)

    assert gate(machine, None) == 0

    pushed = [call for call in runner.calls if call[:2] == ["git", "push"]]
    assert pushed == [["git", "push", "-q", "--force", "vm:repo2ree", f"{REVISION}:refs/testbed/head"]]
    assert any(f"git checkout -q --detach --force {REVISION}" in call[-1] for call in runner.calls)
    [ran] = runner.streamed
    assert ran[:2] == ["ssh", "vm"]
    assert ran[2].startswith("bash -lc ")
    assert "nix develop --command just assurance-gate 6" in ran[2]

    run_fetch, receipt_fetch = runner.piped
    assert "--exclude=*.tar" in run_fetch[0][-1]
    assert run_fetch[1] == ["tar", "-xf", "-", "-C", str(ROOT / "test-artifacts/e2e")]
    assert RECEIPT in receipt_fetch[0][-1]


def test_a_failed_remote_gate_brings_back_its_runs_but_not_a_receipt() -> None:
    remote_run = "/srv/repo2ree/test-artifacts/e2e/e2e-gui-instant-20261027-120000"
    runner = FakeRunner(code=1, printed=[f"{RUN_LINE}{remote_run}"])
    machine = Machine("vm", Target(host="vm", fetch="full"), runner)

    assert gate(machine, 2) == 1

    [run_fetch] = runner.piped
    assert "--exclude" not in run_fetch[0][-1]
    assert "just assurance-gate 2" in runner.streamed[0][-1]


def test_the_local_target_runs_here_and_moves_nothing() -> None:
    runner = FakeRunner(printed=[f"{RUN_LINE}{ROOT}/test-artifacts/e2e/e2e-system-20261027-120000"])
    machine = Machine(LOCAL, Target(path=str(ROOT), shell=()), runner)

    assert gate(machine, None) == 0
    assert run_recipe(machine, ["test-e2e-system"]) == 0

    assert runner.calls == []
    assert runner.piped == []
    assert runner.streamed == [["just", "assurance-gate", "4"], ["just", "test-e2e-system"]]


def test_a_target_runs_only_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(target_mod, "capture", lambda argv: " M core/x.py")
    with pytest.raises(SystemExit, match="commit first"):
        gate(Machine("vm", Target(host="vm"), FakeRunner()), None)
