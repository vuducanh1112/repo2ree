from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import zones
from scripts.zones import check, conflicts, load, problems, staged

RUNTIME = "core/src/repo2ree_core/operations/capture.py"

# The completeness of the committed declaration (`zones.py verify`) is deliberately
# not tested here, so commit-gate does not require it yet.


def test_a_specification_change_with_its_generated_contract_checker_and_gate_is_allowed() -> None:
    paths = [
        "assurance/spec/entities/run.toml",
        "contracts/behaviour/events.schema.json",
        "assurance/checker/src/repo2ree_assurance_checker/check.py",
        "assurance/checker/expected-verdicts.toml",
        "scripts/publish/behaviour_gate.py",
    ]
    assert check(paths) == 0


def test_unprotected_changes_alone_are_allowed() -> None:
    paths = [
        RUNTIME,
        "api/tests/system/test_failures.py",
        "testbed/src/repo2ree_testbed/stack/e2e.py",
        "docs/README.md",
    ]
    assert check(paths) == 0


@pytest.mark.parametrize(
    "protected_path",
    [
        "assurance/spec/invariants.toml",
        "assurance/spec/vocabulary/run.toml",
        "contracts/behaviour/events.schema.json",
        "assurance/checker/tests/test_system_conformance.py",
        "assurance/checker/expected-verdicts.toml",
        "scripts/publish/behaviour_gate.py",
        "scripts/publish/commit_gate_stamp.py",
        "just/gates.just",
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
    assert declared.entry("assurance/checker/expected-verdicts.toml").group == "excuses"  # type: ignore[union-attr]
    assert declared.entry("assurance/checker/src/repo2ree_assurance_checker/check.py").group == "checker"  # type: ignore[union-attr]
    assert declared.entry("api/tests/system/test_failures.py").group == "scenarios"  # type: ignore[union-attr]
    assert declared.entry("testbed/src/repo2ree_testbed/stack/e2e.py").zone == "tooling"  # type: ignore[union-attr]
    assert declared.entry("assurance/collector/src/repo2ree_assurance_collector/cli.py").zone == "assurance"  # type: ignore[union-attr]
    assert declared.protected("contracts/behaviour/events.schema.json")
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
    assert (
        zones.place(declared, "assurance/checker/expected-verdicts.toml").splitlines()[1]
        == "  spec [protected] / excuses"
    )


def test_the_export_places_each_file_and_carries_the_problems(tmp_path: Path) -> None:
    path = tmp_path / "zones.toml"
    path.write_text(
        '[z]\nsummary = "s"\nprotected = true\n'
        '[z.groups.g]\nsummary = "t"\n[z.groups.g.paths]\n"a/" = "d"\n"b/" = "d"\n'
    )
    exported = zones.export(load(path), ["a/x", "c"])
    assert exported["zones"] == [
        {
            "name": "z",
            "summary": "s",
            "protected": True,
            "groups": [
                {
                    "name": "g",
                    "summary": "t",
                    "entries": [{"path": "a/", "description": "d"}, {"path": "b/", "description": "d"}],
                }
            ],
        }
    ]
    assert exported["files"] == [
        {"path": "a/x", "zone": "z", "group": "g", "entry": "a/"},
        {"path": "c", "zone": None, "group": None, "entry": None},
    ]
    assert exported["problems"] == problems(load(path), ["a/x", "c"])
