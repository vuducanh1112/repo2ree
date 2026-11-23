from __future__ import annotations

from repo2ree_api.ree_index import ReeIndex
from repo2ree_api.settings import service_settings
from repo2ree_supervisor import (
    CommandDispatcher,
    ReeLocks,
    ReeRegistry,
    ReeRoute,
    ReeRouter,
    StoreRegistry,
    StoreUnavailableError,
    Transfers,
    WorkbenchConnectionRegistry,
    WsWorkbenchClient,
)
from repo2ree_telemetry.relay import build_span_sink

workbench_connections = WorkbenchConnectionRegistry()

workbench_transfers = Transfers()
_workbench_client = WsWorkbenchClient(workbench_connections, workbench_transfers)
workbench_client = _workbench_client

span_sink = build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True)

store_registry = StoreRegistry(service_settings.CONTROL_STATE_DIR / "stores.json")
ree_registry = ReeRegistry(service_settings.CONTROL_STATE_DIR / "rees.json")
ree_router = ReeRouter(ree_registry, workbench_connections)


def _reroute(handle: ReeRoute) -> ReeRoute | None:
    try:
        return ree_router.route(handle.ree_id)
    except StoreUnavailableError:
        return None


command_dispatcher = CommandDispatcher(_workbench_client, ReeLocks(), span_sink, reroute=_reroute)

ree_index = ReeIndex(service_settings.REE_INDEX_FILE)
