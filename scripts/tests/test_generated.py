import subprocess
from pathlib import Path

import pytest
from scripts import prune


def registry(**owners: tuple[str, ...]) -> prune.Registry:
    return prune.Registry(
        roots=("test-artifacts", ".receipts"),
        ignore=frozenset({".DS_Store"}),
        owners=tuple(prune.Owner(name, claims) for name, claims in owners.items()),
    )


def test_the_repositorys_registry_is_coherent() -> None:
    loaded = prune.load()
    assert prune.registry_problems(loaded) == []
    assert "test-artifacts/e2e" in loaded.claims


def test_a_claim_outside_every_root_twice_made_or_inside_another_is_refused() -> None:
    problems = prune.registry_problems(
        registry(
            a=("test-artifacts/e2e", "elsewhere/x", "test-artifacts"),
            b=("test-artifacts/e2e", "test-artifacts/python/tests"),
            c=("test-artifacts/python",),
        )
    )
    assert "a claims elsewhere/x, which lies under no root" in problems
    assert "a claims test-artifacts, which lies under no root" in problems
    assert "test-artifacts/e2e is claimed by both a and b" in problems
    assert "test-artifacts/python/tests lies inside test-artifacts/python: claim one or the other" in problems


def test_what_no_claim_covers_is_found_as_high_up_as_it_can_be_named(tmp_path: Path) -> None:
    for directory in ("test-artifacts/e2e/run-1", "test-artifacts/python/tests/x", "test-artifacts/python/old/y"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "test-artifacts/retired").mkdir()
    (tmp_path / "test-artifacts/.DS_Store").write_text("")
    (tmp_path / ".receipts").mkdir()
    (tmp_path / ".receipts/.gitignore").write_text("*\n")
    (tmp_path / ".receipts/commit-gate.json").write_text("{}")
    (tmp_path / ".receipts/legacy").mkdir()
    kept = {tmp_path / ".receipts/.gitignore"}

    found = prune.unclaimed(
        registry(testbed=("test-artifacts/e2e", "test-artifacts/python/tests"), gates=(".receipts/commit-gate.json",)),
        tmp_path,
        kept,
    )

    # Root by root, in the registry's order.
    assert found == [
        tmp_path / "test-artifacts/python/old",
        tmp_path / "test-artifacts/retired",
        tmp_path / ".receipts/legacy",
    ]


def test_each_owner_prunes_once_and_a_dry_run_is_passed_on(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        ran.append(command)
        return subprocess.CompletedProcess(command, 1 if "fails" in command else 0)

    monkeypatch.setattr("scripts.prune.subprocess.run", run)
    owners = (
        prune.Owner("a", ("test-artifacts/a",), ("python", "-m", "a", "prune")),
        prune.Owner("b", ("test-artifacts/b",)),
        prune.Owner("c", ("test-artifacts/c",), ("tool", "fails")),
    )
    failed = prune.run_owners(prune.Registry(("test-artifacts",), frozenset(), owners), dry_run=True)
    assert [command[1:] for command in ran] == [["-m", "a", "prune", "--dry-run"], ["fails", "--dry-run"]]
    assert failed == ["c"]
