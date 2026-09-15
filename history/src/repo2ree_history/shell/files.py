"""Constrain filesystem access to a declared root."""

from pathlib import Path


def contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"artifact escapes recording root: {relative}")
    return path
