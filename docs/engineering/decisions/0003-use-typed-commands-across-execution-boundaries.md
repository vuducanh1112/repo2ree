# 0003 — Cross execution boundaries with typed commands

- **Status:** accepted
- **Date:** original date unknown; retrospectively recorded 2026-08-11
- **Decision owners:** repo2ree maintainers

## Context

The control plane cannot call execution code in-process. Operations cross both
the supervisor-to-agent network boundary and the agent-to-workbench process
boundary. Shell command strings would make quoting, validation, compatibility,
auditing, and later replay depend on ad hoc interpolation.

repo2ree also needs structured logs and results that the GUI, API clients, and
future surfaces can interpret without parsing terminal prose.

## Decision

Represent execution requests as typed `Command` values in
`repo2ree_protocol`. The executor reads one serialized command from standard
input, invokes the corresponding core handler, streams typed `LogFrame` values,
emits an `ActionResult`, and exits.

The agent transports frames and invokes the executor but does not interpret or
perform the domain operation. Public surfaces assemble commands through the
same protocol instead of creating parallel execution paths.

## Alternatives considered

- **Transport interpolated shell or CLI strings.** This creates quoting and
  injection hazards and loses a stable operation schema.
- **Expose core through a server inside every workbench.** This adds a
  long-running network service, port lifecycle, and another API without removing
  the need for versioned messages.
- **Import core into the agent.** This collapses the workbench boundary and lets
  the runtime host perform operations outside the isolated environment.

## Consequences

- Boundary inputs and outputs can be validated, tested, recorded, and evolved.
- Protocol compatibility becomes a deliberate concern across independently
  deployed control plane, agent, and injected executor versions.
- Streaming and cancellation need typed frame protocols in addition to the
  command and final result.
- New operations require protocol models and dispatch wiring rather than an
  arbitrary shell escape hatch.
- Structured commands provide a basis for provenance, replay, and possible
  content-addressed execution without committing the project to a cache design.

## Evidence

- [The command envelope is the contract](../../ARCHITECTURE.md#the-command-envelope-is-the-contract)
- [`repo2ree_protocol.command`](../../../protocol/src/repo2ree_protocol/command.py)
- [`repo2ree_protocol.result`](../../../protocol/src/repo2ree_protocol/result.py)
- [`repo2ree_executor.cli`](../../../executor/src/repo2ree_executor/cli.py)

