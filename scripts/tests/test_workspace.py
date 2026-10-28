from pathlib import Path
from typing import Any

import pytest
from scripts import workspace


def config(members: list[str]) -> dict[str, Any]:
    return {
        "tool": {
            "repo2ree": {
                "workspace": {"backend": ["alpha", "beta"], "assurance": ["assurance/checker"], "tooling": []}
            },
            "uv": {"workspace": {"members": members}},
        }
    }


def test_roles_divide_the_members() -> None:
    packages = workspace.roles(config(["alpha", "beta", "assurance/checker"]))

    assert packages["backend"] == ["alpha", "beta"]
    assert packages["members"] == ["alpha", "beta", "assurance/checker"]


@pytest.mark.parametrize("members", [["alpha", "beta"], ["alpha", "beta", "assurance/checker", "gamma"]])
def test_a_member_without_exactly_one_role_is_refused(members: list[str]) -> None:
    with pytest.raises(ValueError, match="exactly one role"):
        workspace.roles(config(members))


def test_suites_follow_each_packages_test_layout(tmp_path: Path) -> None:
    for path in ("alpha/tests/unit", "alpha/tests/integration", "beta/tests"):
        (tmp_path / path).mkdir(parents=True)

    assert workspace.suites(tmp_path, "unit", ["alpha", "beta", "gamma"]) == ["alpha/tests/unit", "beta/tests"]
    assert workspace.suites(tmp_path, "integration", ["alpha", "beta"]) == ["alpha/tests/integration"]
