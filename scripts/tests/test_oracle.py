from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import oracle
from scripts.oracle import check, conflicts, coverage_problems, load, staged, tracked

RUNTIME = "core/src/repo2ree_core/operations/capture.py"


def test_a_specification_change_with_its_generated_module_and_checker_is_allowed() -> None:
    paths = [
        "specifications/behaviour/entities/run.toml",
        "protocol/src/repo2ree_protocol/behaviour/machines.py",
        "conformance/src/repo2ree_conformance/check.py",
        "conformance/tests/test_check.py",
    ]
    assert check(paths) == 0


def test_product_alone_is_allowed() -> None:
    assert check(["api/src/repo2ree_api/storage/json_run_store.py", "api/tests/unit/test_run_behaviour.py"]) == 0


@pytest.mark.parametrize(
    "oracle_path",
    [
        "specifications/behaviour/invariants.toml",
        # Weakening a rule's reading, or excusing an edge, beside the code that needed it.
        "conformance/tests/test_system_conformance.py",
        "conformance/expected-verdicts.toml",
        "scripts/publish/behaviour_gate.py",
        "just/behaviour.just",
        # Dropping a scenario, or what it asserts, drops the evidence the gate judges.
        "api/tests/system/test_failures.py",
        "gui/tests/e2e-instant/failures.spec.ts",
        "examples/recipes/instant_hello_world/build_script.sh",
        "scripts/test-stack/e2e_stack.py",
        "collect/src/repo2ree_collect/collect.py",
        # The guard itself.
        ".pre-commit-config.yaml",
        "scripts/oracle.py",
    ],
)
def test_the_oracle_and_product_together_are_refused(oracle_path: str) -> None:
    paths = [oracle_path, RUNTIME]
    assert conflicts(paths) == (paths[:1], paths[1:])
    assert check(paths) == 1


def test_support_mixes_with_either() -> None:
    assert check(["docs/README.md", "traceview/src/repo2ree_traceview/render.py", RUNTIME]) == 0
    assert check(["docs/README.md", "just/e2e.just", "conformance/src/repo2ree_conformance/check.py"]) == 0


def test_the_longest_entry_decides() -> None:
    zones = load()
    assert zones.zone("api/tests/system/test_failures.py") == "oracle"
    assert zones.zone("api/tests/unit/test_runs.py") == "product"
    assert zones.zone("gui/tests/e2e/helpers/flow.ts") == "oracle"
    assert zones.zone("gui/tests/e2e/ree-pipeline.spec.ts") == "product"
    assert zones.zone("scripts/test-stack/inspect_run.py") == "support"
    assert zones.zone("unknown-top-level-file") is None


def test_every_file_has_a_zone_and_every_entry_a_file() -> None:
    assert coverage_problems(load(), tracked()) == []


def test_an_unclaimed_file_and_an_idle_entry_are_problems() -> None:
    zones = oracle.Zones((oracle.Entry("a/", "oracle", "g"), oracle.Entry("b/", "product", "g")), {})
    assert coverage_problems(zones, ["a/x", "c"]) == ["no zone declares c", "b/ is declared but owns no tracked file"]


def test_a_path_declared_twice_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "zones.toml"
    body = '[{0}]\nsummary = "s"\n[{0}.groups.g]\nsummary = "s"\npaths = ["x/"]\n'
    path.write_text("".join(body.format(zone) for zone in oracle.ZONES))
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
    monkeypatch.setattr(oracle, "ROOT", tmp_path)
    assert sorted(staged()) == ["gone.py", "moved.py", "renamed.py"]


def test_the_view_draws_every_zone(capsys: pytest.CaptureFixture[str]) -> None:
    oracle.show(load(), tracked())
    drawn = capsys.readouterr().out
    assert all(zone.upper() in drawn for zone in oracle.ZONES)
    assert "api/tests/system/" in drawn
