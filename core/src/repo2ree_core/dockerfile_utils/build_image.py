import logging
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import docker
import docker.models
import docker.models.images

logger = logging.getLogger(__name__)


def build_docker_image(build_context: Path, dockerfile: Path) -> docker.models.images.Image | None:
    dockerfile = dockerfile.resolve()

    logger.info("Attempting to build Dockerfile: %s in build context: %s", dockerfile, build_context)
    for root, _dirs, files in os.walk(build_context):
        for name in files:
            logger.debug("%s", os.path.abspath(os.path.join(root, name)))

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
                logger.debug("%s", value)

        logger.info("Build successful!")
        return image

    except docker.errors.BuildError as e:
        logger.error("Build failed: %s", e)

        if hasattr(e, "build_log"):
            log_lines = [(item.get("stream") or item.get("error") or "").strip() for item in e.build_log]
            full_log = "\n".join(filter(None, log_lines))
            logger.error("%s", full_log)

        return None
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)
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
