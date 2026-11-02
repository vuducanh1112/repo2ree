"""Where an REE's commands go.

An REE served by a store goes to the workbench serving that store, whichever one that is
at the moment; one set up for it by a provider (or reserved from an external bench) goes
to that workbench, as its allocation says.
"""

from __future__ import annotations

from typing import Protocol

from repo2ree_supervisor.handle import WorkbenchHandle
from repo2ree_supervisor.rees import ReeRegistry
from repo2ree_supervisor.workbench_link import WorkbenchConnectionRegistry


class Allocations(Protocol):
    """The workbenches set up for REEs one by one (the manager), as far as routing needs them."""

    def lookup(self, ree_id: str) -> WorkbenchHandle | None: ...

    def is_registered(self, ree_id: str) -> bool: ...


class StoreUnavailableError(RuntimeError):
    """The REE's store has no workbench connected to serve it."""

    def __init__(self, store_id: str) -> None:
        super().__init__(f"no workbench is serving store {store_id!r}")
        self.store_id = store_id


class ReeRouter:
    def __init__(self, rees: ReeRegistry, connections: WorkbenchConnectionRegistry, allocations: Allocations) -> None:
        self._rees = rees
        self._connections = connections
        self._allocations = allocations

    def route(self, ree_id: str) -> WorkbenchHandle | None:
        """The workbench to send ``ree_id``'s commands to; None for an REE this control plane does not know.

        Raises ``StoreUnavailableError`` for an REE whose store no workbench serves right now.
        """
        record = self._rees.get(ree_id)
        if record is None:
            return self._allocations.lookup(ree_id)
        workbench_id = self._connections.store_workbench(record.store_id)
        if workbench_id is None:
            raise StoreUnavailableError(record.store_id)
        return WorkbenchHandle(ree_id=ree_id, workbench_id=workbench_id, mode="store", location_id=record.store_id)

    def is_known(self, ree_id: str) -> bool:
        """Whether ``ree_id`` names an REE here, reachable or not."""
        return self._rees.get(ree_id) is not None or self._allocations.is_registered(ree_id)
