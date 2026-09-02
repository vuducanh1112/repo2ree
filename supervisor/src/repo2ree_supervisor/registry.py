"""Persistent mapping of ree_id to opaque workbench references and specs.

Stored as a JSON file on the host. Writes are atomic (write-to-temp +
os.replace), so a torn write cannot corrupt the file. Read-modify-write
transactions are serialized across threads in this process. The JSON backend
does not coordinate multiple processes; deployments must use one API worker
until the store moves to transactional storage.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from repo2ree_protocol.frames import WorkbenchRef
from repo2ree_protocol.provider import DockerWorkbenchSpec, WorkbenchSpec


@dataclass(frozen=True)
class WorkbenchEntry:
    ree_id: str
    ref: WorkbenchRef
    spec: WorkbenchSpec | None
    # The workbench this REE's workbench is pinned to (placement affinity): every
    # later op must reach the same workbench that holds the workbench.
    workbench_id: str
    provider_id: str = ""
    # The capacity request identity is distinct from both the REE and the
    # connected workbench. Empty is accepted only for in-memory legacy callers.
    allocation_id: str = ""
    mode: str = "provider_managed"
    state: str = "ready"


class WorkbenchRegistry:
    def __init__(self, registry_file: Path):
        self._path = registry_file
        self._lock = RLock()

    def register(self, entry: WorkbenchEntry) -> None:
        with self._lock:
            data = self._read_unlocked()
            data[entry.ree_id] = {
                "ref": entry.ref.model_dump(),
                "spec": entry.spec.model_dump() if entry.spec is not None else None,
                "workbench_id": entry.workbench_id,
                "provider_id": entry.provider_id,
                "allocation_id": entry.allocation_id or entry.ree_id,
                "mode": entry.mode,
                "state": "ready",
            }
            self._write_unlocked(data)

    def begin(
        self,
        *,
        ree_id: str,
        allocation_id: str,
        workbench_id: str,
        provider_id: str,
        mode: str,
        spec: WorkbenchSpec | None,
    ) -> None:
        """Persist intent before any external provisioning or binding occurs."""
        with self._lock:
            data = self._read_unlocked()
            data[ree_id] = {
                "spec": spec.model_dump() if spec is not None else None,
                "workbench_id": workbench_id,
                "provider_id": provider_id,
                "allocation_id": allocation_id,
                "mode": mode,
                "state": "provisioning",
            }
            self._write_unlocked(data)

    def mark_failed(self, ree_id: str, detail: str) -> None:
        with self._lock:
            data = self._read_unlocked()
            if record := data.get(ree_id):
                record["state"] = "failed"
                record["detail"] = detail
                self._write_unlocked(data)

    def lookup(self, ree_id: str) -> WorkbenchEntry | None:
        with self._lock:
            record = self._read_unlocked().get(ree_id)
        if record is None:
            return None
        if record.get("state", "ready") != "ready":
            return None
        return self._entry_from_record(ree_id, record)

    def list_all(self) -> list[WorkbenchEntry]:
        with self._lock:
            data = self._read_unlocked()
        return [
            self._entry_from_record(ree_id, record)
            for ree_id, record in data.items()
            if record.get("state", "ready") == "ready"
        ]

    @staticmethod
    def _entry_from_record(ree_id: str, record: dict[str, object]) -> WorkbenchEntry:
        spec: WorkbenchSpec | None
        if "ref" not in record:
            # One-time compatibility with registries written before references
            # became opaque. This mirrors the v1 Docker token solely while
            # reading old state; new records never expose backend fields.
            handle = {
                "version": 1,
                "ree_id": ree_id,
                "container_name": str(record["container_name"]),
                "volume_name": str(record["volume_name"]),
                "exec_path": str(record.get("exec_path", "repo2ree-exec")),
            }
            token = base64.urlsafe_b64encode(json.dumps(handle, separators=(",", ":")).encode()).rstrip(b"=").decode()
            ref = WorkbenchRef(runtime="docker", token=token)
            spec = DockerWorkbenchSpec(base_image=str(record["image"]))
        else:
            ref = WorkbenchRef.model_validate(record["ref"])
            raw_spec = record.get("spec")
            spec = DockerWorkbenchSpec.model_validate(raw_spec) if raw_spec is not None else None
        workbench_id = record.get("workbench_id")
        if not isinstance(workbench_id, str) or not workbench_id.strip():
            raise ValueError(f"registry entry {ree_id!r} has no workbench placement")
        return WorkbenchEntry(
            ree_id=ree_id,
            ref=ref,
            spec=spec,
            workbench_id=workbench_id,
            provider_id=str(record.get("provider_id") or workbench_id),
            allocation_id=str(record.get("allocation_id") or ree_id),
            mode=str(record.get("mode") or "provider_managed"),
            state=str(record.get("state") or "ready"),
        )

    def unregister(self, ree_id: str) -> None:
        with self._lock:
            data = self._read_unlocked()
            data.pop(ree_id, None)
            self._write_unlocked(data)

    def _read_unlocked(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        parsed: dict[str, dict[str, object]] = json.loads(self._path.read_text(encoding="utf-8"))
        return parsed

    def _write_unlocked(self, data: dict[str, dict[str, object]]) -> None:
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
