from collections.abc import Callable
from pathlib import Path

import pytest
from coverage import CoverageData
from scripts.coverage import python_coverage


def test_packages_come_from_backend_workspace_category() -> None:
    assert python_coverage.packages() == (
        "protocol",
        "core",
        "supervisor",
        "api",
        "executor",
        "docker-support",
        "provider",
        "workbench",
    )


def test_tier_matches_tree_rejects_missing_sources(tmp_path: Path) -> None:
    data = CoverageData(basename=str(tmp_path / ".coverage.one"))
    data.add_lines({str(tmp_path / "gone.py"): {1}})
    data.write()

    assert not python_coverage.tier_matches_tree(tmp_path)


@pytest.mark.parametrize(
    ("tier", "parts", "combine_parts"),
    [
        ("unit", python_coverage.UNIT_PARTS, python_coverage.combine_unit),
        ("integration", python_coverage.INTEGRATION_PARTS, python_coverage.combine_integration),
    ],
)
def test_combine_tier_requires_every_part(
    tier: str,
    parts: tuple[str, ...],
    combine_parts: Callable[[], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path)
    for part in parts[:-1]:
        path = tmp_path / f"{tier}-parts" / part / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"same-run"}')

    with pytest.raises(RuntimeError, match=rf"^{tier} coverage is incomplete; missing: {parts[-1]}$"):
        combine_parts()


@pytest.mark.parametrize(
    ("tier", "parts", "combine_parts"),
    [
        ("unit", python_coverage.UNIT_PARTS, python_coverage.combine_unit),
        ("integration", python_coverage.INTEGRATION_PARTS, python_coverage.combine_integration),
    ],
)
def test_combine_tier_uses_each_expected_part(
    tier: str,
    parts: tuple[str, ...],
    combine_parts: Callable[[], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(python_coverage, "ROOT", tmp_path)
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path)
    files = []
    for part in parts:
        path = tmp_path / f"{tier}-parts" / part / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"same-run"}')
        files.append(path)

    calls: list[tuple[object, ...]] = []

    def record_call(*args: object, **_kwargs: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(python_coverage, "coverage_command", record_call)

    combine_parts()

    assert calls == [(tmp_path / tier / ".coverage", "combine", "--keep", *(str(path) for path in files))]


def test_combine_uses_only_selected_tiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(python_coverage, "ROOT", tmp_path)
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path)
    selected = []
    for tier in ("unit", "integration", "demo-api"):
        path = tmp_path / tier / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"same-run"}')
        if tier != "demo-api":
            selected.append(path)

    calls: list[tuple[object, ...]] = []

    def record_call(*args: object, **_kwargs: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(python_coverage, "coverage_command", record_call)
    monkeypatch.setattr(python_coverage, "tier_matches_tree", lambda _directory: True)

    python_coverage.combine(("unit", "integration"))

    combined = tmp_path / "combined" / ".coverage"
    assert calls == [
        (combined, "combine", "--keep", *(str(path) for path in selected)),
        (combined, "report"),
    ]


def test_reporting_selects_one_complete_historical_run(tmp_path, monkeypatch):
    monkeypatch.setattr(python_coverage, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path / "runs/new/coverage/python/data")
    complete = tmp_path / "runs/complete"
    for run, tier in [(complete, "unit"), (complete, "integration"), (tmp_path / "runs/later-unit", "unit")]:
        path = run / "coverage/python/data" / tier / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"same-run"}')
    assert python_coverage.select_reporting_run(("unit", "integration")) == complete


def test_reporting_does_not_mix_separate_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(python_coverage, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path / "runs/new/coverage/python/data")
    for tier in ("unit", "integration"):
        path = tmp_path / "runs" / tier / "coverage/python/data" / tier / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"same-run"}')
    with pytest.raises(RuntimeError, match="no recorded run"):
        python_coverage.select_reporting_run(("unit", "integration"))


def test_current_and_explicit_reporting_runs_are_preserved(tmp_path, monkeypatch):
    current = tmp_path / "current"
    data = current / "coverage/python/data"
    monkeypatch.setattr(python_coverage, "DATA_DIR", data)
    (data / "unit").mkdir(parents=True)
    (data / "unit/.coverage").touch()
    assert python_coverage.select_reporting_run(("unit", "integration")) == current
    assert python_coverage.select_reporting_run(("combined",), tmp_path / "explicit") == tmp_path / "explicit"


def test_stable_coverage_paths_reject_mixed_executions(tmp_path):
    files = []
    for tier in ("unit", "integration"):
        path = tmp_path / tier / ".coverage"
        path.parent.mkdir()
        path.touch()
        (path.parent / "provenance.json").write_text('{"execution_id":"' + tier + '"}')
        files.append(path)
    with pytest.raises(RuntimeError, match="different executions"):
        python_coverage.coverage_identity(files)
