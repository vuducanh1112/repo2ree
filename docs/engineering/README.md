# repo2ree Engineering Documentation

Contributor-facing documentation: how to run the thing, how to test it, how to
ship it, and why the backend is shaped the way it is.

## How-to guides

| Doc | What it covers |
|---|---|
| [Development setup](how-to/development.md) | Toolchain, initial setup, running the app locally, devcontainer, configuration, package layout, common commands. |
| [Testing](how-to/testing.md) | The test tiers (`make` targets), Docker-gated suites, e2e projects, coverage, the commit and push gates. |
| [Deployment](how-to/deployment.md) | Images and registries, the compose stacks, the agent deployment, environment configuration. |

## Explanation

These record *why* the backend code is shaped as it is. The modules themselves
document what each piece does; these pages carry the argument, so it lives in one
place instead of being restated in every docstring that touches it.

| Doc | What it covers |
|---|---|
| [Step lifecycle](explanation/step-lifecycle.md) | The author and review step lifecycles, what `operations/steps/` owns, where the shared abstraction deliberately stops, and the `require_*` caller protocol. |
| [Review evidence](explanation/review-evidence.md) | What a review attempt certifies: verdict ladders per step, evidence bases (`independent` vs `bundled`), and why activation has no comparison. |
| [Script inference](explanation/script-inference.md) | How author-facing scripts are proposed: the decision DAG as sole control-flow authority, score-free resolution, and the upstream-only scan rule. |

## Tutorials

No contributor tutorial exists yet. The development setup is a task-oriented
procedure, not a learning path, and remains under how-to.

## Engineering decisions

Consequential choices and their tradeoffs live in the
[engineering decision log](decisions/README.md). The records preserve why a
choice was made; the architecture documents below remain the living description
of the system.

## Where the rest lives

- [Architecture reference](../reference/architecture.md) — execution and isolation: the `/ree`
  tree, the control/execution plane split, the typed action envelope, CAS, bundles.
- [Component reference](../reference/components.md) — package architecture, the dependency
  rules and the import-linter contracts that enforce them.
- [Concept reference](../reference/concepts.md) — normative definitions of the named concepts.
- [../public/](../public/) — product-facing docs and workflows.
- [../research/](../research/) — positioning, roadmap, and paper-facing notes.
