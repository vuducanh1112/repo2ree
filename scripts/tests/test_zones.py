from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import zones
from scripts.zones import check, conflicts, load, problems, staged

RUNTIME = "core/src/repo2ree_core/operations/capture.py"

# The completeness of the committed declaration (`zones.py verify`) is deliberately
# not tested here, so commit-gate does not require it yet.


def test_a_specification_change_with_its_generated_module_checker_and_gate_is_allowed() -> None:
    paths = [
        "specifications/behaviour/entities/run.toml",
        "protocol/src/repo2ree_protocol/behaviour/machines.py",
        "conformance/src/repo2ree_conformance/check.py",
        "conformance/expected-verdicts.toml",
        "scripts/publish/behaviour_gate.py",
    ]
    assert check(paths) == 0


def test_unprotected_changes_alone_are_allowed() -> None:
    paths = [RUNTIME, "api/tests/system/test_failures.py", "scripts/test-stack/e2e_stack.py", "docs/README.md"]
    assert check(paths) == 0


@pytest.mark.parametrize(
    "protected_path",
    [
        "specifications/behaviour/invariants.toml",
        "conformance/tests/test_system_conformance.py",
        "conformance/expected-verdicts.toml",
        "scripts/publish/behaviour_gate.py",
        "scripts/publish/commit_gate_stamp.py",
        "just/behaviour.just",
        "just/publish.just",
        "zones.toml",
        "scripts/zones.py",
        ".pre-commit-config.yaml",
    ],
)
def test_a_protected_change_beside_anything_unprotected_is_refused(protected_path: str) -> None:
    for other in (RUNTIME, "docs/README.md", "unclaimed-file"):
        paths = [protected_path, other]
        assert conflicts(paths) == (paths[:1], paths[1:])
        assert check(paths) == 1


def test_the_longest_entry_decides() -> None:
    declared = load()
    assert declared.entry("conformance/expected-verdicts.toml").group == "excuses"  # type: ignore[union-attr]
    assert declared.entry("conformance/src/repo2ree_conformance/check.py").group == "checker"  # type: ignore[union-attr]
    assert declared.entry("api/tests/system/test_failures.py").group == "scenarios"  # type: ignore[union-attr]
    assert declared.entry("scripts/test-stack/e2e_stack.py").zone == "tooling"  # type: ignore[union-attr]
    assert declared.protected("protocol/src/repo2ree_protocol/behaviour/machines.py")
    assert not declared.protected("protocol/src/repo2ree_protocol/behaviour/writer.py")


def test_unclaimed_files_and_entries_that_claim_nothing_are_problems(tmp_path: Path) -> None:
    path = tmp_path / "zones.toml"
    path.write_text('[z]\nsummary = "s"\n[z.groups.g]\nsummary = "s"\n[z.groups.g.paths]\n"a/" = "d"\n"b/" = "d"\n')
    assert problems(load(path), ["a/x", "c"]) == ["no zone claims c", "b/ is declared but no tracked file is there"]


def test_a_path_declared_twice_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "zones.toml"
    group = '[{0}.groups.g]\nsummary = "s"\n[{0}.groups.g.paths]\n"x/" = "d"\n'
    path.write_text('[y]\nsummary = "s"\n' + group.format("y") + '[z]\nsummary = "s"\n' + group.format("z"))
    with pytest.raises(ValueError, match="declared more than once: x/"):
        load(path)


def test_a_staged_deletion_and_both_sides_of_a_rename_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    for name in ("gone.py", "moved.py"):
        (tmp_path / name).write_text("x = 1\n")
    run("add", ".")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    run("rm", "-q", "gone.py")
    run("mv", "moved.py", "renamed.py")
    monkeypatch.setattr(zones, "ROOT", tmp_path)
    assert sorted(staged()) == ["gone.py", "moved.py", "renamed.py"]


def test_the_map_draws_every_zone_and_places_a_path(capsys: pytest.CaptureFixture[str]) -> None:
    declared = load()
    zones.draw(declared, ["api/x.py"], ["dist/"])
    drawn = capsys.readouterr().out
    assert all(zone.name.upper() in drawn for zone in declared.zones)
    assert "SPEC [protected]" in drawn
    assert "dist/" in drawn
    assert zones.place(declared, "conformance/expected-verdicts.toml").splitlines()[1] == "  spec [protected] / excuses"
