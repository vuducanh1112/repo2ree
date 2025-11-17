import logging
from pathlib import Path
from datetime import datetime
import tempfile

from repo2ree.dockerfile_utils.extract_files import extract_file_from_image
from repo2ree.dockerfile_utils.pin_versions import pin_base_image
from repo2ree.dockerfile_utils.build_image import (
    build_docker_image,
    save_image_to_tar,
    unify_build_contexts,
)
from repo2ree.python_packages_util.extract_python_version import get_required_python

import tomli

CONDA_BASE_IMAGE = "continuumio/miniconda3:latest"
UV_BASE_IMAGE = "ghcr.io/astral-sh/uv:debian"


def generate_dockerfile_and_build_image(
    repo_path: Path, cutoff_date: datetime, output_dir: Path
) -> Path | None:
    ##############
    assert repo_path.exists(), "Repository path must exist."
    assert output_dir.exists(), "Output directory must exist."
    ##############

    dockerfile_path = output_dir / "Dockerfile-ree"

    dockerfile_contents = generate_dockerfile(repo_path, cutoff_date)

    print("Generated Dockerfile contents:")
    print(dockerfile_contents)

    dockerfile_path.write_text(dockerfile_contents)

    build_contexts = []
    build_contexts.append(repo_path)

    tmp_dir = None
    if (
        not (repo_path / "environment.yml").exists()
        and not (repo_path / "pyproject.toml").exists()
    ):
        pyproject_contents = generate_uv_pyprojecttoml(repo_path, cutoff_date)
        tmp_dir = tempfile.TemporaryDirectory()
        tmp_pyproject_toml = Path(tmp_dir.name) / "pyproject.toml"
        tmp_pyproject_toml.write_text(pyproject_contents)
        build_contexts.append(Path(tmp_dir.name))
        print(f"Created temporary pyproject.toml at: {tmp_pyproject_toml}")
        print(tmp_pyproject_toml.read_text())

    with unify_build_contexts(build_contexts) as temp_build_context:
        print(f"Temporary build context created at: {temp_build_context}")
        temp_build_context_path = Path(temp_build_context)
        image = build_docker_image(temp_build_context_path, dockerfile_path)

    if tmp_dir:
        tmp_dir.cleanup()

    if image is None:
        logging.error("Failed to build Docker image.")
        return None

    if (repo_path / "pyproject.toml").exists():
        extract_file_from_image(
            image.id, "/app/uv.lock", str(output_dir / "extracted_uv.lock")
        )
        extract_file_from_image(
            image.id,
            "/app/pyproject.toml",
            str(output_dir / "extracted_pyproject.toml"),
        )

    save_image_to_tar(image, output_dir / "ree.tar")

    ##############
    assert Path(output_dir / "Dockerfile-ree").exists(), (
        "Output Dockerfile was not created."
    )
    assert Path(output_dir / "ree.tar").exists(), "Output tar file was not created."
    ##############

    return output_dir


def generate_dockerfile(repo_path: Path, cutoff_date: datetime) -> str:
    dockerfile_contents = ""

    if (repo_path / "environment.yml").exists():
        base_image = pin_base_image(CONDA_BASE_IMAGE, datetime.now())
        dockerfile_contents += f"FROM {base_image}\n"
        dockerfile_contents += "COPY . /app\n"
        dockerfile_contents += "WORKDIR /app\n"
        # dockerfile_contents += "RUN conda env create -f environment.yml\n"
        dockerfile_contents += (
            "RUN conda install --channel=conda-forge --name=base conda-lock\n"
        )
        dockerfile_contents += (
            "RUN conda-lock -f environment.yml -p osx-64 -p linux-64\n"
        )

    else:
        if (repo_path / "pyproject.toml").exists():
            pyproject_file = repo_path / "pyproject.toml"
            with open(pyproject_file, "rb") as f:
                data = tomli.load(f)
            # check if poetry is used
            if "tool" in data and "poetry" in data["tool"]:
                print("Detected poetry project.")
                return ""
            else:
                base_image = pin_base_image(UV_BASE_IMAGE, datetime.now())
                dockerfile_contents += f"FROM {base_image}\n"
                dockerfile_contents += "COPY . /app\n"
                dockerfile_contents += "WORKDIR /app\n"
                dockerfile_contents += "RUN uv sync\n"

        else:
            if (repo_path / "requirements.txt").exists():
                base_image = pin_base_image(UV_BASE_IMAGE, datetime.now())
                dockerfile_contents += f"FROM {base_image}\n"
                dockerfile_contents += "COPY . /app\n"
                dockerfile_contents += "WORKDIR /app\n"
                dockerfile_contents += "RUN uv add -r requirements.txt\n"
                dockerfile_contents += "RUN uv sync\n"

    dockerfile_contents += 'CMD ["/bin/bash"]\n'

    return dockerfile_contents


def generate_uv_pyprojecttoml(repo_path: Path, exclude_newer: datetime) -> str:
    pyproject_contents = ""

    required_python = get_required_python(repo_path, exclude_newer)

    pyproject_contents += "[project]\n"
    pyproject_contents += f'name = "{repo_path.name}"\n'
    pyproject_contents += 'version = "0.1.0"\n'
    pyproject_contents += 'description = ""\n'
    if required_python:
        pyproject_contents += f'requires-python = "{required_python}"\n'
    pyproject_contents += "\n"

    pyproject_contents += "[tool.uv]\n"
    pyproject_contents += (
        f'exclude-newer = "{exclude_newer.strftime("%Y-%m-%dT%H:%M:%SZ")}"\n'
    )

    return pyproject_contents
