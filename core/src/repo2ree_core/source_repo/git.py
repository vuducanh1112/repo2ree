"""Best-effort git facts read from an acquired source tree."""

from __future__ import annotations

import subprocess
from pathlib import Path


def resolved_git_head(tree: Path) -> str:
    """The HEAD commit of a git working tree, or ``""`` when unavailable.

    Empty when the tree carries no git history (an upload, a non-git origin, or a
    snapshot that did not preserve ``.git``). Never raises: a source's identity
    receipt must not block acquisition.
    """
    rev = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return rev.stdout.strip() if rev.returncode == 0 else ""
