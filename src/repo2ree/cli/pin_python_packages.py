
from pathlib import Path
from datetime import datetime

import click

from repo2ree.cli.cli import cli as repo2ree_cli
from repo2ree.python_packages_util.pin_pypi_package_version import (
    pin_package_versions_in_requirements_txt,
    pin_package_versions_in_pyproject_toml,
)
from repo2ree.python_packages_util.pin_conda_package_version import (
    pin_package_versions_in_environment_yml,
)


@repo2ree_cli.command()
@click.option('-f', '--requirements_file', type=click.Path(exists=True, dir_okay=False, file_okay=True), default="./requirements.txt", help='Path to the requirements.txt file to be processed. Defaults to ./requirements.txt')
@click.option('--cutoff_date', help='Cutoff date in YYYY-MM-DD format. If none is provided, defaults to today.')
@click.option('-o', '--output_path', type=click.Path(exists=True), help='Can be a directory or a file path. If a directory, the pinned requirements file will be saved in that directory with the name <original_name>_pinned.txt. If a file path, the pinned requirements file will be saved at that exact location. Defaults parent directory of the input requirements file.')
def pin_requirements_txt(requirements_file: str, cutoff_date: str, output_path: str):
    """
    Pin Python package versions in a requirements.txt file.
    """

    _requirements_file = Path(requirements_file)
    if not _requirements_file.exists():
        print(f"Error: The specified requirements file does not exist: {_requirements_file}")
        return

    _cutoff_date: datetime
    if cutoff_date:
        try:
            _cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d")
        except ValueError:
            print("Error: cutoff_date must be in YYYY-MM-DD format. Defaulting to today instead.")
            _cutoff_date = datetime.now()
    else:
        _cutoff_date = datetime.now()

    if not output_path:
        _ouput_path = _requirements_file.parent
    else:
        _ouput_path = Path(output_path)
    if _ouput_path.is_dir():
        pinned_requirements_file_path = _ouput_path / f"{_requirements_file.stem}_pinned{_requirements_file.suffix}"
    else:
        pinned_requirements_file_path = _ouput_path


    requirements_file_content = _requirements_file.read_text()
    pinned_requirements_file_content = pin_package_versions_in_requirements_txt(requirements_file_content, _cutoff_date)
    pinned_requirements_file_path.write_text(pinned_requirements_file_content)
    print(f"Pinned requirements file created at: {pinned_requirements_file_path}")


@repo2ree_cli.command()
@click.option('-f', '--pyproject_file', type=click.Path(exists=True, dir_okay=False, file_okay=True), default="./pyproject.toml", help='Path to the pyproject.toml file to be processed. Defaults to ./pyproject.toml')
@click.option('--cutoff_date', help='Cutoff date in YYYY-MM-DD format. If none is provided, defaults to today.')
@click.option('-o', '--output_path', type=click.Path(exists=True, file_okay=False, dir_okay=True), help='Path to save the pinned pyproject.toml file. If a directory, the pinned pyproject.toml file will be saved in that directory with the name <original_name>_pinned.toml. If a file path, the pinned pyproject.toml file will be saved at that exact location. Defaults to parent directory of the input pyproject.toml file.')
def pin_pyproject_toml(pyproject_file: str, cutoff_date: str, output_path: str):
    """
    Pin Python package versions in a pyproject.toml file.
    """

    _requirements_file = Path(pyproject_file)
    if not _requirements_file.exists():
        print(f"Error: The specified requirements file does not exist: {_requirements_file}")
        return

    _cutoff_date: datetime
    if cutoff_date:
        try:
            _cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d")
        except ValueError:
            print("Error: cutoff_date must be in YYYY-MM-DD format. Defaulting to today instead.")
            _cutoff_date = datetime.now()
    else:
        _cutoff_date = datetime.now()

    if not output_path:
        _ouput_path = _requirements_file.parent
    else:
        _ouput_path = Path(output_path)
    if _ouput_path.is_dir():
        pinned_pyproject_file_path = _ouput_path / f"{_requirements_file.stem}_pinned{_requirements_file.suffix}"
    else:
        pinned_pyproject_file_path = _ouput_path

    pyproject_file_content = _requirements_file.read_text()
    pinned_pyproject_file_content = pin_package_versions_in_pyproject_toml(pyproject_file_content, _cutoff_date)
    pinned_pyproject_file_path.write_text(pinned_pyproject_file_content)
    print(f"Pinned requirements file created at: {pinned_pyproject_file_path}")


@repo2ree_cli.command()
@click.option('-f', '--environment_yml_file', type=click.Path(exists=True, dir_okay=False, file_okay=True), default="./environment.yml", help='Path to the conda environment.yml file to be processed. Defaults to ./environment.yml')
@click.option('--cutoff_date', help='Cutoff date in YYYY-MM-DD format. If none is provided, defaults to today.')
@click.option('-o', '--output_path', type=click.Path(exists=True, file_okay=False, dir_okay=True), help='Path to save the pinned environment.yml file. If a directory, the pinned environment.yml file will be saved in that directory with the name <original_name>_pinned.yml. If a file path, the pinned environment.yml file will be saved at that exact location. Defaults to parent directory of the input environment.yml file.')
def pin_environment_yml(environment_yml_file: str, cutoff_date: str, output_path: str):
    """
    Pin package versions in a conda environment.yml file.
    """

    _environment_yml_file = Path(environment_yml_file)
    if not _environment_yml_file.exists():
        print(f"Error: The specified environment.yml file does not exist: {_environment_yml_file}")
        return

    _cutoff_date: datetime
    if cutoff_date:
        try:
            _cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d")
        except ValueError:
            print("Error: cutoff_date must be in YYYY-MM-DD format. Defaulting to today instead.")
            _cutoff_date = datetime.now()
    else:
        _cutoff_date = datetime.now()

    if not output_path:
        _ouput_path = _environment_yml_file.parent
    else:
        _ouput_path = Path(output_path)
    if _ouput_path.is_dir():
        pinned_environment_yml_file_path = _ouput_path / f"{_environment_yml_file.stem}_pinned{_environment_yml_file.suffix}"
    else:
        pinned_environment_yml_file_path = _ouput_path

    environment_yml_file_content = _environment_yml_file.read_text()
    pinned_environment_yml_file_content = pin_package_versions_in_environment_yml(environment_yml_file_content, _cutoff_date)
    pinned_environment_yml_file_path.write_text(pinned_environment_yml_file_content)
    print(f"Pinned environment.yml file created at: {pinned_environment_yml_file_path}")