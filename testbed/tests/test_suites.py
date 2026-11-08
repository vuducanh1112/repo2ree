"""What import-linter cannot see: the suites are scripts beside the harness, not a package."""

import ast
from pathlib import Path

import pytest

SUITES = Path(__file__).resolve().parents[1] / "suites"


def repo2ree_imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return {name for name in found if name.startswith("repo2ree_")}


@pytest.mark.parametrize("path", sorted(SUITES.rglob("*.py")), ids=lambda path: str(path.relative_to(SUITES)))
def test_a_suite_reaches_the_product_only_as_a_deployment(path: Path) -> None:
    assert repo2ree_imports(path) <= {"repo2ree_testbed"}
