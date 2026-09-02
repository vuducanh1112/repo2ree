"""Route capacity operations to the isolation backend named by a spec or reference."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from repo2ree_protocol.frames import Frame, WorkbenchRef
from repo2ree_protocol.provider import WorkbenchSpec
from repo2ree_provider_docker.isolation import IsolationBackend


class ProvisionerService:
    """The backend-neutral provisioning service: creates and destroys benches.

    It contains no execution vocabulary or workbench-service dependency.
    """

    def __init__(self, backends: Mapping[str, IsolationBackend]):
        self._backends = dict(backends)

    def _backend(self, name: str) -> IsolationBackend:
        try:
            return self._backends[name]
        except KeyError as exc:
            raise ValueError(f"unsupported workbench runtime {name!r}") from exc

    def provision(
        self,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: WorkbenchSpec,
    ) -> Iterator[Frame]:
        return self._backend(spec.runtime).provision(allocation_id, workbench_id, enrollment_token, ree_id, spec)

    def remove(self, ref: WorkbenchRef) -> None:
        self._backend(ref.runtime).remove(ref)

    def is_running(self, ref: WorkbenchRef) -> bool:
        return self._backend(ref.runtime).is_running(ref)
