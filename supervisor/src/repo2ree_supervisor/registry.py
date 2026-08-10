"""Persistent mapping of ree_id → workbench container + volume names.

Stored as a JSON file on the host. Writes are atomic (write-to-temp +
os.replace), so a torn write cannot corrupt the file. Read-modify-write
transactions are serialized across threads in this process. The JSON backend
does not coordinate multiple processes; deployments must use one API worker
until the store moves to transactional storage.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock


@dataclass(frozen=True)
class WorkbenchEntry:
    ree_id: str
    container_name: str
    volume_name: str
    # The image this workbench was provisioned from.
    image: str
    # The agent this REE's workbench is pinned to (placement affinity): every
    # later op must reach the same agent that holds the container.
    agent_id: str
    # How the executor is invoked inside this bench, as minted by the agent at
    # provision time (see WorkbenchLocation.exec_path).
    exec_path: str


class WorkbenchRegistry:
    def __init__(self, registry_file: Path):
        self._path = registry_file
        self._lock = RLock()

    def register(self, entry: WorkbenchEntry) -> None:
        with self._lock:
            data = self._read_unlocked()
            data[entry.ree_id] = {
                "container_name": entry.container_name,
                "volume_name": entry.volume_name,
                "image": entry.image,
                "agent_id": entry.agent_id,
                "exec_path": entry.exec_path,
            }
            self._write_unlocked(data)

    def lookup(self, ree_id: str) -> WorkbenchEntry | None:
        with self._lock:
            record = self._read_unlocked().get(ree_id)
        if record is None:
            return None
        return self._entry_from_record(ree_id, record)

    def list_all(self) -> list[WorkbenchEntry]:
        with self._lock:
            data = self._read_unlocked()
        return [self._entry_from_record(ree_id, record) for ree_id, record in data.items()]

    @staticmethod
    def _entry_from_record(ree_id: str, record: dict[str, str]) -> WorkbenchEntry:
        return WorkbenchEntry(
            ree_id=ree_id,
            container_name=record["container_name"],
            volume_name=record["volume_name"],
            image=record["image"],
            agent_id=record["agent_id"],
            exec_path=record["exec_path"],
        )

    def unregister(self, ree_id: str) -> None:
        with self._lock:
            data = self._read_unlocked()
            data.pop(ree_id, None)
            self._write_unlocked(data)

    def _read_unlocked(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        parsed: dict[str, dict[str, str]] = json.loads(self._path.read_text(encoding="utf-8"))
        return parsed

    def _write_unlocked(self, data: dict[str, dict[str, str]]) -> None:
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
            Path(tmp).replace(self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
