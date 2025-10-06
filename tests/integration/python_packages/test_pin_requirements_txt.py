
from datetime import datetime
from pathlib import Path

from repo2ree.python_packages_util.pin_pypi_package_version import pin_package_versions_in_requirements_txt



def test_pin_requirements_txt(snapshot, resources_dir: Path):

    requirements_file = resources_dir / "requirements.txt"
    cutoff_date = datetime(2025, 1, 1)

    pinned_requirements = pin_package_versions_in_requirements_txt(requirements_file.read_text(), cutoff_date)

    assert pinned_requirements == snapshot