"""Where the repository is, how the views ask Git about it, and the commit a view is drawn from."""

from __future__ import annotations

import datetime
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from repo2ree_repoview.documents import Record

# The package is installed editable from repoview/src, so the repository is three levels up.
ROOT = Path(__file__).resolve().parents[3]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


class Provenance(Record):
    """The commit a view was made from, whether the working tree differed (and a hash of how), and when."""

    revision: str
    tree: str
    dirty: bool
    working_tree_sha256: str | None
    generated: str

    @classmethod
    def now(cls) -> Provenance:
        status = git("status", "--porcelain")
        working = git("diff", "HEAD", "--binary") + status
        return cls(
            revision=git("rev-parse", "HEAD"),
            tree=git("rev-parse", "HEAD^{tree}"),
            dirty=bool(status),
            working_tree_sha256=hashlib.sha256(working.encode()).hexdigest() if status else None,
            generated=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        )


@dataclass(frozen=True)
class Head:
    """The checked-out commit as the overview shows it."""

    provenance: Provenance
    index_tree: str
    subject: str
    branch: str
    committed: str

    @classmethod
    def now(cls) -> Head:
        return cls(
            provenance=Provenance.now(),
            index_tree=git("write-tree"),
            subject=git("log", "-1", "--format=%s"),
            branch=git("rev-parse", "--abbrev-ref", "HEAD"),
            committed=git("log", "-1", "--format=%cI"),
        )

    @property
    def revision(self) -> str:
        return self.provenance.revision

    @property
    def tree(self) -> str:
        return self.provenance.tree

    @property
    def dirty(self) -> bool:
        return self.provenance.dirty
