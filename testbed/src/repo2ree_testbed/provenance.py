"""Where and on what a run ran: the tree it was built from, the Docker platform, and the machine.

A run record carries these so a run can be told apart from another of the same tier: one
built from a dirty tree, or from a tree that changed while it ran, names no tree at all.
"""

from __future__ import annotations

import os
import subprocess

from repo2ree_testbed.artifacts import ROOT


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def clean_tree() -> str:
    """HEAD's tree when the checkout is clean (untracked files included); "" otherwise."""
    if _git("status", "--porcelain") or not (tree := _git("rev-parse", "HEAD^{tree}")):
        return ""
    return tree


def platform() -> str:
    """The Docker server's ``os/arch``, as an image platform names it; "" without a reachable daemon."""
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
    """The machine a run ran on: the name ``just on`` gave its job, or ``local``."""
    return os.environ.get("REPO2REE_MACHINE") or "local"
