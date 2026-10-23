#!/usr/bin/env python3
"""Require workspace-wide Just recipes to match the declared Python workspace."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def assignment_words(document: dict[str, Any], name: str) -> list[str]:
    return str(document["assignments"][name]["value"]).split()


def dependency_names(document: dict[str, Any], recipe: str) -> list[str]:
    return [str(item["recipe"]) for item in document["recipes"][recipe]["dependencies"]]


def expected_suites(root: Path, members: list[str], tier: str) -> list[str]:
    suites = []
    for member in members:
        tier_dir = root / member / "tests" / tier
        has_separate_tiers = (root / member / "tests" / "integration").is_dir()
        if tier_dir.is_dir() and (tier != "unit" or has_separate_tiers):
            suites.append(f"{member}/tests/{tier}")
        elif tier == "unit" and (root / member / "tests").is_dir():
            suites.append(f"{member}/tests")
    return suites


def recipe_stem(member: str) -> str:
    """A workspace member's name in its recipes: its path with "-" for "/" (assurance/checker → assurance-checker)."""
    return member.replace("/", "-")


def expected_test_recipes(suites: list[str], tier: str) -> list[str]:
    recipes = []
    for suite in suites:
        member = suite.split("/", 1)[0]
        suffix = f"-{tier}" if suite.endswith(f"/{tier}") else ""
        recipes.append(f"test-{member}{suffix}")
    return recipes


def compare(label: str, actual: list[str], expected: list[str]) -> str | None:
    if Counter(actual) == Counter(expected):
        return None
    return (
        f"{label} differs from the Python workspace\n  expected: {' '.join(expected)}\n  actual:   {' '.join(actual)}"
    )


def validate(document: dict[str, Any], config: dict[str, Any], root: Path) -> list[str]:
    members = list(config["tool"]["uv"]["workspace"]["members"])
    categories = config["tool"]["repo2ree"]["workspace"]
    backend = list(categories["backend"])
    assurance = list(categories["assurance"])
    tooling = list(categories["tooling"])
    import_packages = list(config["tool"]["importlinter"]["root_packages"])
    unit_suites = assignment_words(document, "UNIT_SUITES")
    integration_suites = assignment_words(document, "INTEGRATION_SUITES")
    integration_members = expected_suites(root, backend, "integration")
    checks = (
        compare("workspace categories", [*backend, *assurance, *tooling], members),
        compare("PYTHON_FORMAT_PATHS", assignment_words(document, "PYTHON_FORMAT_PATHS"), ["scripts", *members]),
        compare(
            "PYTHON_METRIC_PATHS",
            assignment_words(document, "PYTHON_METRIC_PATHS"),
            [f"{m}/src" for m in backend],
        ),
        compare(
            "ASSURANCE_METRIC_PATHS",
            assignment_words(document, "ASSURANCE_METRIC_PATHS"),
            [f"{m}/src" for m in assurance],
        ),
        compare("UNIT_SUITES packages", [suite.split("/", 1)[0] for suite in unit_suites], backend),
        compare(
            "INTEGRATION_SUITES packages",
            [suite.split("/", 1)[0] for suite in integration_suites],
            [suite.split("/", 1)[0] for suite in integration_members],
        ),
        compare("BACKEND_GRAPH_PACKAGES", assignment_words(document, "BACKEND_GRAPH_PACKAGES"), import_packages),
        compare(
            "check-backend dependencies",
            [name for name in dependency_names(document, "check-backend") if name != "check-architecture"],
            [f"check-{member}" for member in backend],
        ),
        compare(
            "test-backend-unit dependencies",
            dependency_names(document, "test-backend-unit"),
            expected_test_recipes(unit_suites, "unit"),
        ),
        compare(
            "test-backend-integration test dependencies",
            [name for name in dependency_names(document, "test-backend-integration") if name.startswith("test-")],
            expected_test_recipes(integration_suites, "integration"),
        ),
    )
    problems = [problem for problem in checks if problem is not None]
    for aggregate, recipe in (("check", "check-assurance"), ("test-unit", "test-assurance")):
        if recipe not in dependency_names(document, aggregate):
            problems.append(f"{aggregate} must include {recipe} independently of backend")
    for member in tooling:
        for aggregate, recipe in (
            ("check", f"check-{recipe_stem(member)}"),
            ("test-unit", f"test-{recipe_stem(member)}"),
        ):
            if recipe not in document["recipes"]:
                problems.append(f"missing tooling recipe: {recipe}")
            elif recipe not in dependency_names(document, aggregate):
                problems.append(f"{aggregate} must include {recipe}")
    for aggregate, prefix in (("check-assurance", "check"), ("test-assurance", "test")):
        expected = [f"{prefix}-{recipe_stem(member)}" for member in assurance]
        if problem := compare(f"{aggregate} dependencies", dependency_names(document, aggregate), expected):
            problems.append(problem)
        problems.extend(
            f"missing assurance recipe: {recipe}" for recipe in expected if recipe not in document["recipes"]
        )
    return problems


def main() -> int:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dumped = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    problems = validate(json.loads(dumped.stdout), config, ROOT)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"Just workspace coverage valid: {len(config['tool']['uv']['workspace']['members'])} packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
