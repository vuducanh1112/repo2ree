"""Source-repository metadata derived from intent, session and file inventory."""

from .metadata import (
    SourceRepoMetadata,
    derive_source_repo_metadata,
    format_source_size,
    repo_name_from_origin_url,
    total_source_size,
)

__all__ = [
    "SourceRepoMetadata",
    "derive_source_repo_metadata",
    "format_source_size",
    "repo_name_from_origin_url",
    "total_source_size",
]
