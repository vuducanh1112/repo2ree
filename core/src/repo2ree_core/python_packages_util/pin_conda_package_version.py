import json
import logging
from datetime import UTC, datetime
from typing import Final

import requests
import yaml
from packaging.version import Version
from pydantic import BaseModel

from repo2ree_core.python_packages_util.pin_pypi_package_version import (
    pin_python_dependency_in_string,
)

logger = logging.getLogger(__name__)

###################
# Constants
###################

ANACONDA_API_URL: Final = "https://api.anaconda.org/package"

###################
# Data Models
###################


class AnacondaPackageInfo(BaseModel):
    name: str
    id: str
    package_types: list[str]
    summary: str
    description: str
    home: str
    public: bool
    owner: dict
    full_name: str
    url: str
    html_url: str
    versions: list[str]
    latest_version: str
    platforms: dict
    conda_platforms: list[str]
    revision: int
    license: str
    license_url: str
    dev_url: str
    doc_url: str
    source_git_url: str
    source_git_tag: str
    app_entry: dict
    app_type: dict
    app_summary: dict
    builds: list[str]
    releases: list[dict]
    watchers: int
    upvoted: bool
    created_at: str
    modified_at: str
    files: list["AnacondaPackageFileInfo"]


class AnacondaPackageFileInfo(BaseModel):
    description: str
    dependencies: dict
    distribution_type: str
    basename: str
    attrs: dict
    upload_time: str
    md5: str
    sha256: str
    size: int
    full_name: str
    download_url: str
    type: str
    version: str
    ndownloads: int
    owner: str
    labels: list[str]


###################
# Main Functions
###################


def pin_package_versions_in_environment_yml(environment_file_content: str, cutoff_date: datetime) -> str:
    conda_env_data = yaml.safe_load(environment_file_content)

    channels = conda_env_data.get("channels", [])
    dependencies = conda_env_data.get("dependencies", [])
    conda_dependencies = []
    pip_dependencies = []
    for dep in dependencies:
        if isinstance(dep, str):
            conda_dependencies.append(dep)
        elif isinstance(dep, dict) and "pip" in dep:
            pip_dependencies.extend(dep["pip"])

    pinned_conda_dependencies = []
    for dep in conda_dependencies:
        if "=" in dep or "<" in dep or ">" in dep or "~" in dep:
            pinned_conda_dependencies.append(dep)
        else:
            version = get_anaconda_package_version_until_date(dep, cutoff_date, channels)
            if version:
                pinned_conda_dependencies.append(f"{dep}={version}")
            else:
                pinned_conda_dependencies.append(dep)

    pinned_pip_dependencies = []
    for dep in pip_dependencies:
        pinned_pip_dependencies.append(pin_python_dependency_in_string(dep, cutoff_date))

    pinned_env_data = conda_env_data.copy()
    pinned_env_data["dependencies"] = pinned_conda_dependencies
    if pip_dependencies:
        pinned_env_data["dependencies"].append({"pip": pinned_pip_dependencies})

    pinned_environment_file_content = yaml.dump(pinned_env_data, sort_keys=False)
    return pinned_environment_file_content


def get_anaconda_package_version_until_date(package_name: str, cutoff_date: datetime, channels: list[str]) -> str:
    # Ensure cutoff_date is timezone-aware (UTC)
    if cutoff_date.tzinfo is None or cutoff_date.tzinfo.utcoffset(cutoff_date) is None:
        cutoff_date = cutoff_date.replace(tzinfo=UTC)

    anaconda_channels_data = get_anaconda_package_data(package_name, channels)

    for channel, data in anaconda_channels_data.items():
        if not data:
            continue

        package_info = parse_anaconda_response(data)

        file_infos_by_version: dict[str, AnacondaPackageFileInfo] = {}
        for file_info in package_info.files:
            file_infos_by_version[file_info.version] = file_info

        sorted_versions = sorted(file_infos_by_version.keys(), key=lambda v: Version(v), reverse=True)
        for version in sorted_versions:
            file_info = file_infos_by_version[version]
            upload_time = datetime.strptime(file_info.upload_time, "%Y-%m-%d %H:%M:%S.%f%z")
            if upload_time <= cutoff_date:
                logger.info(
                    "Found version '%s' on channel '%s' uploaded at %s",
                    version,
                    channel,
                    upload_time.isoformat(),
                )
                return version

    return ""


def extract_conda_environment_dependencies(
    environment_file_content: str,
) -> dict:
    conda_env_data = yaml.safe_load(environment_file_content)

    channels = conda_env_data.get("channels", [])
    dependencies = conda_env_data.get("dependencies", [])
    conda_dependencies = []
    pip_dependencies = []
    for dep in dependencies:
        if isinstance(dep, str):
            conda_dependencies.append(dep)
        elif isinstance(dep, dict) and "pip" in dep:
            pip_dependencies.extend(dep["pip"])

    return {
        "channels": channels,
        "conda_dependencies": conda_dependencies,
        "pip_dependencies": pip_dependencies,
    }


###################
# Impure Functions
###################


def get_anaconda_package_data(package_name: str, channels: list[str]) -> dict:
    """
    Programmatically fetches all available versions for a package across specified Conda channels.

    Args:
        package_name: The name of the package (e.g., 'numpy', 'pytorch').

    Returns:
        A dictionary where keys are the channel names and values are lists of
        unique versions found on that channel.
    """

    anaconda_channels_data: dict[str, dict] = {channel: dict() for channel in channels}

    logger.info("Searching for package '%s' across channels: %s", package_name, ", ".join(channels))

    for channel in channels:
        api_url = f"{ANACONDA_API_URL}/{channel}/{package_name}"

        try:
            response = requests.get(api_url, timeout=10)

            response.raise_for_status()

            data = response.json()
            # Path("debug_anaconda_response.json").write_text(json.dumps(data, indent=2))

            anaconda_channels_data[channel] = data

        except requests.exceptions.HTTPError as e:
            # A 404 (Not Found) is common if the package isn't in that specific channel
            if e.response.status_code == 404:
                logger.debug("Package not found on channel '%s' (404).", channel)
            else:
                logger.warning("Error accessing channel '%s': HTTP Error %s", channel, e.response.status_code)
        except requests.exceptions.RequestException as e:
            logger.error("An error occurred while connecting to Anaconda API for channel '%s': %s", channel, e)
        except json.JSONDecodeError:
            logger.error("Received non-JSON response from channel '%s'.", channel)

    return anaconda_channels_data


###################
# Pure Functions
###################


def parse_anaconda_response(data: dict) -> AnacondaPackageInfo:
    """
    Parses the JSON response from the Anaconda API into an AnacondaPackageInfo object.
    """

    anaconda_package_files = []
    for file_data in data.get("files", []):
        anaconda_package_file_info = AnacondaPackageFileInfo(
            description=file_data.get("description") or "",
            dependencies=file_data.get("dependencies", {}) if isinstance(file_data.get("dependencies"), dict) else {},
            distribution_type=file_data.get("distribution_type") or "",
            basename=file_data.get("basename") or "",
            attrs=file_data.get("attrs") or {},
            upload_time=file_data.get("upload_time") or "",
            md5=file_data.get("md5") or "",
            sha256=file_data.get("sha256") or "",
            size=file_data.get("size") if file_data.get("size") is not None else 0,
            full_name=file_data.get("full_name") or "",
            download_url=file_data.get("download_url") or "",
            type=file_data.get("type") or "",
            version=file_data.get("version") or "",
            ndownloads=file_data.get("ndownloads") if file_data.get("ndownloads") is not None else 0,
            owner=file_data.get("owner") or "",
            labels=file_data.get("labels") or [],
        )
        anaconda_package_files.append(anaconda_package_file_info)

    anaconda_package_info = AnacondaPackageInfo(
        name=data.get("name") or "",
        id=data.get("id") or "",
        package_types=data.get("package_types") or [],
        summary=data.get("summary") or "",
        description=data.get("description") or "",
        home=data.get("home") or "",
        public=data.get("public", False) if data.get("public") is not None else False,
        owner=data.get("owner") or {},
        full_name=data.get("full_name") or "",
        url=data.get("url") or "",
        html_url=data.get("html_url") or "",
        versions=data.get("versions") or [],
        latest_version=data.get("latest_version") or "",
        platforms=data.get("platforms") or {},
        conda_platforms=data.get("conda_platforms") or [],
        revision=data.get("revision") or 0,
        license=data.get("license") or "",
        license_url=data.get("license_url") or "",
        dev_url=data.get("dev_url") or "",
        doc_url=data.get("doc_url") or "",
        source_git_url=data.get("source_git_url") or "",
        source_git_tag=data.get("source_git_tag") or "",
        app_entry=data.get("app_entry") or {},
        app_type=data.get("app_type") or {},
        app_summary=data.get("app_summary") or {},
        builds=data.get("builds") or [],
        releases=data.get("releases") or [],
        watchers=data.get("watchers", 0) if data.get("watchers") is not None else 0,
        upvoted=data.get("upvoted", False) if data.get("upvoted") is not None else False,
        created_at=data.get("created_at") or "",
        modified_at=data.get("modified_at") or "",
        files=anaconda_package_files,
    )

    return anaconda_package_info
