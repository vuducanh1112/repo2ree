"""Workbench-level routes (not scoped to a single REE)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from repo2ree_api.workbench.catalog import (
    WORKBENCH_IMAGE_CATALOG,
    WorkbenchImage,
    default_workbench_image,
)

workbench_router = APIRouter()


class WorkbenchImageCatalog(BaseModel):
    images: list[WorkbenchImage]
    defaultId: str


@workbench_router.get("/api/v1/workbench/images")
def list_workbench_images() -> WorkbenchImageCatalog:
    """The base images the frontend offers at provision time."""
    return WorkbenchImageCatalog(
        images=list(WORKBENCH_IMAGE_CATALOG),
        defaultId=default_workbench_image().id,
    )
