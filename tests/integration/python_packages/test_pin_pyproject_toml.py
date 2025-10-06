
from datetime import datetime

from repo2ree.python_packages_util.pin_pypi_package_version import (
    pin_package_versions_in_pyproject_toml,
)

def test_pin_pyproject_toml(snapshot, resources_dir):

    pyproject_file = resources_dir / "pyproject.toml"
    cutoff_date = datetime(2025, 1, 1)

    pinned_pyproject = pin_package_versions_in_pyproject_toml(pyproject_file.read_text(), cutoff_date)

    assert pinned_pyproject == snapshot