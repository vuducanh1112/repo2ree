"""The recording format: behaviour evidence collected from a deployment, and where each piece came from.

A recording is a directory with ``manifest.json`` and the copies it lists. The system is
distributed, so a source names its origin (the control plane it was fetched through, the
location it came from) rather than assuming one host, and a snapshot of a running system
carries the journal positions it was taken between (its cut). Readers find evidence only
through the manifest.

Collection writes recordings, verification and the views read them; this package is the
one thing they share, and it knows none of them.
"""

from __future__ import annotations

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


class RecordedSource(FormatModel):
    kind: SourceKind
    path: str  # Where the copy sits inside the recording.
    origin: str  # Where it was collected from: a URL through the control plane, or a local path.
    name: str | None = None  # The source's own name: the REE label, the process that wrote the spans.
    location: str | None = None  # The compute location the evidence came from, when it came from one.
    cut: Cut | None = None  # None when taken after the owners it speaks for stopped.
    status: Literal["recorded", "unavailable", "error"] = "recorded"
    problem: str | None = None


class RecordingContext(FormatModel):
    """What the recording was taken for; absent when it was collected from a running deployment."""

    suite: str | None = None
    test: str | None = None
    outcome: str | None = None
    started: float | None = None
    finished: float | None = None


class Recording(FormatModel):
    control_plane: str | None = None
    build_revision: str | None = None
    context: RecordingContext = RecordingContext()
    sources: tuple[RecordedSource, ...] = ()

    def recorded(self, kind: SourceKind) -> list[RecordedSource]:
        return [source for source in self.sources if source.kind == kind and source.status == "recorded"]

    def with_source(self, source: RecordedSource) -> Recording:
        """Add a source, replacing one recorded at the same path."""
        kept = tuple(existing for existing in self.sources if existing.path != source.path)
        return self.model_copy(update={"sources": (*kept, source)})


def read_recording(directory: Path) -> Recording:
    """The manifest; a ValueError names the directory when there is none or it is not one."""
    path = directory / MANIFEST
    try:
        return Recording.model_validate_json(path.read_text())
    except FileNotFoundError:
        raise ValueError(f"{directory}: no {MANIFEST}, not a recording") from None
    except ValidationError as exc:
        raise ValueError(f"{path}: not a recording manifest ({exc.error_count()} problems)") from None


def write_recording(directory: Path, recording: Recording) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST).write_text(recording.model_dump_json(indent=2, exclude_defaults=True) + "\n")


__all__ = [
    "MANIFEST",
    "Cut",
    "RecordedSource",
    "Recording",
    "RecordingContext",
    "SourceKind",
    "read_recording",
    "write_recording",
]
