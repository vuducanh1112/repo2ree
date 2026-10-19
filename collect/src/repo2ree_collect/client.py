"""A minimal read-only client of the control plane's HTTP API."""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class UnreachableError(RuntimeError):
    """The control plane did not answer a request with success."""


class ControlPlane:
    def __init__(self, url: str, timeout: float = 300) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    def address(self, path: str, **query: str | int) -> str:
        suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
        return f"{self.url}{path}{suffix}"

    def get_json(self, path: str, **query: str | int) -> Any:
        return json.loads(self.get_bytes(path, **query))

    def get_bytes(self, path: str, **query: str | int) -> bytes:
        with self._open(path, **query) as response:
            data: bytes = response.read()
            return data

    def download(self, path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._open(path) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output, 1 << 20)

    def _open(self, path: str, **query: str | int) -> Any:
        address = self.address(path, **query)
        try:
            return urllib.request.urlopen(address, timeout=self.timeout)  # noqa: S310 — the operator's control plane
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UnreachableError(f"GET {address}: {exc}") from exc
