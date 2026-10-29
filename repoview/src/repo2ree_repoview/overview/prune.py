"""Keep reports/overview/ bounded: the newest overviews, and the one `latest` points to.

Every overview build prunes after it writes. Only a folder whose manifest says the overview
wrote it is ever removed; anything else in reports/overview/ is left alone.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from repo2ree_repoview.overview.bundle import is_overview
from repo2ree_repoview.repository import ROOT

OVERVIEWS = ROOT / "reports/overview"
KEEP = 3


def stale_overviews(overviews: Path, keep: int = KEEP) -> list[Path]:
    """The overviews beyond the newest ``keep``, never the one ``latest`` points to."""
    if not overviews.is_dir():
        return []
    latest = overviews / "latest"
    current = latest.resolve() if latest.is_symlink() else None
    found = [path for path in overviews.iterdir() if path.is_dir() and not path.is_symlink() and is_overview(path)]
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return [path for path in found[keep:] if path.resolve() != current]


def prune(overviews: Path, *, keep: int = KEEP, dry_run: bool = False) -> list[Path]:
    stale = stale_overviews(overviews, keep)
    for path in stale:
        print(f"   {'would remove' if dry_run else 'removing'} {path.name}")
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
    print(f">> pruned overviews: {len(stale)} {'would go' if dry_run else 'removed'}, the newest {keep} kept")
    return stale
