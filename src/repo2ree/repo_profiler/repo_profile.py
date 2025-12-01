from pathlib import Path

from pydantic import BaseModel

from repo2ree.python_packages_util.extract_python_version import (
    find_required_python_version,
)

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
    declared_dependencies: list["DeclaredDependency"]


class DeclaredDependency(BaseModel):
    name: str
    version_specifier: str | None


###################
# Main Functions
###################


def profile_repository(repo_dir: Path) -> PythonRepoProfile:
    extracted_python_version = find_required_python_version(repo_dir)

    configuration_files = extract_config_files(repo_dir)
    lock_files = extract_lock_files(repo_dir)
    declared_dependencies = []

    if (repo_dir / "Dockerfile").exists():
        dockerfile_path = str(repo_dir / "Dockerfile")
    else:
        dockerfile_path = None

    if (repo_dir / "LICENSE").exists():
        license_path = str(repo_dir / "LICENSE")
    else:
        license_path = None

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
        configuration_files=configuration_files,
        declared_dependencies=declared_dependencies,
    )

    return repo_profile


def extract_config_files(repo_dir: Path) -> list[str]:
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

    for config_file in possible_config_files:
        if (repo_dir / config_file).exists():
            config_files.append(config_file)

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
