"""Route capacity operations to the isolation backend, honouring catalog policy."""

from __future__ import annotations

from collections.abc import Iterator

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import Frame
from repo2ree_provider_docker.isolation import IsolationBackend


class ProvisionerService:
    """The backend-neutral provisioning service: creates and destroys benches.

    It contains no execution vocabulary or workbench-service dependency.
    """

    def __init__(self, backend: IsolationBackend, catalog: set[str], accepts_custom_image: bool):
        self._backend = backend
        self._catalog = set(catalog)
        self._accepts_custom_image = accepts_custom_image

    def ensure(
        self,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        image = allocation.image
        if not image:
            raise ValueError("a provider-managed allocation must name an image")
        # The control plane resolves the ref against the catalog it was told
        # about, but a provider's own policy is the one that binds — a stale
        # catalog on the control plane must not become a way past this.
        if image not in self._catalog and not self._accepts_custom_image:
            raise ValueError(f"image {image!r} is not in this provider's catalog and custom images are refused")
        return self._backend.ensure(allocation, workbench_id, enrollment_token)

    def release(self, allocation_id: str) -> None:
        self._backend.release(allocation_id)

    def inspect(self, allocation_id: str) -> bool:
        return self._backend.inspect(allocation_id)
