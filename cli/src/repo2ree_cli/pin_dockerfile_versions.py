from datetime import datetime
from pathlib import Path

import click

from repo2ree.cli.cli import cli as repo2ree_cli
from repo2ree.core.dockerfile_utils.pin_versions import (
    pin_dockerfile_base_image_and_packages,
)


@repo2ree_cli.command()
@click.option(
    "-f",
    "--dockerfile",
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    default="./Dockerfile",
    help="Path to the Dockerfile to be processed.",
)
@click.option(
    "--cutoff_date",
    help="Cutoff date in YYYY-MM-DD format. If none is provided, defaults to today.",
)
@click.option(
    "-o",
    "--output_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to save the pinned Dockerfile. If a directory, the pinned Dockerfile be saved in that directory with the name Dockerfile_pinned. If a file path, the pinned environment.yml file will be saved at that exact location. Defaults to parent directory of the input environment.yml file.",
)
def pin_dockerfile(dockerfile: str, cutoff_date: str, output_path: str):
    """
    Command-line interface to pin versions in a Dockerfile based on a cutoff date.
    This will 1) pin the base image to a specific digest and 2) pin package versions of various package managers.
    """

    _dockerfile = Path(dockerfile)
    if not _dockerfile.exists():
        print(f"Error: The specified Dockerfile does not exist: {_dockerfile}")
        return

    _cutoff_date: datetime

    if cutoff_date:
        try:
            _cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d")
        except ValueError:
            print(
                "Error: cutoff_date must be in YYYY-MM-DD format. Defaulting to today instead."
            )
            _cutoff_date = datetime.now()
    else:
        _cutoff_date = datetime.now()

    if not output_path:
        _ouput_path = _dockerfile.parent
    else:
        _ouput_path = Path(output_path)
    if _ouput_path.is_dir():
        pinned_dockerfile_path = (
            _ouput_path / f"{_dockerfile.stem}_pinned{_dockerfile.suffix}"
        )
    else:
        pinned_dockerfile_path = _ouput_path

    dockerfile_path = Path(dockerfile)
    dockerfile_contents = dockerfile_path.read_text()

    try:
        pinned_dockerfile_contents = pin_dockerfile_base_image_and_packages(
            dockerfile_contents, _cutoff_date
        )
        print(pinned_dockerfile_contents)

        pinned_dockerfile_path.write_text(pinned_dockerfile_contents)

        print(f"Pinned Dockerfile written to: {pinned_dockerfile_path}")
    except Exception as e:
        print(f"An error occurred while pinning the Dockerfile: {e}")
