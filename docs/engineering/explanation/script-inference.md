# Understanding Script Inference

> Status: current, Phase 1 = build inference (2026-07). Code lives in
> [`core/author_recipes/inference/`](../../../core/src/repo2ree_core/author_recipes/inference/).
> This page is the design overview; each module's docstring covers its own
> mechanics.

Script inference proposes repo2ree's author-facing shell scripts (the
`ree-scripts/` overlay) from evidence in the repository, and shows its work. It
is **read-only**: it produces candidate bytes and a trace, and never writes.
A caller may later persist a candidate through `writeReeFile`.

## The load-bearing rule

**The published, versioned decision DAG is the only control-flow authority.**

No parallel imperative rule implementation exists. The DAG is deployment-static
data — the sibling of `ree_step_catalog` — and the generic engine
(`engine.py`) walks exactly those nodes: invoking registered pure checks, fanning
into strategy branches, and joining their outcomes through a named resolver.

The same walk that produces the candidates produces the trace shown to the user,
so the graph can never drift from its own explanation.

`validate_dag` runs at **registry import time**, so a structurally invalid graph
fails the process at startup rather than at request time.

## Resolution is score-free

The resolver joins every strategy leaf's outcome and applies a fixed policy. It
never ranks strategies — "Docker 100 versus Conda 80" is not a valid model.
Multiple viable strategies are a **visible decision**, not a priority contest.

| Outcomes | Result |
|---|---|
| Exactly one viable complete outcome | `complete` |
| One or more other viable outcomes | `needs_input` |
| No viable outcomes | `not_inferred` |

"Viable" means `complete` or `candidate`. `blocked` and `not_applicable` leaves
are not viable but still travel in the observation, so the trace explains why the
resolver saw no viable strategy.

Adding an ecosystem means adding a fork branch and another input edge to the same
resolver — never a priority number.

## Scan upstream, never the workspace

`scan_repository` builds `RepositoryFacts` from the immutable acquired `upstream`
tree. This is the load-bearing scoping rule: scanning the materialized workspace
would let inference discover **its own output** — reserved scripts, generated
recipes, runtime artifacts — as evidence. Scoping to upstream needs no digest to
hold.

`resolve_logical_root` peels wrapper directories off the extracted tree using one
structural rule, taking only a directory path. A git clone lands contents at the
extraction root; a source archive commonly wraps everything under one
`project-name-main/`. Both resolve the same way.

Facts are deliberately richer than the aggregate reproducibility report:
generation decisions need physical paths, normalized project-root-relative paths,
and structural ambiguity, all of which the report's levels flatten away.

Inference is **stateless and always recomputes** — there is no persisted report.

## Phase 1: build inference

A shared project-root prefix, a fork into two strategy branches — `dockerfile`
and `pip` — and an explicit score-free resolver join.

The `dockerfile` branch is purely **locational**:

- more than one project-root Dockerfile → `blocked` (can't pick which);
- a nested Dockerfile → `blocked` on ambiguous build context;
- exactly one at the root → `complete`.

The `pip` branch yields a **`candidate`**, never a complete outcome: a generated
build strategy is viable but requires confirmation. A lone `requirements.txt`
resolves to `needs_input`, and a Dockerfile alongside it makes the two strategies
an explicit decision rather than a silent pick.

Both Phase 1 build strategies work from the repository's own declared technology
— a repository Dockerfile drives `docker build`, a requirements.txt drives a
`pip`/venv build — so neither consults a policy-supplied base image. The
base-image maps on the policy model are latent deployment config for future
strategies that genuinely synthesize a runtime substrate; nothing in Phase 1
reads them.

## Warnings are codes, not prose

Warning *meaning* must not live only in prose or shell comments. The API returns
stable codes with a fixed severity and a `blocking` flag, so a machine can
enforce automation policy without parsing text. `warnings.py` is the single
mapping from code to meaning, so a leaf that names a code cannot invent a new
meaning for it.

Only the codes Phase 1 can actually emit are defined; the reserved vocabulary
grows as the strategy that raises each one lands.

## Generated scripts fail closed

Activation and experiment run scripts share a scaffold: an empty `set --` the
author must fill with the command, and a guard that exits **64** if it is still
empty. When the runtime image declared any candidates, they are rendered as
*commented* `set --` examples — suggestions, never selected.

`set --` is a transparent, quoting-safe argv form: no `eval`, no accidental word
splitting, and no assumption that the runtime image has a shell.

## Module map

| Module | Role |
|---|---|
| `models.py` | The typed surface everything exchanges. Closed discriminated unions live here so no import cycle forms between machinery modules. |
| `engine.py` | The only thing that runs a DAG: startup validator and evaluator. |
| `registry.py` | The deployment surface — registered checks, resolvers, renderers, DAGs. |
| `decision_graphs/` | The versioned DAG data itself. |
| `checks/` | Pure checks the engine invokes. |
| `resolvers.py` | Score-free strategy join. |
| `renderers/` | Candidate shell bytes per strategy. |
| `repository_facts.py` | One upstream scan per request. |
| `policy.py` | Deployment policy (supported strategies, latent base-image maps). |
| `warnings.py` | The stable warning catalog. |
| `build_wiring.py` | The single wiring of checks, resolver, and renderers for the build DAG, shared by the registry and `build_regeneration` so the two cannot drift. |
| `inference.py` | Top-level entrypoint. |

## See also

- [step-lifecycle.md](step-lifecycle.md) — how a generated script is later run and receipted.
- [Concept reference](../../reference/concepts.md) — Overlay, REE, Repro Label.
