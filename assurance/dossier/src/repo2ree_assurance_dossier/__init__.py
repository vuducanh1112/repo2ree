"""The dossier format: behaviour evidence collected from a deployment, and where each piece came from.

A dossier is a directory with ``manifest.json`` and the copies it lists. The system is
distributed, so a source names its origin (the control plane it was fetched through, the
location it came from) rather than assuming one host, and a snapshot of a running system
carries the journal positions it was taken between (its cut). Readers find evidence only
through the manifest.

Collection writes dossiers, verification and the views read them; this package is the
one thing they share, and it knows none of them.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

MANIFEST = "manifest.json"

# Where a snapshot was taken relative to a journal: the journal's last sequence
# number read before taking it, and the last one read after. Keyed by journal id.
type Cut = dict[str, tuple[int, int]]

type SourceKind = Literal["journal", "git", "state", "spans"]


class FormatModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DossierSource(FormatModel):
    kind: SourceKind
    path: str  # Where the copy sits inside the dossier.
    origin: str  # Where it was collected from: a URL through the control plane, or a local path.
    name: str | None = None  # The source's own name: the REE label, the process that wrote the spans.
    location: str | None = None  # The compute location the evidence came from, when it came from one.
    cut: Cut | None = None  # None when taken after the owners it speaks for stopped.
    status: Literal["recorded", "unavailable", "error"] = "recorded"
    problem: str | None = None


class DossierContext(FormatModel):
    """What the dossier was taken for; absent when it was collected from a running deployment."""

    suite: str | None = None
    test: str | None = None
    outcome: str | None = None
    started: float | None = None
    finished: float | None = None


class Dossier(FormatModel):
    control_plane: str | None = None
    build_revision: str | None = None
    context: DossierContext = DossierContext()
    sources: tuple[DossierSource, ...] = ()

    def recorded(self, kind: SourceKind) -> list[DossierSource]:
        return [source for source in self.sources if source.kind == kind and source.status == "recorded"]

    def with_source(self, source: DossierSource) -> Dossier:
        """Add a source, replacing one recorded at the same path."""
        kept = tuple(existing for existing in self.sources if existing.path != source.path)
        return self.model_copy(update={"sources": (*kept, source)})


def read_dossier(directory: Path) -> Dossier:
    """The manifest; a ValueError names the directory when there is none or it is not one."""
    path = directory / MANIFEST
    try:
        return Dossier.model_validate_json(path.read_text())
    except FileNotFoundError:
        raise ValueError(f"{directory}: no {MANIFEST}, not a dossier") from None
    except ValidationError as exc:
        raise ValueError(f"{path}: not a dossier manifest ({exc.error_count()} problems)") from None


def write_dossier(directory: Path, dossier: Dossier) -> None:
    """Replace the manifest atomically: an interrupted write leaves the previous one, never half of one."""
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=directory, prefix=f".{MANIFEST}-", delete=False) as pending:
        pending.write(dossier.model_dump_json(indent=2, exclude_defaults=True) + "\n")
    Path(pending.name).replace(directory / MANIFEST)


__all__ = [
    "MANIFEST",
    "Cut",
    "Dossier",
    "DossierContext",
    "DossierSource",
    "SourceKind",
    "read_dossier",
    "write_dossier",
]
