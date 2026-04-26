from pathlib import Path
import subprocess
import os
import json

from repo2ree_core.repo_profiler.dependency_score import DependencyMaturity


def analyze_dependency_maturity(repo_path: Path) -> DependencyMaturity:
    dependencies = analyze_dependencies(repo_path)
    maturity = calculate_dependency_maturity(dependencies)

    return maturity


def analyze_dependencies(repo_path: Path) -> dict:
    renovate_output = analyze_dependencies_with_renovate(repo_path)
    dependencies = extract_dependencies_from_renovate_output(renovate_output)

    return dependencies


def analyze_dependencies_with_renovate(repo_path: Path) -> str:
    assert repo_path.exists()

    env = os.environ.copy()
    env["LOG_LEVEL"] = "info"

    cmd = ["renovate", "--platform=local", "--dry-run=extract"]

    try:
        completed_process = subprocess.run(
            cmd,
            cwd=str(repo_path),
            env=env,
            text=True,
            check=False,
            capture_output=True,
        )

        res = completed_process.stdout
    except Exception as e:
        raise RuntimeError(f"Failed to run Renovate: {e}")

    return res


def extract_dependencies_from_renovate_output(renovate_output: str) -> dict:
    dependencies_json_str = ""

    # split on INFO:
    parts = renovate_output.split("INFO: ")

    for part in parts:
        if part.startswith("Extracted dependencies (repository=local)"):
            dependencies_json_str = (
                "{" + part[len("Extracted dependencies (repository=local)") :] + "}"
            )
            break

    json_data = json.loads(dependencies_json_str)

    return json_data


def calculate_dependency_maturity(dependencies: dict) -> DependencyMaturity:
    range_version_specifiers = [">", "<", "~", "^"]

    unpinned_dependencies = []
    range_pinned_dependencies = []
    exactly_pinned_dependencies = []
    locked_dependencies = []

    for overall_package_file in dependencies.get("packageFiles", []):
        for specific_package_file in dependencies.get("packageFiles", {}).get(
            overall_package_file, []
        ):
            for dep in specific_package_file.get("deps", []):
                if dep.get("lockedVersion"):
                    locked_dependencies.append(dep.get("depName", ""))
                    continue

                declared_version = dep.get("currentValue", "")
                if not declared_version:
                    unpinned_dependencies.append(dep.get("depName", ""))
                else:
                    if any(
                        specifier in declared_version
                        for specifier in range_version_specifiers
                    ):
                        range_pinned_dependencies.append(dep.get("depName", ""))
                    else:
                        exactly_pinned_dependencies.append(dep.get("depName", ""))

    maturity = DependencyMaturity.NONE
    if (
        not unpinned_dependencies
        and not range_pinned_dependencies
        and not exactly_pinned_dependencies
    ):
        maturity = DependencyMaturity.NONE

    if (
        unpinned_dependencies
        and not range_pinned_dependencies
        and not exactly_pinned_dependencies
    ):
        maturity = DependencyMaturity.DECLARED

    if range_pinned_dependencies or exactly_pinned_dependencies:
        maturity = DependencyMaturity.COMPATIBLE

    if (
        exactly_pinned_dependencies
        and not range_pinned_dependencies
        and not unpinned_dependencies
    ):
        maturity = DependencyMaturity.STRICT

    if (
        locked_dependencies
        and not range_pinned_dependencies
        and not unpinned_dependencies
        and not exactly_pinned_dependencies
    ):
        maturity = DependencyMaturity.DETERMINISTIC

    return maturity


if __name__ == "__main__":
    res = analyze_dependencies_with_renovate(Path("/home/nixuser/HumanEvo"))
    # print("Renovate output:")
    print(res)
    depdencies = extract_dependencies_from_renovate_output(res)
    print("Extracted dependencies:")
    print(json.dumps(depdencies, indent=2))
    maturity = calculate_dependency_maturity(depdencies)
    print(f"Dependency maturity: {maturity.label} - {maturity.description}")
