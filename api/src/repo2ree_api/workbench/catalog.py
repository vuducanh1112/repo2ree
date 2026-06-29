"""Catalog of base images offered for workbench provisioning.

Single source of truth for which images the UI can pick from and which one a
provisioning request defaults to when it omits an image. A deployment may still
override the *default* image via the ``WORKBENCH_IMAGE`` env var (see settings)
— handy for driving a locally-built image in tests/dev without editing this
list.
"""

from __future__ import annotations

from pydantic import BaseModel


class WorkbenchImage(BaseModel):
    id: str
    ref: str
    label: str
    description: str


# Ordered; the first entry is the default offered when a request omits an image.
WORKBENCH_IMAGE_CATALOG: tuple[WorkbenchImage, ...] = (
    WorkbenchImage(
        id="standard",
        ref="docker.io/vuducanh1112/repo2ree-workbench:edge",
        label="Standard",
        description="Default workbench toolchain.",
    ),
)


def default_workbench_image() -> WorkbenchImage:
    """The image used when a provisioning request doesn't specify one."""
    return WORKBENCH_IMAGE_CATALOG[0]
