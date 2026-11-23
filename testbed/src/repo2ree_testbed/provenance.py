from __future__ import annotations

import os
import subprocess

from repo2ree_testbed.artifacts import ROOT


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def clean_tree() -> str:
    if _git("status", "--porcelain") or not (tree := _git("rev-parse", "HEAD^{tree}")):
        return ""
    return tree


def clean_revision() -> str:
    return _git("rev-parse", "HEAD") if clean_tree() else ""


def platform() -> str:
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def machine() -> str:
    return os.environ.get("REPO2REE_MACHINE") or "local"


def head() -> tuple[str, bool]:
    return _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain"))


def commit(revision: str, dirty: bool = False) -> str:
    if not revision:
        return "an unknown commit"
    return revision[:10] + (" + uncommitted changes" if dirty else "")
