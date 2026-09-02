"""The isolation seam a compute provider backend implements.

The capacity connection translates wire requests into these verbs and streams
the frames back. Everything substrate-specific (containers, volumes, daemons)
lives behind this Protocol; ``DockerIsolation`` is the only implementation
today.

Benches are addressed exclusively by ``WorkbenchRef``: the backend mints one at
provision time and every later verb receives it back verbatim. Its token is the
minting backend's private vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.frames import Frame, WorkbenchRef
from repo2ree_protocol.provider import WorkbenchSpec


class IsolationBackend(Protocol):
    """The verbs a provider needs to place a workbench on its host.

    Streaming verbs yield ``Frame`` records ending in a terminal frame;
    request/response verbs return plain values.
    """

    runtime_name: str

    def provision(
        self,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: WorkbenchSpec,
    ) -> Iterator[Frame]:
        """Create a bench for ``ree_id``; ends with a workbench-ref frame."""
        ...

    def remove(self, ref: WorkbenchRef) -> None:
        """Tear down the bench and its backing storage (best-effort)."""
        ...

    def is_running(self, ref: WorkbenchRef) -> bool: ...
