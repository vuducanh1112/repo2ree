from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

MANIFEST = "manifest.json"

type Cut = dict[str, tuple[int, int]]

type SourceKind = Literal["journal", "git", "state", "spans"]


class FormatModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DossierSource(FormatModel):
    kind: SourceKind
    path: str
    origin: str
    name: str | None = None
    location: str | None = None
    cut: Cut | None = None
    status: Literal["recorded", "unavailable", "error"] = "recorded"
    problem: str | None = None


class DossierContext(FormatModel):
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
        kept = tuple(existing for existing in self.sources if existing.path != source.path)
        return self.model_copy(update={"sources": (*kept, source)})


def read_dossier(directory: Path) -> Dossier:
    path = directory / MANIFEST
    try:
        return Dossier.model_validate_json(path.read_text())
    except FileNotFoundError:
        raise ValueError(f"{directory}: no {MANIFEST}, not a dossier") from None
    except ValidationError as exc:
        raise ValueError(f"{path}: not a dossier manifest ({exc.error_count()} problems)") from None


def write_dossier(directory: Path, dossier: Dossier) -> None:
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
