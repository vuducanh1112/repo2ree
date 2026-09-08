from collections.abc import Callable
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
