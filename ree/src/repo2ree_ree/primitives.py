from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from repo2ree_ree.digest import Digest
from repo2ree_ree.instant import UtcInstant, format_utc_instant, parse_utc_instant
from repo2ree_ree.paths import validate_path_segment, validate_relative_path
from repo2ree_ree.scalar import StringValue

SourceType = Literal["", "git", "hg", "svn", "cvs", "bzr", "tarball", "zip"]


class RunId(StringValue):
    @classmethod
    def validate(cls, value: str) -> str:
        return validate_path_segment(value, kind="run_id")


class ReePath(StringValue):
    """A relative path; ``RELATIVE_TO`` names the entries of the REE tree it is resolved under, in order."""

    RELATIVE_TO: ClassVar[tuple[str, ...]] = (".",)

    @classmethod
    def validate(cls, value: str) -> str:
        validate_relative_path(value)
        return value

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        found: dict[str, Any] = handler(schema)
        return found | {"x-relative-to": list(cls.RELATIVE_TO)}


class OverlayPath(ReePath):
    RELATIVE_TO: ClassVar[tuple[str, ...]] = ("overlay",)


class WorkspacePath(ReePath):
    RELATIVE_TO: ClassVar[tuple[str, ...]] = ("workspace",)


class ArtifactPath(ReePath):
    """Spelled from the REE root, into ``artifacts/``."""


class ExperimentEnvironmentPath(WorkspacePath):
    """Where the build script writes the environment, under the workspace. A bundle lifts the file into
    ``artifacts/`` and rewrites the path to ``artifacts/<name>``, spelled from the REE root; a reader
    resolves it there next, then by its file name in ``artifacts/``."""

    RELATIVE_TO: ClassVar[tuple[str, ...]] = ("workspace", ".", "artifacts")


class ScriptPath(WorkspacePath):
    pass


class ReeRevision(Digest):
    pass


class GitRevision(StringValue):
    pass


class Swhid(StringValue):
    @classmethod
    def validate(cls, value: str) -> str:
        if not value.startswith("swh:1:"):
            raise ValueError("Swhid must use the swh:1:<object>:<hash> form")
        return value


__all__ = [
    "ArtifactPath",
    "Digest",
    "ExperimentEnvironmentPath",
    "GitRevision",
    "OverlayPath",
    "ReePath",
    "ReeRevision",
    "RunId",
    "ScriptPath",
    "SourceType",
    "Swhid",
    "UtcInstant",
    "WorkspacePath",
    "format_utc_instant",
    "parse_utc_instant",
]
