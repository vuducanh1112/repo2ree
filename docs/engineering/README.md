# repo2ree engineering documentation

Contributor documentation for development, testing, deployment, and system
design.

## How-to guides

| Doc | What it covers |
|---|---|
| [Development setup](how-to/development.md) | Toolchain, initial setup, running the app locally, devcontainer, configuration, package layout, common commands. |
| [Testing](how-to/testing.md) | The test tiers (`make` targets), Docker-gated suites, e2e projects, coverage, the commit and push gates. |
| [Deployment](how-to/deployment.md) | Images and registries, the compose stacks, the agent deployment, environment configuration. |

## Explanation

These pages explain why the backend has its current shape. Module docstrings
describe individual mechanisms.

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

## Reference

- [Reference overview](reference/README.md) — technical concepts, architecture,
  and package boundaries.
- [Architecture reference](reference/architecture.md) — execution and isolation: the `/ree`
  tree, the control/execution plane split, the typed action envelope, CAS, bundles.
- [Component reference](reference/components.md) — package architecture, the dependency
  rules and the import-linter contracts that enforce them.
- [Concept reference](reference/concepts.md) — normative definitions of technical concepts.

Product workflows live in the [public docs](../public/). Positioning, plans,
and manuscript material live in [research notes](../research/).
