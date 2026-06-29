"""Persistent mapping of ree_id → workbench container + volume names.

Stored as a JSON file on the host. All reads and writes are atomic
(write-to-temp + os.replace) so concurrent API workers cannot corrupt it.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkbenchEntry:
    ree_id: str
    container_name: str
    volume_name: str
    # The image this workbench was provisioned from. Empty for entries written
    # before image tracking existed; consumers fall back to the manager default.
    image: str = ""


class WorkbenchRegistry:
    def __init__(self, registry_file: Path):
        self._path = registry_file

    def register(self, entry: WorkbenchEntry) -> None:
        data = self._read()
        data[entry.ree_id] = {
            "container_name": entry.container_name,
            "volume_name": entry.volume_name,
            "image": entry.image,
        }
        self._write(data)

    def lookup(self, ree_id: str) -> WorkbenchEntry | None:
        data = self._read()
        record = data.get(ree_id)
        if record is None:
            return None
        return self._entry_from_record(ree_id, record)

    def list_all(self) -> list[WorkbenchEntry]:
        data = self._read()
        return [self._entry_from_record(ree_id, record) for ree_id, record in data.items()]

    @staticmethod
    def _entry_from_record(ree_id: str, record: dict[str, str]) -> WorkbenchEntry:
        return WorkbenchEntry(
            ree_id=ree_id,
            container_name=record["container_name"],
            volume_name=record["volume_name"],
            # Absent for entries written before image tracking.
            image=record.get("image", ""),
        )

    def unregister(self, ree_id: str) -> None:
        data = self._read()
        data.pop(ree_id, None)
        self._write(data)

    def _read(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, dict[str, str]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, sort_keys=True)
        fd, tmp = tempfile.mkstemp(
            prefix=self._path.name + ".",
            suffix=".tmp",
            dir=self._path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
