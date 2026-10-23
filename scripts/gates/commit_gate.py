#!/usr/bin/env python3
"""Write and verify the commit gate's receipt: the tree its checks and tests passed on.

``write`` runs after the gate's checks and records the working tree as it would be staged;
``verify`` (the pre-commit hook) requires the tree being committed to be exactly that tree.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.gates import receipts
from scripts.gates.receipts import CommitGateReceipt, ReceiptError


def git(*args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def receipt_path() -> Path:
    return receipts.path(Path(git("rev-parse", "--show-toplevel")), "commit-gate")


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


def write() -> None:
    receipts.write(receipt_path(), CommitGateReceipt(revision=None, tree=worktree_tree(), written=receipts.now()))


def verify() -> None:
    receipt = receipts.read(CommitGateReceipt, receipt_path())
    if receipt is None:
        raise ReceiptError("no commit-gate receipt for this clone — run: just commit-gate")
    if receipt.tree != git("write-tree"):
        raise ReceiptError(
            "the commit-gate receipt covers different content than you are committing.\n"
            "stage everything you mean to commit, then re-run: just commit-gate"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        write() if args.command == "write" else verify()
    except (ReceiptError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
