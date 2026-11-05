"""Module-level control-plane singletons shared across API routes.

The composition root: builds the registry of dialed-in workbenches, the dispatcher that drives
REE commands through them, the stores and the REEs they serve, and the REE index.

The connections are liveness state and die with the process that holds them. The registries of
stores and REEs, and the index, do not: their files must survive the service, so each is built
from its own configured path rather than derived from anything running.
"""

from __future__ import annotations

from repo2ree_api.ree_index import ReeIndex
from repo2ree_api.settings import service_settings
from repo2ree_supervisor import (
    CommandDispatcher,
    ReeLocks,
    ReeRegistry,
    ReeRouter,
    StoreRegistry,
    Transfers,
    WorkbenchConnectionRegistry,
    WsWorkbenchClient,
)
from repo2ree_telemetry.relay import build_span_sink

# The registry of workbenches that have dialed in. The WebSocket route (/workbench/connect)
# populates it; WsWorkbenchClient reads from it to drive the workbench serving an REE's store.
workbench_connections = WorkbenchConnectionRegistry()

# Files workbenches upload beside their control socket (an REE archive), by single-use token.
workbench_transfers = Transfers()
_workbench_client = WsWorkbenchClient(workbench_connections, workbench_transfers)
workbench_client = _workbench_client

# Where relayed spans go. Two sources feed it: executor spans, which the dispatcher
# forwards off the command path, and a workbench's own spans, which arrive
# uncorrelated on its socket (see WorkbenchConnection.on_message). Both are
# base64 OTLP payloads this side never decodes.
span_sink = build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True)

# Commands and queries for an REE, one at a time per REE.
command_dispatcher = CommandDispatcher(_workbench_client, ReeLocks(), span_sink)

# Stores an operator registered and the REEs they serve; each REE's commands go where the router says.
store_registry = StoreRegistry(service_settings.CONTROL_STATE_DIR / "stores.json")
ree_registry = ReeRegistry(service_settings.CONTROL_STATE_DIR / "rees.json")
ree_router = ReeRouter(ree_registry, workbench_connections)

# The durable record of what has been sealed here and where it was deposited.
# Written at seal, appended to when a deposit publishes, and read by anything
# that lists or exports the index.
ree_index = ReeIndex(service_settings.REE_INDEX_FILE)
