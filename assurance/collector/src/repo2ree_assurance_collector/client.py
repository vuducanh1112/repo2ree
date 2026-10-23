"""A read-only client of the control plane's HTTP API, and the answers the collector reads from it.

Every answer is parsed where it arrives. Only the fields the collector uses are read, and each
is checked for type; every name that becomes a path in the dossier must be one safe path
segment. An answer that is not what was asked for fails like an unreachable control plane, so
the collector lists the source with the problem instead of writing what it was handed.
"""

from __future__ import annotations

import re
import shutil
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Annotated

from pydantic import BaseModel, ConfigDict, JsonValue, StringConstraints, ValidationError

# One path segment: no separator, no leading dot, so never "..", a hidden file, or a way out.
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

type SafeName = Annotated[str, StringConstraints(pattern=SAFE_NAME.pattern)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
# Per journal id: the last sequence number read before a snapshot was taken, and the last read after.
type Cut = dict[SafeName, tuple[int, int]]


class ControlPlaneError(RuntimeError):
    """The control plane gave no usable answer: unreachable, an error status, or not what was asked for."""


class Answer(BaseModel):
    """What the collector reads of an answer; fields it does not use are the control plane's business."""

    model_config = ConfigDict(frozen=True, extra="ignore")


class BuildInfo(Answer):
    revision: str | None = None


class Journal(Answer):
    id: SafeName


class Journals(Answer):
    journals: tuple[Journal, ...]


class OwnerState(Answer):
    """The owners' persisted state, read between two sets of journal positions."""

    cut: Cut
    runs: dict[SafeName, dict[str, JsonValue]]  # Each run's state.json, by its directory name.
    allocations: dict[str, JsonValue] | None


class ServedArchive(Answer):
    """One REE archive the control plane served, so a copy a client kept can be placed."""

    ree_id: SafeName
    sha256: Sha256
    cut: Cut


class ServedArchives(Answer):
    archives: tuple[ServedArchive, ...]


class ControlPlane:
    def __init__(self, url: str, timeout: float = 300) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    def address(self, path: str) -> str:
        return f"{self.url}{path}"

    def get[A: Answer](self, answer: type[A], path: str) -> A:
        body = self.get_bytes(path)
        try:
            return answer.model_validate_json(body)
        except ValidationError as exc:
            problem = exc.errors()[0]
            where = ".".join(str(part) for part in problem["loc"]) or "the answer"
            raise ControlPlaneError(
                f"GET {self.address(path)}: not the expected answer ({where}: {problem['msg']})"
            ) from None

    def get_bytes(self, path: str) -> bytes:
        with self._open(path) as response:
            return response.read()

    def download(self, path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._open(path) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output, 1 << 20)

    @contextmanager
    def _open(self, path: str) -> Iterator[IO[bytes]]:
        address = self.address(path)
        try:
            response = urllib.request.urlopen(address, timeout=self.timeout)  # noqa: S310 — the operator's control plane
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ControlPlaneError(f"GET {address}: {exc}") from exc
        with response:
            yield response
