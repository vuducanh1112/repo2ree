# 0001 — Separate control and execution planes

- **Status:** accepted
- **Date:** original date unknown; retrospectively recorded 2026-08-11
- **Decision owners:** repo2ree maintainers

## Context

repo2ree executes repository-supplied build and experiment scripts. The product
also needs a user-facing API, durable intent and metadata, workbench lifecycle,
and streamed results. Letting the process that serves users execute those
scripts or directly own their container runtime would combine application state,
runtime credentials, and untrusted execution in one trust boundary.

Execution may also move between a local Docker host, institutional compute, and
future substrates without changing the authoring and review workflows.

## Decision

Separate repo2ree into a control plane and an execution plane.

The API and supervisor own intent, REE-to-workbench registration, lifecycle
requests, and result presentation. A runtime-owning agent provisions and drives
isolated workbenches. Inside a workbench, the executor invokes core operations
against that REE's tree. The control plane does not execute core operations and
does not hold a container-runtime socket.

## Alternatives considered

- **Run core operations in the API process.** This removes transport plumbing
  but puts untrusted execution and application serving in one process and host.
- **Give the supervisor direct Docker access.** This simplifies discovery and
  provisioning but couples the control plane to one substrate and gives it
  runtime credentials.
- **Make the supervisor a separate daemon.** This adds an IPC boundary without
  separating the runtime-owning trust boundary; the supervisor remains a
  library hosted by the API or a future CLI.

## Consequences

- Runtime credentials and substrate-specific code remain on the agent host.
- The same control-plane workflows can address different execution locations.
- Workbench locations are opaque agent-owned values; the control plane must
  persist its registry instead of reconstructing state with `docker inspect`.
- Commands, logs, results, cancellation, transfers, and health need explicit
  boundary protocols.
- Local development requires both the control plane and a reachable agent.

## Revisit when

Revisit the process topology if fleet-wide scheduling or background work needs
an independently scalable control-plane worker. Such a worker should still use
the supervisor library and preserve the execution boundary.

## Evidence

- [Component architecture](../../COMPONENTS.md#mental-model)
- [Control plane and execution plane](../../ARCHITECTURE.md#control-plane--execution-plane-split)
- [`repo2ree_agent.app`](../../../agent/src/repo2ree_agent/app.py)
- [`repo2ree_supervisor`](../../../supervisor/src/repo2ree_supervisor/)

