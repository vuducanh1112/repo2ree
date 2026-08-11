# 0002 — Have runtime-owning agents dial the control plane

- **Status:** accepted
- **Date:** original date unknown; retrospectively recorded 2026-08-11
- **Decision owners:** repo2ree maintainers

## Context

Execution hosts may sit behind NAT, cluster ingress policy, or institutional
firewalls. The control plane must dispatch work and stream frames without
requiring an inbound service on each runtime host or taking custody of SSH keys,
kubeconfigs, cloud credentials, or other user infrastructure credentials.

## Decision

The agent initiates one outbound WebSocket connection to the control plane,
identifies itself, and serves typed requests over that same connection. The
control plane routes every later operation for a workbench to the concrete agent
that provisioned it.

The agent exposes no listening control port. Credentials for Docker or a future
execution substrate remain inside the user's or institution's boundary.

## Alternatives considered

- **Control plane connects to an agent listener.** This requires a
  network-reachable inbound endpoint and per-host ingress configuration.
- **Control plane connects directly through SSH or provider APIs.** This makes
  the service a custodian of powerful infrastructure credentials and embeds
  substrate-specific policy in the control plane.
- **Polling for jobs without a persistent channel.** This can preserve outbound
  connectivity but complicates low-latency frame streaming and cancellation.

## Consequences

- Agents work from NATed and egress-only environments.
- The control plane needs connection identity, reconnection, routing, and stale
  registration behavior.
- One multiplexed channel carries concurrent requests, responses, logs,
  transfers, and cancellations, so every frame needs request identity.
- Agent availability is a hard precondition for execution, while non-executing
  authoring operations can remain available.

## Revisit when

Revisit the transport if scale, delivery guarantees, or intermittent execution
hosts require a durable queue. Preserve the outbound trust direction unless the
deployment model itself changes.

## Evidence

- [Component call graph](../../COMPONENTS.md#call-graph--what-is-and-isnt-a-process-boundary)
- [`agent.control.connection`](../../../agent/src/repo2ree_agent/control/connection.py)
- [`protocol.agent`](../../../protocol/src/repo2ree_protocol/agent.py)
