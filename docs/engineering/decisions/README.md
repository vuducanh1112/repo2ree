# Engineering decision records

This directory records consequential engineering decisions that continue to
constrain repo2ree. The records explain why a choice was made, which alternatives
were rejected, and which consequences the project accepts.

These are historical decision records, not the living architecture reference.
[Architecture](../reference/architecture.md) and
[component architecture](../reference/components.md) describe the implemented and
target system; the records here explain accepted decisions behind the current
shape. When the implementation changes, update the living documentation and
supersede the affected record rather than rewriting its original decision.

## When to write a record

Write a decision record when a choice:

- crosses a process, package, trust, persistence, or public-contract boundary;
- has meaningful alternatives and consequences;
- is expensive to reverse or likely to be questioned again; or
- establishes an invariant that automated architecture checks should enforce.

Do not use a decision record for a local refactor, a temporary implementation
detail, a feature description, or a procedure. Those belong in code, issues,
how-to documentation, or the living architecture reference.

## Statuses

- **proposed** — under consideration and not yet authoritative;
- **accepted** — the current decision;
- **rejected** — considered but not adopted;
- **superseded** — replaced by a later record, which both records must link;
- **deprecated** — still present but intentionally being removed.

Accepted records are immutable except for status, supersession links, and
corrections that do not change the decision. A reversal gets a new record.

## Naming and metadata

Files use a stable four-digit sequence and a short descriptive slug:
`0001-separate-control-and-execution-planes.md`. Numbers identify records; they
do not imply priority. New records copy [template.md](template.md).

A retrospective record documents a decision that predates this log. Its date
line says when it was recorded and explicitly marks the original decision date
as unknown; it must not invent a historical date from a later commit or document.

## Accepted decisions

- [0001 — Separate control and execution planes](0001-separate-control-and-execution-planes.md)
- [0002 — Have runtime-owning agents dial the control plane](0002-have-agents-dial-the-control-plane.md)
- [0003 — Cross execution boundaries with typed commands](0003-use-typed-commands-across-execution-boundaries.md)
- [0004 — Persist an REE as upstream, overlay, and derived workspace](0004-persist-ree-as-upstream-overlay-and-derived-workspace.md)
- [0005 — Ship a POSIX shell reproducer in every bundle](0005-ship-a-posix-shell-reproducer-in-every-bundle.md)
