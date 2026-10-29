from __future__ import annotations

from typing import Literal

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
    @classmethod
    def validate(cls, value: str) -> str:
        validate_relative_path(value)
        return value


class WorkspacePath(ReePath):
    pass


class ArtifactPath(ReePath):
    pass


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
    "GitRevision",
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
