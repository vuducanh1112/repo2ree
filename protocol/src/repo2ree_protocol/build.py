from __future__ import annotations

import os
from importlib import metadata

from pydantic import BaseModel, ConfigDict

BUILD_REVISION_ENV = "REPO2REE_BUILD_REVISION"


class BuildInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    version: str = ""
    revision: str = ""


def current_build(distribution: str) -> BuildInfo:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        version = ""
    return BuildInfo(version=version, revision=os.environ.get(BUILD_REVISION_ENV, "").strip())
