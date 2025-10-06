
from datetime import datetime
from pathlib import Path


from repo2ree.dockerfile_utils.pin_versions import pin_dockerfile_base_image_and_packages
from repo2ree.dockerfile_utils.validate import is_dockerfile_buildable

def test_pin_dockerfile(snapshot, resources_dir, tmp_path):

    dockerfile_path = resources_dir / "Dockerfile"
    dockerfile_contents = dockerfile_path.read_text()

    cutoff_date = datetime(2025, 1, 1)

    pinned_dockerfile_contents = pin_dockerfile_base_image_and_packages(dockerfile_contents, cutoff_date)

    tmp_dockerfile_path = tmp_path / "Dockerfile"
    tmp_dockerfile_path.write_text(pinned_dockerfile_contents)
    
    assert pinned_dockerfile_contents == snapshot
    assert is_dockerfile_buildable(Path("pinned-Dockerfile"))