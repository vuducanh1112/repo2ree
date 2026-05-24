import os
from pathlib import Path
from datetime import datetime
from typing import Any
import json
import logging

from pydantic import BaseModel

from repo2ree_core.python_packages_util.extract_python_version import (
    find_required_python_version,
)
from repo2ree_core.python_packages_util.pin_conda_package_version import (
    extract_conda_environment_dependencies,
)
from repo2ree_core.python_packages_util.pin_pypi_package_version import (
    extract_dependencies_from_requirements_txt,
    extract_dependencies_from_pyproject_toml,
)
from repo2ree_core.llm_utils.client import generate_completion


logging.basicConfig(level=logging.DEBUG)

###################
# Data Models
###################


class PythonRepoProfile(BaseModel):
    name: str
    url: str | None
    license: str | None

    python_version: str | None

    dockerfile: str | None
    sbom_path: str | None

    lock_files: list[str]

    configuration_files: list[str]
    declared_dependencies: dict[str, list["DeclaredDependency"]]

    repo_content_hash: str | None
    profile_created_at: datetime | None

    has_unpinned_dependencies: bool = False


class DeclaredDependency(BaseModel):
    name: str


###################
# Main Functions
###################


def profile_repository(repo_dir: Path) -> PythonRepoProfile:
    extracted_python_version = find_required_python_version(repo_dir)

    configuration_files = extract_config_files(repo_dir)
    lock_files = extract_lock_files(repo_dir)
    declared_dependencies = extract_declared_dependencies(configuration_files)

    if (repo_dir / "Dockerfile").exists():
        dockerfile_path = str(repo_dir / "Dockerfile")
    else:
        dockerfile_path = None

    if (repo_dir / "LICENSE").exists():
        license_path = str(repo_dir / "LICENSE")
    else:
        license_path = None

    profile_created_at = datetime.now()

    readme_extracted_data: dict[str, Any] = {}
    if (repo_dir / "README.md").exists():
        logging.info("Extracting data from README.md using LLM.")
        # readme_extracted_data = extract_python_and_dependencies_from_readme(
        #    repo_dir / "README.md"
        # )

    declared_dependencies["README.md"] = []
    for dep in readme_extracted_data.get("dependencies", []):
        declared_dependencies["README.md"].append(DeclaredDependency(name=dep))

    if not extracted_python_version and readme_extracted_data.get("python_version"):
        extracted_python_version = readme_extracted_data.get("python_version")

    repo_profile = PythonRepoProfile(
        name=repo_dir.name,
        url=None,
        license=license_path,
        python_version=str(extracted_python_version)
        if extracted_python_version
        else None,
        dockerfile=dockerfile_path,
        sbom_path=None,
        lock_files=lock_files,
        configuration_files=[str(file) for file in configuration_files],
        declared_dependencies=declared_dependencies,
        repo_content_hash=None,
        profile_created_at=profile_created_at,
    )

    repo_profile.has_unpinned_dependencies = has_unpinned_dependencies(repo_profile)

    return repo_profile


def extract_config_files(repo_dir: Path) -> list[Path]:
    config_files = []
    possible_config_files = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "requirements.txt",
        "environment.yml",
        "runtime.txt",
    ]

    config_files = find_files(possible_config_files, repo_dir, max_depth=1)

    return config_files


def extract_lock_files(repo_dir: Path) -> list[str]:
    lock_files = []
    possible_lock_files = [
        "poetry.lock",
        "Pipfile.lock",
        "requirements.lock",
        "environment.lock.yml",
        "uv.lock",
    ]

    for lock_file in possible_lock_files:
        if (repo_dir / lock_file).exists():
            lock_files.append(lock_file)

    return lock_files


def extract_declared_dependencies(
    configuration_files: list[Path],
) -> dict[str, list[DeclaredDependency]]:
    ##############
    assert all(path.exists() for path in configuration_files), (
        "All configuration files must exist"
    )
    ##############

    declared_dependencies: dict[str, list[DeclaredDependency]] = dict()
    for config_file in configuration_files:
        declared_dependencies[str(config_file)] = []
        if config_file.name == "requirements.txt":
            requirements_file_content = (config_file).read_text()
            dependencies = extract_dependencies_from_requirements_txt(
                requirements_file_content
            )
            for dep in dependencies:
                declared_dependencies[str(config_file)].append(
                    DeclaredDependency(name=dep)
                )
        elif config_file.name == "pyproject.toml":
            pyproject_file_content = (config_file).read_text()
            dependencies = extract_dependencies_from_pyproject_toml(
                pyproject_file_content
            )
            for dep in dependencies:
                declared_dependencies[str(config_file)].append(
                    DeclaredDependency(name=dep)
                )
        elif config_file.name == "environment.yml":
            environment_file_content = (config_file).read_text()
            conda_dependencies = extract_conda_environment_dependencies(
                environment_file_content
            )

            for dep in conda_dependencies.get("pip_dependencies", []):
                declared_dependencies[str(config_file)].append(
                    DeclaredDependency(name=dep)
                )
            for dep in conda_dependencies.get("conda_dependencies", []):
                declared_dependencies[str(config_file)].append(
                    DeclaredDependency(name=dep)
                )

    return declared_dependencies


def has_unpinned_dependencies(repo_profile: PythonRepoProfile) -> bool:
    version_specifier_keywords = [
        ">",
        "<",
        "=",
        "~",
        "^",
        "*",
    ]

    for deps in repo_profile.declared_dependencies.values():
        for dep in deps:
            if not any(keyword in dep.name for keyword in version_specifier_keywords):
                return True

    return False


def find_files(file_names: list[str], root_dir: Path, max_depth: int = 0) -> list[Path]:
    ##############
    assert root_dir.exists(), "root_dir must exist"
    assert root_dir.is_dir(), "root_dir must be a directory"
    assert max_depth >= 0, "max_depth must be non-negative"
    ##############

    found_files: list[Path] = []
    enumerated_files = []

    # Enumerate files up to max_depth
    for current_path, dirs, files in os.walk(root_dir):
        current_depth = Path(current_path).relative_to(root_dir).parts
        if len(current_depth) > max_depth:
            # Skip directories deeper than max_depth
            dirs[:] = []
            continue
        for file in files:
            enumerated_files.append(Path(current_path) / file)

    for enumerated_file in enumerated_files:
        for file_name in file_names:
            # print(f"Checking if {file_name} is in {enumerated_file}. result: {file_name in str(enumerated_file)}")
            if file_name in str(enumerated_file):
                found_files.append(enumerated_file)

    ##############
    assert all(path.exists() for path in found_files)
    ##############

    return found_files


def extract_python_and_dependencies_from_readme(readme_path: Path) -> dict:
    ##############
    assert readme_path.exists(), "readme_path must exist"
    assert readme_path.is_file(), "readme_path must be a file"
    ##############

    readme_content = readme_path.read_text()

    prompt = f"""
    Extract the declared Python version and list of dependencies that need to be installed to run the project from the following README content.

    --- README CONTENT START ---
    {readme_content}
    --- README CONTENT END ---

    Respond in the following JSON format:
    {{
        "python_version": "<extracted_python_version_or_None>",
        "dependencies": ["<dependency1>", "<dependency2>", ...]
    }}
    """

    response = generate_completion(
        url="http://host.docker.internal:11434/api/generate",
        api_key="",
        model="deepseek-r1",
        prompt=prompt,
        format="json",
    )

    try:
        extracted_data = json.loads(response)
        validated_data = validate_llm_extracted_data(extracted_data, readme_content)
    except json.JSONDecodeError:
        logging.error("Failed to decode LLM response as JSON.")
        validated_data = {
            "python_version": None,
            "dependencies": [],
        }

    return validated_data


def validate_llm_extracted_data(data: dict, source_data: str) -> dict:
    new_data: dict[str, Any] = {
        "python_version": None,
        "dependencies": set(),
    }

    for line in source_data.splitlines():
        if data.get("python_version"):
            if "python" in line.lower() and data["python_version"] in line.lower():
                new_data["python_version"] = data["python_version"]

        for dependency in data.get("dependencies", []):
            if dependency in line:
                new_data["dependencies"].add(dependency)

    return new_data
