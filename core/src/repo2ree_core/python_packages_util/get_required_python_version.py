from datetime import datetime
from packaging.version import Version


def get_python_version_until_date(target_date: datetime) -> Version:
    PYTHON_RELEASES: dict[str, datetime] = {
        "3.6": datetime.strptime("2016-12-23", "%Y-%m-%d"),
        "3.7": datetime.strptime("2018-06-27", "%Y-%m-%d"),
        "3.8": datetime.strptime("2019-10-14", "%Y-%m-%d"),
        "3.9": datetime.strptime("2020-10-05", "%Y-%m-%d"),
        "3.10": datetime.strptime("2021-10-04", "%Y-%m-%d"),
        "3.11": datetime.strptime("2022-10-24", "%Y-%m-%d"),
        "3.12": datetime.strptime("2023-10-02", "%Y-%m-%d"),
        "3.13": datetime.strptime("2024-10-01", "%Y-%m-%d"),
        "3.14": datetime.strptime("2025-10-06", "%Y-%m-%d"),
    }

    available_versions = [
        Version(version)
        for version, release_date in PYTHON_RELEASES.items()
        if release_date <= target_date
    ]

    if not available_versions:
        raise ValueError(
            f"No Python versions found released before {target_date.isoformat()}"
        )

    python_version = max(available_versions)

    return python_version
