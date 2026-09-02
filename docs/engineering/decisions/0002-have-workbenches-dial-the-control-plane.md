# 0002 — Have compute-side services dial the control plane

- **Status:** accepted
- **Date:** original date unknown; retrospectively recorded 2026-08-11
- **Decision owners:** repo2ree maintainers

## Context

Execution hosts may sit behind NAT, cluster ingress policy, or institutional
firewalls. The control plane must dispatch work and stream frames without
requiring an inbound service on each runtime host or taking custody of SSH keys,
kubeconfigs, cloud credentials, or other user infrastructure credentials.

## Decision

Each compute-side service initiates one outbound WebSocket connection to the
control plane, identifies itself, and serves typed requests over that same
connection. A provider dials in to offer capacity; each workbench it creates
dials in separately to execute commands. The control plane routes every later
operation for an REE to that REE's own workbench connection.

Neither service exposes a listening control port. Credentials for Docker or a
future execution substrate remain inside the user's or institution's boundary.

## Alternatives considered

- **Control plane connects to a listener on the execution host.** This requires
  a network-reachable inbound endpoint and per-host ingress configuration.
- **Control plane connects directly through SSH or provider APIs.** This makes
  the service a custodian of powerful infrastructure credentials and embeds
  substrate-specific policy in the control plane.
- **Polling for jobs without a persistent channel.** This can preserve outbound
  connectivity but complicates low-latency frame streaming and cancellation.

## Consequences

- Providers and workbenches work from NATed and egress-only environments.
- The control plane needs connection identity, reconnection, routing, and stale
  registration behavior.
- One multiplexed channel carries concurrent requests, responses, logs,
  transfers, and cancellations, so every frame needs request identity.
- Workbench availability is a hard precondition for execution, while non-executing
  authoring operations can remain available.

## Revisit when

Revisit the transport if scale, delivery guarantees, or intermittent execution
hosts require a durable queue. Preserve the outbound trust direction unless the
deployment model itself changes.

## Evidence

- [Component call graph](../reference/components.md#call-graph--what-is-and-isnt-a-process-boundary)
- [`repo2ree_workbench.connection`](../../../workbench/src/repo2ree_workbench/connection.py)
- [`repo2ree_provider_docker.connection`](../../../provider/src/repo2ree_provider_docker/connection.py)
- [`protocol.workbench`](../../../protocol/src/repo2ree_protocol/workbench.py)
- [`protocol.provider`](../../../protocol/src/repo2ree_protocol/provider.py)
