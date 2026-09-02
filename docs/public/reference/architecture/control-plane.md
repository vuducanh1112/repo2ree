# How the control plane is organized

The control plane translates user requests into tracked operations and routes
those operations to the workbench that holds an REE.

![Control-plane request adapters, run orchestration, transfer services, workbench management, routing registries, and state](assets/control-plane.svg)

## Responsibilities

| Area | Responsibility |
|---|---|
| Request adapters | Translate authoring, review, fleet, file, and run requests into operations. |
| Run orchestration | Starts background work and maps progress and results onto run records. |
| Transfer services | Stage uploads and coordinate movement of source, archives, and workspace files. |
| Capacity management | Asks a connected provider to create or remove a workbench for an REE. |
| Workbench routing | Maps an REE identity to its workbench and opaque location. |
| Workbench connections | Owns live workbench sessions and carries request and response messages. |
| Run and control state | Persists run records, uploads, the REE index, and other coordination data. |

Capacity and execution reach the control plane on separate connections. A
provider dials in to offer capacity and never carries an REE command; a
workbench dials in to execute commands and can never create or destroy
infrastructure.

Long-running operations are accepted as background runs. Orchestration resolves
the REE's workbench, dispatches work over that workbench's own connection, and
updates the run as messages return. A client can poll that run independently of
the original request.

File transfers follow the same boundary: the control plane stages and
coordinates data, while the workbench performs the effects. The API does not
bypass that boundary to inspect or modify an REE tree directly.

See [how a pipeline stage runs](pipeline-stage-execution.md) for this
interaction in execution order.
