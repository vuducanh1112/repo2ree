import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import docker
import docker.models
import docker.models.images


def build_docker_image(build_context: Path, dockerfile: Path) -> docker.models.images.Image | None:
    dockerfile = dockerfile.resolve()

    print(f"Attempting to build Dockerfile: {dockerfile} in build context: {build_context}")
    for root, _dirs, files in os.walk(build_context):
        for name in files:
            print(os.path.abspath(os.path.join(root, name)))

    try:
        client = docker.from_env()

        response = client.images.build(
            path=str(build_context),
            dockerfile=str(dockerfile),
            nocache=True,
            rm=True,
            forcerm=True,
            timeout=600,
        )

        image, build_log = response
        for chunk in build_log:
            for _key, value in chunk.items():
                print(value, end="")

        print("\nBuild successful!")
        return image

    except docker.errors.BuildError as e:
        print(f"\nBuild failed: {e}")

        if hasattr(e, "build_log"):
            log_lines = [(item.get("stream") or item.get("error") or "").strip() for item in e.build_log]

            full_log = "\n".join(filter(None, log_lines))
            print(full_log)

        return None
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return None


def unify_build_contexts(build_contexts_to_unify: list[Path]) -> TemporaryDirectory:
    # copy all specified build contexts into a single temporary directory
    temp_dir = TemporaryDirectory()
    temp_path = Path(temp_dir.name).resolve()

    for context in build_contexts_to_unify:
        for item in context.iterdir():
            dest = temp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    return temp_dir


def save_image_to_tar(image: docker.models.images.Image, tar_path: Path) -> Path:
    """
    Saves a Docker image to a tar file.

    Args:
        image (docker.models.images.Image): The Docker image to save.
        tar_path (Path): The path where the tar file will be saved.
    """
    with open(tar_path, "wb") as tar_file:
        for chunk in image.save(named=True):
            tar_file.write(chunk)

    return tar_path
