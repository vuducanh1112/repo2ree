"""Nominal scalar value types shared by the REE domain.

The string-backed types deliberately retain scalar JSON representations while
remaining distinct to static type checkers. Host filesystem locations use
``pathlib.Path`` elsewhere; these path types name portable POSIX locations
inside an REE.
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from repo2ree_core.digests import Digest
from repo2ree_core.path_safety import validate_path_segment, validate_relative_path
from repo2ree_core.time_utils import UtcInstant, format_utc_instant, parse_utc_instant

SourceType = Literal["", "git", "hg", "svn", "cvs", "bzr", "tarball", "zip"]


class _StringValue(str):
    """A validated nominal string that remains a JSON string on the wire."""

    def __new__(cls, value: str) -> Self:
        text = cls.validate(str(value))
        return str.__new__(cls, text)

    @classmethod
    def validate(cls, value: str) -> str:
        if not value:
            raise ValueError(f"{cls.__name__} must not be empty")
        return value

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


class RunId(_StringValue):
    @classmethod
    def validate(cls, value: str) -> str:
        return validate_path_segment(value, kind="run_id")


class ReePath(_StringValue):
    @classmethod
    def validate(cls, value: str) -> str:
        validate_relative_path(value)
        return value


class WorkspacePath(ReePath):
    """A portable path resolved relative to the materialized workspace."""


class ArtifactPath(ReePath):
    """A portable path naming machine-produced REE content."""


class ScriptPath(WorkspacePath):
    """A workspace path expected to contain an executable recipe script."""


class ReeRevision(Digest):
    """Content identity of one authored REE head."""


class GitRevision(_StringValue):
    """A source-control revision, distinct from an REE content revision."""


class Swhid(_StringValue):
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
