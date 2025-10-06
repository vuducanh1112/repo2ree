
from repo2ree.python_packages_util.pin_conda_package_version import (
    pin_package_versions_in_environment_yml,
)
from datetime import datetime

def test_pin_environment_yml(snapshot, resources_dir):

    environment_file = resources_dir / "environment.yml"
    cutoff_date = datetime(2025, 1, 1)

    pinned_environment = pin_package_versions_in_environment_yml(environment_file.read_text(), cutoff_date)

    assert pinned_environment == snapshot