#!/usr/bin/env python3
"""Install a fully generated directory while preserving the previous result on failure."""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path


def replace_directory(staging: Path, target: Path) -> None:
    if not staging.is_dir():
        raise RuntimeError(f"staging directory does not exist: {staging}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if staging.parent.resolve() != target.parent.resolve():
        raise RuntimeError("staging and target must share a parent so installation stays on one filesystem")

    backup = target.with_name(f".{target.name}.previous-{uuid.uuid4().hex}")
    moved_previous = False
    if target.exists() or target.is_symlink():
        target.rename(backup)
        moved_previous = True
    try:
        staging.rename(target)
    except OSError:
        if moved_previous and not target.exists():
            backup.rename(target)
        raise
    if moved_previous:
        if backup.is_dir() and not backup.is_symlink():
            shutil.rmtree(backup)
        else:
            backup.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    try:
        replace_directory(args.staging, args.target)
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
