from pathlib import Path

import pytest
from coverage import CoverageData

from repo2ree_testbed import python_coverage
from repo2ree_testbed.python_coverage import CoverageRoot


def measured(path: Path, execution: str = "same-run") -> Path:
    path.parent.mkdir(parents=True)
    path.touch()
    (path.parent / "provenance.json").write_text('{"execution_id":"' + execution + '"}')
    return path


def test_packages_come_from_backend_workspace_category() -> None:
    assert python_coverage.packages()[:3] == ("ree", "protocol", "core")


def test_tier_matches_tree_rejects_missing_sources(tmp_path: Path) -> None:
    data = CoverageData(basename=str(tmp_path / ".coverage.one"))
    data.add_lines({str(tmp_path / "gone.py"): {1}})
    data.write()
    assert not python_coverage.tier_matches_tree(tmp_path)


def test_combine_parts_requires_every_part(tmp_path: Path) -> None:
    root = CoverageRoot(tmp_path)
    measured(root.data / "unit-parts/core/.coverage")
    with pytest.raises(RuntimeError, match=r"^unit coverage is incomplete; missing: api$"):
        python_coverage.combine_parts(root, "unit", ("core", "api"))


def test_combine_uses_only_selected_tiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = CoverageRoot(tmp_path)
    selected = [measured(root.tier(tier)) for tier in ("unit", "integration")]
    measured(root.tier("demo-api"))
    calls: list[tuple[object, ...]] = []

    def record(*args: object, **_: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(python_coverage, "coverage_command", record)
    monkeypatch.setattr(python_coverage, "tier_matches_tree", lambda _directory: True)

    python_coverage.combine(root, ("unit", "integration"))

    combined = root.tier("combined")
    assert calls == [(combined, "combine", "--keep", *(str(path) for path in selected)), (combined, "report")]


def test_coverage_from_different_executions_is_refused(tmp_path: Path) -> None:
    files = [measured(tmp_path / tier / ".coverage", tier) for tier in ("unit", "integration")]
    with pytest.raises(RuntimeError, match="different executions"):
        python_coverage.coverage_identity(files)
