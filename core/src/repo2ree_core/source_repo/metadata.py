"""Derive display-ready source-repository metadata.

Pure module: no filesystem or network I/O. Callers pass already-loaded intent,
session and the enumerated workspace file inventory.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from repo2ree_core.domain.ree_intent import ReeIntent, SourceType
from repo2ree_core.domain.ree_session import ReeSession, SourceAcquiredBy
from repo2ree_core.ree.workspace.inventory import WorkspaceFile

_VCS_SUFFIX = ".git"


# ================================================
# Data Models
# ================================================


class SourceRepoMetadata(BaseModel):
    """One coherent view of the source loaded into a workspace.

    snake_case field names are the wire shape — the model doubles as the
    API contract for the document's ``source_repo`` block.
    """

    name: str = ""
    origin: str = ""
    acquired_by: SourceAcquiredBy = ""
    source_type: SourceType = ""
    swhid: str = ""
    size_bytes: int | None = None
    size_label: str | None = None


# ================================================
# Helpers
# ================================================


def repo_name_from_origin_url(origin_url: str) -> str:
    """Last path segment of ``origin_url`` without a trailing ``.git``.

    ``https://github.com/acme/widget.git`` → ``widget``; ``""`` when none.
    """
    without_query = origin_url.split("?", 1)[0].split("#", 1)[0]
    segments = [segment for segment in without_query.rstrip("/").split("/") if segment]
    if not segments:
        return ""
    name = segments[-1]
    if name.lower().endswith(_VCS_SUFFIX):
        name = name[: -len(_VCS_SUFFIX)]
    return name


def total_source_size(files: Iterable[WorkspaceFile]) -> int | None:
    """Sum the sizes of the enumerated files, or ``None`` for an empty inventory."""
    sizes = [file.size for file in files]
    return sum(sizes) if sizes else None


def format_source_size(num_bytes: int) -> str:
    """Render a byte count compactly, e.g. ``1.4 MB`` or ``512 B``."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    units = ("KB", "MB", "GB", "TB")
    value = num_bytes / 1024
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    rounded = round(value) if value >= 10 else round(value * 10) / 10
    return f"{rounded:g} {units[unit]}"


# ================================================
# Derivation
# ================================================


def derive_source_repo_metadata(
    intent: ReeIntent,
    session: ReeSession,
    files: Iterable[WorkspaceFile],
) -> SourceRepoMetadata:
    """Fold intent, session and the file inventory into one source record."""
    from_upload = session.source_acquired_by == "upload"
    repo_name = repo_name_from_origin_url(intent.origin_url)
    uploaded = session.uploaded_archive or ""

    # Name after the most specific thing we have: the archive for uploads, the
    # origin repo for downloads, then fall through to whatever else is set.
    preferred = uploaded if from_upload else repo_name
    name = next(
        (candidate for candidate in (preferred, repo_name, uploaded, intent.name) if candidate),
        "Unnamed source",
    )

    size_bytes = total_source_size(files)
    size_label = None if size_bytes is None else format_source_size(size_bytes)

    return SourceRepoMetadata(
        name=name,
        origin=intent.origin_url or ("Upload" if from_upload else ""),
        acquired_by=session.source_acquired_by,
        source_type=intent.source_type,
        swhid=intent.swhid,
        size_bytes=size_bytes,
        size_label=size_label,
    )
