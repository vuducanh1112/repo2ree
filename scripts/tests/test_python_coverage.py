from pathlib import Path

import pytest
from coverage import CoverageData
from scripts.coverage import python_coverage


def test_packages_come_from_workspace_configuration() -> None:
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


def test_combine_unit_requires_every_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path)
    for part in python_coverage.UNIT_PARTS[:-1]:
        path = tmp_path / "unit-parts" / part / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()

    with pytest.raises(RuntimeError, match=f"^unit coverage is incomplete; missing: {python_coverage.UNIT_PARTS[-1]}$"):
        python_coverage.combine_unit()


def test_combine_unit_uses_each_expected_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(python_coverage, "ROOT", tmp_path)
    monkeypatch.setattr(python_coverage, "DATA_DIR", tmp_path)
    files = []
    for part in python_coverage.UNIT_PARTS:
        path = tmp_path / "unit-parts" / part / ".coverage"
        path.parent.mkdir(parents=True)
        path.touch()
        files.append(path)

    calls: list[tuple[object, ...]] = []

    def record_call(*args: object, **_kwargs: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(python_coverage, "coverage_command", record_call)

    python_coverage.combine_unit()

    assert calls == [(tmp_path / "unit" / ".coverage", "combine", "--keep", *(str(path) for path in files))]
