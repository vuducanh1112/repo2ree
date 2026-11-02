"""Where an REE's commands go: the REE and the workbench it is served by."""

from __future__ import annotations

from dataclasses import dataclass

from repo2ree_protocol.allocation import AllocationRecord


@dataclass(frozen=True)
class WorkbenchHandle:
    ree_id: str
    # The workbench this REE is pinned to; every op on this handle routes to it.
    workbench_id: str = ""
    allocation_id: str = ""
    provider_id: str = ""
    mode: str = "provider_managed"
    location_id: str = ""
    image: str = ""

    @classmethod
    def from_record(cls, record: AllocationRecord) -> WorkbenchHandle:
        request = record.request
        return cls(
            ree_id=request.ree_id,
            workbench_id=record.workbench_id or "",
            allocation_id=request.allocation_id,
            provider_id=record.provider_id or "",
            mode="provider_managed" if record.provider_id else "external",
            location_id=request.location_id,
            image=record.resolved_image or request.image,
        )
