#!/usr/bin/env python3
"""Record and verify the tree covered by the commit gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def git(*args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def stamp_path() -> Path:
    return Path(git("rev-parse", "--show-toplevel")) / ".validation-certificates/commit-gate-ok"


def assert_ignored(stamp: Path) -> None:
    if subprocess.run(["git", "check-ignore", "-q", str(stamp)], check=False).returncode != 0:
        raise RuntimeError(
            f"{stamp} is not ignored by git — a tracked certificate changes the tree it\n"
            "measures and can never match. Restore .validation-certificates/.gitignore."
        )


def worktree_tree() -> str:
    descriptor, name = tempfile.mkstemp(prefix="repo2ree-index-")
    os.close(descriptor)
    index = Path(name)
    environment = {**os.environ, "GIT_INDEX_FILE": str(index)}
    try:
        subprocess.run(["git", "read-tree", "HEAD"], check=False, env=environment, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "add", "-A"], check=True, env=environment)
        return git("write-tree", env=environment)
    finally:
        index.unlink(missing_ok=True)


def atomic_write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as pending:
        pending.write(contents)
        pending_path = Path(pending.name)
    pending_path.replace(path)


def write() -> None:
    stamp = stamp_path()
    assert_ignored(stamp)
    atomic_write(stamp, f"{worktree_tree()}\n")


def verify() -> None:
    stamp = stamp_path()
    if not stamp.is_file():
        raise RuntimeError("no commit-gate certificate for this clone — run: just commit-gate")
    if stamp.read_text().strip() != git("write-tree"):
        raise RuntimeError(
            "the commit-gate certificate covers different content than you are committing.\n"
            "stage everything you mean to commit, then re-run: just commit-gate"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        write() if args.command == "write" else verify()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
