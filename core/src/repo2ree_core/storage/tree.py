"""Filesystem tree helpers.

Shell module: performs filesystem I/O. Independent of the REE concept.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_tree_contents(source_path: Path, destination: Path) -> None:
    """Merge the contents of ``source_path`` into ``destination``.

    If ``source_path`` is a directory, each top-level entry is copied
    into ``destination`` (directories merged recursively with
    ``dirs_exist_ok=True``; files copied with metadata preserved). If
    ``source_path`` is a regular file, it is copied as
    ``destination / source_path.name``.

    ``destination`` and any missing parent directories are created as
    needed.
    """
    if source_path.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for item in source_path.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        return
    target = destination / source_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
