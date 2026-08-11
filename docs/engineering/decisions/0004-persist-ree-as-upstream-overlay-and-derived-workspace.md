# 0004 — Persist an REE as upstream, overlay, and derived workspace

- **Status:** accepted
- **Date:** original date unknown; retrospectively recorded 2026-08-11
- **Decision owners:** repo2ree maintainers

## Context

repo2ree must preserve the acquired source, add authoring material without
rewriting that source, run tools against a conventional working tree, retain
evidence, and package enough state to reconstruct or review an REE. Treating one
mutable checkout as all of those things makes source identity ambiguous and
allows generated or runtime files to become accidental inputs.

The running workbench is replaceable; the REE must survive it.

## Decision

Use a durable `/ree` tree with distinct roles:

- `upstream/` is the pristine acquired source snapshot;
- `overlay/` contains repo2ree-authored definition and scripts;
- `workspace/` is the derived, materialized execution view;
- `artifacts/`, `results/`, `runs/`, and `reviews/` retain produced evidence and
  execution history.

Upstream and overlay are authoritative inputs. Workspace is disposable and may
be rebuilt by materializing those inputs. The durable tree, not the running
container, is the REE state that a workbench must preserve or rehydrate.

## Alternatives considered

- **Modify the acquired checkout in place.** This obscures which bytes belong
  to the source and makes source identity and non-invasive adoption unreliable.
- **Treat the workspace as authoritative.** Runtime output and generated files
  can contaminate later inference, builds, or seals.
- **Treat the workbench container as the durable object.** This couples state to
  one runtime instance and makes teardown, migration, and archival composition
  difficult.

## Consequences

- Source identity and repo2ree-authored material remain distinguishable.
- Materialization must be deterministic and reset stale workspace state.
- Analysis and inference that describe the source must scan `upstream/`, not the
  workspace.
- Paths and mutation rules form a contract shared by core, bundles, review, and
  generated reproduction scripts.
- Workbenches can be destroyed and recreated if their durable tree is retained.
- Storage costs include source, derived workspace, artifacts, results, and
  review trees unless lifecycle policy reclaims them.

## Evidence

- [Working-environment directory layout](../../reference/architecture.md#working-environment-directory-layout)
- [State ownership](../../reference/architecture.md#state-ownership-portable-aggregate-and-durable-tree)
- [Script inference: scan upstream](../explanation/script-inference.md#scan-upstream-never-the-workspace)
- [`repo2ree_core.persistence`](../../../core/src/repo2ree_core/persistence/)
- [`repo2ree_core.workspace`](../../../core/src/repo2ree_core/workspace/)
