"""The REEs this control plane serves from stores, and what was last seen of each.

An REE in a store outlives any workbench: it is listed, and its name and status read,
whether or not the workbench serving its store is connected. The summary is refreshed
whenever its REE is read; it is what a listing shows of an REE it cannot reach.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_supervisor.json_file import write_json_atomic


class ReeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ree_id: str
    store_id: str
    name: str
    status: str = "draft"
    created_at: str


class ReeRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def create(self, ree_id: str, name: str, store_id: str) -> ReeRecord:
        with self._lock:
            rees = self._read()
            if ree_id in rees:
                raise ValueError(f"REE {ree_id!r} is already registered")
            record = ReeRecord(ree_id=ree_id, store_id=store_id, name=name, created_at=datetime.now(UTC).isoformat())
            rees[ree_id] = record
            self._write(rees)
            return record

    def get(self, ree_id: str) -> ReeRecord | None:
        with self._lock:
            return self._read().get(ree_id)

    def all(self) -> list[ReeRecord]:
        with self._lock:
            return list(self._read().values())

    def update_summary(self, ree_id: str, *, name: str, status: str) -> None:
        """Remember what the REE was last seen as; nothing when it is not (or no longer) registered."""
        with self._lock:
            rees = self._read()
            record = rees.get(ree_id)
            if record is None or (record.name, record.status) == (name, status):
                return
            rees[ree_id] = record.model_copy(update={"name": name, "status": status})
            self._write(rees)

    def delete(self, ree_id: str) -> None:
        with self._lock:
            rees = self._read()
            if rees.pop(ree_id, None) is not None:
                self._write(rees)

    def _read(self) -> dict[str, ReeRecord]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {key: ReeRecord.model_validate(value) for key, value in raw.get("rees", {}).items()}

    def _write(self, rees: dict[str, ReeRecord]) -> None:
        write_json_atomic(self._path, {"rees": {key: record.model_dump(mode="json") for key, record in rees.items()}})
