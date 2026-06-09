import logging
from enum import Enum

import docker
import docker.errors
from pydantic import BaseModel

logger = logging.getLogger(__name__)

###################
# Data Models
###################


class OSReleaseID(Enum):
    DEBIAN = "debian"
    UBUNTU = "ubuntu"
    ARCH = "arch"


class OSReleaseInfo(BaseModel):
    pretty_name: str
    name: str
    version_id: str
    version: str
    version_code_name: str
    id: OSReleaseID


###################
# Impure Functions
###################


def get_os_release_lightweight(image_name: str) -> tuple[str, str]:
    """
    Reads /etc/os-release from a Docker image in a lightweight manner.
    Since it is already starting a docker container, also returns the architecture.

    returns a tuple of (architecture, os_release_str)
    """
    client = docker.from_env()

    try:
        shell_command = "dpkg --print-architecture; cat /etc/os-release"
        container_output_bytes = client.containers.run(
            image=image_name,
            entrypoint="sh",
            command=["-c", shell_command],
            remove=True,
            detach=False,
        )
        container_output = container_output_bytes.decode("utf-8")
        # split into first line and rest
        architecture, os_release_str = container_output.split("\n", 1)

        return architecture, os_release_str

    except docker.errors.ImageNotFound:
        logger.error("Image '%s' not found.", image_name)
        return "", ""
    except Exception as e:
        logger.error("An error occurred: %s", e)
        return "", ""


def get_docker_image_digest(image_name: str) -> str | None:
    client = docker.from_env()

    try:
        # Pull or get the image from the local machine
        image = client.images.get(image_name)

        # Check for digests
        if not image.attrs.get("RepoDigests"):
            logger.info("Image %s has no digest. Pulling the image...", image_name)
            image = client.images.pull(image_name)

        # A list of digests is returned, but for tagged images,
        # the first one is typically the one you want.
        digest = image.attrs["RepoDigests"][0]
        return digest

    except docker.errors.ImageNotFound:
        logger.info("Image %s not found locally. Pulling it from the registry...", image_name)
        image = client.images.pull(image_name)

        # After a pull, the digest should be available.
        if image.attrs.get("RepoDigests"):
            digest = image.attrs["RepoDigests"][0]
            return digest
        else:
            return None
    except docker.errors.APIError as e:
        logger.error("An API error occurred: %s", e)
        return None


###################
# Pure Functions
###################


def parse_os_release(os_release_str: str) -> OSReleaseInfo:
    """
    Parses the content of /etc/os-release into an OSReleaseInfo object.
    """
    info = {}
    for line in os_release_str.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key] = value.strip('"')

    os_release_info = OSReleaseInfo(
        pretty_name=info.get("PRETTY_NAME", ""),
        name=info.get("NAME", ""),
        version_id=info.get("VERSION_ID", ""),
        version=info.get("VERSION", ""),
        version_code_name=info.get("VERSION_CODENAME", ""),
        id=OSReleaseID(info.get("ID", "")),
    )

    return os_release_info
