# System architecture

repo2ree separates coordination from isolated execution. The control plane
accepts requests and tracks progress, while each REE gets its own workbench: an
isolated environment where the requested operations actually run. This section
describes that system from its outer boundary down to two important execution
flows.

## Architecture maps

1. [The repo2ree ecosystem](ecosystem.md) introduces the people and external
   systems that participate in authoring and reproduction.
2. [Services, workbenches, and data stores](services-and-storage.md) shows the
   running applications and where they keep state.
3. [How the control plane is organized](control-plane.md) describes request
   handling, orchestration, workbench routing, and run tracking.
4. [How workbenches are provisioned and driven](workbench.md) describes the two
   compute-side deployables: the provider that creates a workbench and the
   service that executes inside one.
5. [Federated compute through connected providers](federated-compute.md) shows
   how private, university, institutional, and cloud resources can participate
   without giving the control plane their infrastructure credentials.

## Execution flows

- [How a pipeline stage runs](pipeline-stage-execution.md) follows one
  asynchronous operation from request to durable evidence.
- [How independent reproduction works](independent-reproduction.md) follows a
  published REE through an isolated review attempt.

Each page is useful on its own. Follow them in order when you want to move from
the product's surroundings toward its implementation boundaries.
