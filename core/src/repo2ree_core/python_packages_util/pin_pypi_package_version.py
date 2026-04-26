import logging
from datetime import datetime

import requests
from pydantic import BaseModel
import tomli
import tomli_w
from packaging.version import Version
from packaging.requirements import Requirement, InvalidRequirement
from packaging.specifiers import SpecifierSet


###################
# Data Models
###################


class PYPIPackageRelease(BaseModel, frozen=True):
    digests: dict
    filename: str
    python_version: str | None
    requires_python: str | None
    size: int
    upload_time: datetime
    upload_time_iso_8601: datetime
    url: str
    yanked: bool


class PYPIPackageInfo(BaseModel):
    name: str
    releases: dict[str, PYPIPackageRelease]


###################
# Main Functions
###################


def get_latest_version_on_pypi_until_date(
    package_name: str, target_date: datetime
) -> str | None:
    pypi_package_info = get_pypi_package_info(package_name)

    versions = [Version(v) for v in pypi_package_info.releases.keys()]

    for version in sorted(versions, reverse=True):
        release = pypi_package_info.releases[str(version)]
        if release.upload_time <= target_date and not release.yanked:
            return str(version)

    return None


def pin_package_versions_in_requirements_txt(
    requirements_file_content: str, cutoff_date: datetime
) -> str:
    pinned_requirements_file_content = ""

    for line in requirements_file_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            pinned_requirements_file_content += line + "\n"
            continue

        pinned_requirements_file_content += (
            pin_python_dependency_in_string(line, cutoff_date) + "\n"
        )

    return pinned_requirements_file_content


def pin_package_versions_in_pyproject_toml(
    pyproject_file_content: str, cutoff_date: datetime
) -> str:
    pyproject_data = tomli.loads(pyproject_file_content)
    # TODO handle other dependency sections like dev-dependencies, optional-dependencies, etc.

    dependencies = []
    dependencies.append(pyproject_data.get("project", {}).get("dependencies", []))

    pinned_dependencies = []

    for dependency in dependencies:
        pinned_dependencies.append(
            pin_python_dependency_in_string(dependency, cutoff_date)
        )

    pyproject_data["project"]["dependencies"] = pinned_dependencies
    # TODO: This does not preserve formatting or comments
    # Consider using a TOML library that supports round-tripping if needed
    pinned_pyproject_file_content = tomli_w.dumps(pyproject_data)
    return pinned_pyproject_file_content


def extract_dependencies_from_requirements_txt(
    requirements_file_content: str,
) -> list[str]:
    dependencies = []
    for line in requirements_file_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dependencies.append(line)

    return dependencies


def extract_dependencies_from_pyproject_toml(
    pyproject_file_content: str,
) -> list[str]:
    pyproject_data = tomli.loads(pyproject_file_content)
    dependencies = []
    dependencies.extend(pyproject_data.get("project", {}).get("dependencies", []))

    return dependencies


###################
# Impure Functions
###################


def pin_python_dependency_in_string(dependency_str: str, cutoff_date: datetime) -> str:
    """
    Pins a single Python dependency string to a specific version based on the cutoff date.

    Examples of input strings:
    - requests
    - requests>=2.25.1
    - requests[socks]
    - requests[socks]>=2.25.1

    Examples of output strings:
    - requests==2.25.1
    - requests[socks]==2.25.1
    """

    try:
        python_dependency = Requirement(dependency_str)
    except InvalidRequirement as e:
        logging.error(f"Invalid requirement string '{dependency_str}': {e}")
        return dependency_str

    if python_dependency.specifier:
        # Already has a version specifier, no need to pin
        return dependency_str

    version = get_latest_version_on_pypi_until_date(python_dependency.name, cutoff_date)
    if version:
        python_dependency.specifier = SpecifierSet(f"=={version}")
        return str(python_dependency)
    else:
        raise ValueError(
            f"Could not find a version for package '{python_dependency.name}' on PyPI before {cutoff_date.isoformat()}"
        )


def get_pypi_package_info(package_name: str) -> PYPIPackageInfo:
    pypi_url = f"https://pypi.org/pypi/{package_name}/json"

    try:
        response = requests.get(pypi_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching data from PyPI for package {package_name}: {e}")
        raise e

    pypi_data = response.json()
    releases = {}

    for version in pypi_data.get("releases", {}):
        if len(pypi_data["releases"][version]) > 0:
            pypi_package_release = PYPIPackageRelease.model_validate(
                pypi_data["releases"][version][0]
            )
            releases[version] = pypi_package_release

    pypi_package_info = PYPIPackageInfo(name=package_name, releases=releases)

    return pypi_package_info
