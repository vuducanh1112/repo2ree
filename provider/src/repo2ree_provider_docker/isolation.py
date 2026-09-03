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

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import Frame


class IsolationBackend(Protocol):
    """The verbs a provider needs to place a workbench on its host.

    Streaming verbs yield ``Frame`` records ending in a terminal frame;
    request/response verbs return plain values.
    """

    def ensure(
        self,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        """Create the bench ``allocation`` names; ends with a status frame.

        The image is read off the allocation rather than passed beside it: the
        container is started from one and labelled from the other, so two
        arguments for one fact is a way for them to disagree.
        """
        ...

    def release(self, allocation_id: str) -> None:
        """Tear down the bench and its backing storage (best-effort)."""
        ...

    def inspect(self, allocation_id: str) -> bool: ...
