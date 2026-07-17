"""The workbench image catalog route.

Which images the UI can pick from — and which one a provisioning request defaults
to when it omits one — is configured on ``Settings.WORKBENCH_IMAGE_CATALOG`` (see
settings.py), so a deployment can serve a different set (e.g. a locally-built
image) via env without touching code. This module reads that catalog and serves
it. To drive a one-off image, pass it as ``workbench_image`` on the provision
request instead.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.settings import WorkbenchImage, service_settings

# The configured catalog, resolved once at import. Ordered; the first entry is the
# default offered when a request omits an image.
WORKBENCH_IMAGE_CATALOG: tuple[WorkbenchImage, ...] = service_settings.WORKBENCH_IMAGE_CATALOG


def default_workbench_image() -> WorkbenchImage:
    """The image used when a provisioning request doesn't specify one."""
    return WORKBENCH_IMAGE_CATALOG[0]


workbench_images_router = APIRouter(tags=["fleet"])


class WorkbenchImageCatalog(BaseModel):
    images: list[WorkbenchImage]
    default_id: str


@workbench_images_router.get(
    "/api/v1/workbench/images",
    operation_id="listWorkbenchImages",
    response_model=WorkbenchImageCatalog,
    responses=ERROR_RESPONSES,
)
def list_workbench_images() -> WorkbenchImageCatalog:
    """The base images the frontend offers at provision time."""
    return WorkbenchImageCatalog(
        images=list(WORKBENCH_IMAGE_CATALOG),
        default_id=default_workbench_image().id,
    )
