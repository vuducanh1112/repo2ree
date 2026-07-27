"""REE source-snapshot naming conventions.

A snapshot archive is the frozen copy of the upstream source captured at
acquisition time. This module owns the naming rules; the bytes themselves
are written by :func:`repo2ree_core.ree.files.pack_directory_tar_gz`.

Pure module: no filesystem I/O.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.ree.files import safe_filename

_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".zip", ".tar", ".git")


def strip_archive_suffix(name: str) -> str:
    """Return ``name`` without a recognized archive/VCS suffix."""
    lower = name.lower()
    for suffix in _ARCHIVE_SUFFIXES:
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def snapshot_archive_name(seed: str | None, fallback: str = "source") -> str:
    """Compose the on-disk filename for a captured source snapshot.

    ``seed`` is typically the upstream archive or repo name. Falls back to
    ``fallback`` if ``seed`` is empty or reduces to nothing after cleanup.
    """
    base = strip_archive_suffix(safe_filename(seed, fallback)).strip()
    normalized = base or fallback
    name = f"{normalized}-snapshot.tar.gz"

    # ── postcondition ──
    assert name.endswith("-snapshot.tar.gz"), f"snapshot name must carry the suffix: {name}"  # noqa: S101
    # ───────────────────
    return name
