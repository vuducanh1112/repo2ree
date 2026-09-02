"""Route capacity operations to the isolation backend named by a spec or reference."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import Frame
from repo2ree_provider_docker.isolation import IsolationBackend


class ProvisionerService:
    """The backend-neutral provisioning service: creates and destroys benches.

    It contains no execution vocabulary or workbench-service dependency.
    """

    def __init__(self, backend: IsolationBackend, profiles: Mapping[tuple[str, str], str]):
        self._backend = backend
        self._profiles = dict(profiles)

    def ensure(
        self,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        key = (allocation.profile_id, allocation.profile_revision)
        try:
            image = self._profiles[key]
        except KeyError as exc:
            raise ValueError(f"unsupported workbench profile {key[0]!r} revision {key[1]!r}") from exc
        return self._backend.ensure(allocation, workbench_id, enrollment_token, image)

    def release(self, allocation_id: str) -> None:
        self._backend.release(allocation_id)

    def inspect(self, allocation_id: str) -> bool:
        return self._backend.inspect(allocation_id)
