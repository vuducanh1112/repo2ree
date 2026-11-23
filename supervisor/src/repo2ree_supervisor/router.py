from __future__ import annotations

from repo2ree_supervisor.handle import ReeRoute
from repo2ree_supervisor.rees import ReeRegistry
from repo2ree_supervisor.workbench_link import WorkbenchConnectionRegistry


class StoreUnavailableError(RuntimeError):
    def __init__(self, store_id: str) -> None:
        super().__init__(f"no workbench is serving store {store_id!r}")
        self.store_id = store_id


class ReeRouter:
    def __init__(self, rees: ReeRegistry, connections: WorkbenchConnectionRegistry) -> None:
        self._rees = rees
        self._connections = connections

    def route(self, ree_id: str) -> ReeRoute | None:
        record = self._rees.get(ree_id)
        if record is None:
            return None
        workbench_id = self._connections.store_workbench(record.store_id)
        if workbench_id is None:
            raise StoreUnavailableError(record.store_id)
        return ReeRoute(ree_id=ree_id, workbench_id=workbench_id, store_id=record.store_id)
