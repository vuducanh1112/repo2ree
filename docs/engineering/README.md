# repo2ree — Engineering Docs

Contributor-facing documentation: how to run the thing, how to test it, how to
ship it, and why the backend is shaped the way it is.

## Setup and operations

| Doc | What it covers |
|---|---|
| [development.md](development.md) | Toolchain, initial setup, running the app locally, devcontainer, configuration, package layout, common commands. |
| [testing.md](testing.md) | The test tiers (`make` targets), Docker-gated suites, e2e projects, coverage, the commit and push gates. |
| [deployment.md](deployment.md) | Images and registries, the compose stacks, the agent deployment, environment configuration. |

## Backend design rationale

These record *why* the backend code is shaped as it is. The modules themselves
document what each piece does; these pages carry the argument, so it lives in one
place instead of being restated in every docstring that touches it.

| Doc | What it covers |
|---|---|
| [step-lifecycle.md](step-lifecycle.md) | The author and review step lifecycles, what `operations/steps/` owns, where the shared abstraction deliberately stops, and the `require_*` caller protocol. |
| [review-evidence.md](review-evidence.md) | What a review attempt certifies: verdict ladders per step, evidence bases (`independent` vs `bundled`), and why activation has no comparison. |
| [script-inference.md](script-inference.md) | How author-facing scripts are proposed: the decision DAG as sole control-flow authority, score-free resolution, and the upstream-only scan rule. |

## Where the rest lives

- [../ARCHITECTURE.md](../ARCHITECTURE.md) — execution and isolation: the `/ree`
  tree, the control/execution plane split, the typed action envelope, CAS, bundles.
- [../COMPONENTS.md](../COMPONENTS.md) — package architecture, the dependency
  rules and the import-linter contracts that enforce them.
- [../CONCEPTS.md](../CONCEPTS.md) — normative definitions of the named concepts.
- [../public/](../public/) — product-facing docs and workflows.
- [../research/](../research/) — positioning, roadmap, and paper-facing notes.
