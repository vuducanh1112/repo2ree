from pathlib import Path

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
