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

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

type SafeName = Annotated[str, StringConstraints(pattern=SAFE_NAME.pattern)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Cut = dict[SafeName, tuple[int, int]]


class ControlPlaneError(RuntimeError):
    pass


class Answer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class BuildInfo(Answer):
    revision: str | None = None


class Journal(Answer):
    id: SafeName


class Journals(Answer):
    journals: tuple[Journal, ...]


class Store(Answer):
    store_id: SafeName


class Stores(Answer):
    stores: tuple[Store, ...]


class OwnerState(Answer):
    cut: Cut
    runs: dict[SafeName, dict[str, JsonValue]]


class ServedArchive(Answer):
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
            response = urllib.request.urlopen(address, timeout=self.timeout)  # noqa: S310
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ControlPlaneError(f"GET {address}: {exc}") from exc
        with response:
            yield response
