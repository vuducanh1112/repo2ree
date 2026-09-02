# Services, workbenches, and data stores

repo2ree consists of several running applications and two distinct kinds of
state. Separating them keeps coordination outside the environment that executes
repository code.

![The browser interface, API, Docker provider, isolated workbench, control-plane state, and durable REE tree](assets/services-and-storage.svg)

## Runtime elements

| Element | Responsibility |
|---|---|
| Browser interface | Guides authoring and review and presents runs and evidence. |
| API and control plane | Accepts requests, orchestrates runs, and manages REE placement. |
| Docker provider | Owns its host's container runtime, creates and removes workbenches, and injects the executor and tools. |
| Per-REE workbench | Runs repo2ree operations, builds runtime artifacts, and executes experiments. |
| Control-plane state | Stores routing, run records, staged uploads, and the REE index. |
| Durable REE tree | Stores one REE's source, overlay, workspace, artifacts, results, runs, and reviews. |

## Ownership boundaries

The API does not control the container runtime directly. The provider connects
outward to the control plane and creates environments on its behalf. Once a
workbench exists, it holds its own outbound connection, and commands travel to
it directly rather than through the provider.

Control metadata and REE contents also have different owners. The control plane
keeps routing and operation state; the workbench volume keeps the durable REE
tree. A workbench can therefore be recreated around persisted REE state.

Deployment details such as proxies, replicas, and host layout are outside this
map. The next pages open the [control plane](control-plane.md) and the
[compute side](workbench.md) to show their internal responsibilities.
