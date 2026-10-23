from pathlib import Path
from typing import Any

from scripts import check_just_workspace


def fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    members = ["alpha", "beta", "assurance/checker", "testbed"]
    for path in (root / "alpha/tests/unit", root / "beta/tests", root / "beta/tests/integration"):
        path.mkdir(parents=True)
    assignments = {
        "PYTHON_FORMAT_PATHS": {"value": "scripts alpha beta assurance/checker testbed"},
        "PYTHON_METRIC_PATHS": {"value": "alpha/src beta/src"},
        "ASSURANCE_METRIC_PATHS": {"value": "assurance/checker/src"},
        "UNIT_SUITES": {"value": "alpha/tests/unit beta/tests"},
        "INTEGRATION_SUITES": {"value": "beta/tests/integration"},
        "BACKEND_GRAPH_PACKAGES": {"value": "pkg_alpha pkg_beta"},
    }
    recipes = {
        "check": {"dependencies": [{"recipe": name} for name in ("check-backend", "check-assurance", "check-testbed")]},
        "test-unit": {
            "dependencies": [{"recipe": name} for name in ("test-backend-unit", "test-assurance", "test-testbed")]
        },
        "check-testbed": {"dependencies": []},
        "test-testbed": {"dependencies": []},
        "check-assurance": {"dependencies": [{"recipe": "check-assurance-checker"}]},
        "test-assurance": {"dependencies": [{"recipe": "test-assurance-checker"}]},
        "check-assurance-checker": {"dependencies": []},
        "test-assurance-checker": {"dependencies": []},
        "check-backend": {
            "dependencies": [{"recipe": name} for name in ("check-alpha", "check-beta", "check-architecture")]
        },
        "test-backend-unit": {"dependencies": [{"recipe": name} for name in ("test-alpha-unit", "test-beta")]},
        "test-backend-integration": {"dependencies": [{"recipe": "build"}, {"recipe": "test-beta-integration"}]},
    }
    document = {"assignments": assignments, "recipes": recipes}
    config = {
        "tool": {
            "repo2ree": {
                "workspace": {"backend": ["alpha", "beta"], "assurance": ["assurance/checker"], "tooling": ["testbed"]}
            },
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


def test_assurance_cannot_leak_back_into_backend(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)
    document["assignments"]["UNIT_SUITES"]["value"] += " assurance/checker/tests"
    document["recipes"]["check-backend"]["dependencies"].append({"recipe": "check-assurance-checker"})
    problems = check_just_workspace.validate(document, config, tmp_path)
    assert any("UNIT_SUITES packages" in problem for problem in problems)
    assert any("check-backend dependencies" in problem for problem in problems)


def test_assurance_still_required_by_global_aggregates(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)
    document["recipes"]["test-unit"]["dependencies"] = [{"recipe": "test-backend-unit"}]
    assert "test-unit must include test-assurance independently of backend" in check_just_workspace.validate(
        document, config, tmp_path
    )


def test_categories_cover_workspace_exactly_once(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)
    config["tool"]["repo2ree"]["workspace"]["backend"].append("conformance")
    assert any(
        "workspace categories" in problem for problem in check_just_workspace.validate(document, config, tmp_path)
    )


def test_tooling_required_by_global_aggregates(tmp_path: Path) -> None:
    document, config = fixture(tmp_path)
    document["recipes"]["check"]["dependencies"].pop()
    del document["recipes"]["test-testbed"]
    assert check_just_workspace.validate(document, config, tmp_path) == [
        "check must include check-testbed",
        "missing tooling recipe: test-testbed",
    ]
