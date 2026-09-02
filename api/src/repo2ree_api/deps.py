"""Module-level control-plane singletons shared across API routes.

The composition root: builds the workbench registry, the registry of dialed-in
workbenches, the manager that drives workbenches through those services, and the REE
index.

The first three are liveness state and die with the process that holds them.
The index does not — it is the one singleton here whose file must survive the
service, so it is built from its own configured path rather than derived from
anything running.
"""

from __future__ import annotations

from repo2ree_api.ree_index import ReeIndex
from repo2ree_api.settings import service_settings
from repo2ree_protocol.tracing import build_span_sink
from repo2ree_supervisor import (
    AllocationStore,
    ProviderConnectionRegistry,
    WorkbenchConnectionRegistry,
    WorkbenchManager,
    WsProviderClient,
    WsWorkbenchClient,
)
from repo2ree_supervisor.enrollment import EnrollmentRegistry

allocation_store = AllocationStore(service_settings.ALLOCATION_STORE_FILE)


# The registry of workbenches that have dialed in. The WebSocket route (/workbench/connect)
# populates it; WsWorkbenchClient reads from it to drive whichever workbench is connected.
def _workbench_allocated(workbench_id: str) -> bool:
    return any(
        record.workbench_id == workbench_id and record.state.value not in {"released", "failed", "incompatible", "lost"}
        for record in allocation_store.list()
    )


workbench_connections = WorkbenchConnectionRegistry(is_allocated=_workbench_allocated)
provider_connections = ProviderConnectionRegistry()
workbench_enrollments = EnrollmentRegistry()

# One combined-workbench client serves both manager seams today: the legacy workbench
# multiplexes capacity and execution over one socket. When the two roles get
# separate transports, only this composition changes.
_workbench_client = WsWorkbenchClient(workbench_connections)
_provider_client = WsProviderClient(provider_connections)

workbench_manager = WorkbenchManager(
    registry=allocation_store,
    provider=_provider_client,
    workbench=_workbench_client,
    enrollment=workbench_enrollments,
    span_sink=build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True),
)

# The durable record of what has been sealed here and where it was deposited.
# Written at seal, appended to when a deposit publishes, and read by anything
# that lists or exports the index.
ree_index = ReeIndex(service_settings.REE_INDEX_FILE)
