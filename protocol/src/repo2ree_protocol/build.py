"""Build identity shared by every repo2ree component."""

from __future__ import annotations

import os
from importlib import metadata

from pydantic import BaseModel, ConfigDict

BUILD_REVISION_ENV = "REPO2REE_BUILD_REVISION"


class BuildInfo(BaseModel):
    """A component's package version and exact source revision.

    Both fields are optional on the wire so independently deployed third-party
    providers and workbenches remain compatible.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    version: str = ""
    revision: str = ""


def current_build(distribution: str) -> BuildInfo:
    """Return build identity without consulting git at runtime."""

    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        version = ""
    return BuildInfo(version=version, revision=os.environ.get(BUILD_REVISION_ENV, "").strip())
