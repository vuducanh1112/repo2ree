from pathlib import Path
from typing import Any

from scripts import check_just_workspace


def fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    members = ["alpha", "beta"]
    for path in (root / "alpha/tests/unit", root / "beta/tests", root / "beta/tests/integration"):
        path.mkdir(parents=True)
    assignments = {
        "PYTHON_FORMAT_PATHS": {"value": "scripts alpha beta"},
        "PYTHON_METRIC_PATHS": {"value": "alpha/src beta/src"},
        "UNIT_SUITES": {"value": "alpha/tests/unit beta/tests"},
        "INTEGRATION_SUITES": {"value": "beta/tests/integration"},
        "BACKEND_GRAPH_PACKAGES": {"value": "pkg_alpha pkg_beta"},
    }
    recipes = {
        "check-backend": {
            "dependencies": [{"recipe": name} for name in ("check-alpha", "check-beta", "check-architecture")]
        },
        "test-backend-unit": {"dependencies": [{"recipe": name} for name in ("test-alpha-unit", "test-beta")]},
        "test-backend-integration": {"dependencies": [{"recipe": "build"}, {"recipe": "test-beta-integration"}]},
    }
    document = {"assignments": assignments, "recipes": recipes}
    config = {
        "tool": {
            "uv": {"workspace": {"members": members}},
            "importlinter": {"root_packages": ["pkg_alpha", "pkg_beta"]},
        }
    }
    return document, config


def test_validate_accepts_complete_workspace_lists(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)

    assert check_just_workspace.validate(document, config, tmp_path) == []


def test_validate_reports_a_missing_package(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)
    document["assignments"]["PYTHON_METRIC_PATHS"]["value"] = "alpha/src"

    assert check_just_workspace.validate(document, config, tmp_path) == [
        "PYTHON_METRIC_PATHS differs from the Python workspace\n  expected: alpha/src beta/src\n  actual:   alpha/src"
    ]
