"""Where the repository is, and how the views ask Git about it."""

from __future__ import annotations

import subprocess
from pathlib import Path

# The package is installed editable from repoview/src, so the repository is three levels up.
ROOT = Path(__file__).resolve().parents[3]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
