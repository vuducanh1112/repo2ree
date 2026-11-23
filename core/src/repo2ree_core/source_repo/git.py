from __future__ import annotations

import subprocess
from pathlib import Path


def resolved_git_head(tree: Path) -> str:
    rev = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return rev.stdout.strip() if rev.returncode == 0 else ""
