"""Single-process durable allocation and REE placement store."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from repo2ree_protocol.allocation import AllocationRecord, AllocationRequest, AllocationState
from repo2ree_protocol.substrate import CompatibilityIssue, ObservedCapabilities
from repo2ree_supervisor.allocation_state import require_transition


class AllocationStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = RLock()

    def create(
        self, request: AllocationRequest, *, provider_id: str | None, workbench_id: str | None
    ) -> AllocationRecord:
        now = datetime.now(UTC)
        record = AllocationRecord(
            request=request,
            state=AllocationState.REQUESTED,
            provider_id=provider_id,
            workbench_id=workbench_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            data = self._read()
            if request.allocation_id in data["allocations"]:
                raise ValueError(f"allocation {request.allocation_id!r} already exists")
            if request.ree_id in data["placements"]:
                raise ValueError(f"REE {request.ree_id!r} already has an allocation")
            data["allocations"][request.allocation_id] = record.model_dump(mode="json")
            data["placements"][request.ree_id] = request.allocation_id
            self._write(data)
        return record

    def update(
        self,
        allocation_id: str,
        state: AllocationState,
        *,
        workbench_id: str | None = None,
        observation: ObservedCapabilities | None = None,
        incompatibilities: tuple[CompatibilityIssue, ...] | None = None,
        detail: str | None = None,
    ) -> AllocationRecord:
        with self._lock:
            data = self._read()
            record = AllocationRecord.model_validate(data["allocations"][allocation_id])
            require_transition(record.state, state)
            record.state = state
            if workbench_id is not None:
                record.workbench_id = workbench_id
            if observation is not None:
                record.observation = observation
            if incompatibilities is not None:
                record.incompatibilities = incompatibilities
            if detail is not None:
                record.detail = detail
            record.updated_at = datetime.now(UTC)
            data["allocations"][allocation_id] = record.model_dump(mode="json")
            self._write(data)
            return record

    def get(self, allocation_id: str) -> AllocationRecord | None:
        with self._lock:
            raw = self._read()["allocations"].get(allocation_id)
        return AllocationRecord.model_validate(raw) if raw is not None else None

    def for_ree(self, ree_id: str) -> AllocationRecord | None:
        with self._lock:
            data = self._read()
            allocation_id = data["placements"].get(ree_id)
            raw = data["allocations"].get(allocation_id) if isinstance(allocation_id, str) else None
        return AllocationRecord.model_validate(raw) if raw is not None else None

    def list(self) -> list[AllocationRecord]:
        with self._lock:
            values = list(self._read()["allocations"].values())
        return [AllocationRecord.model_validate(value) for value in values]

    def remove_placement(self, ree_id: str) -> None:
        with self._lock:
            data = self._read()
            data["placements"].pop(ree_id, None)
            self._write(data)

    def _read(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {"allocations": {}, "placements": {}}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {"allocations": dict(raw.get("allocations", {})), "placements": dict(raw.get("placements", {}))}

    def _write(self, data: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=self._path.name + ".", suffix=".tmp", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, sort_keys=True)
            Path(temporary).replace(self._path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
