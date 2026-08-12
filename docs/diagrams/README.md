# Architecture diagrams

This directory contains diagrams that are part of the documentation itself.
Standalone, committed SVG files let readers view them without a renderer or the
development environment.

The C4 diagrams have companion description pages in the
[C4 architecture reference](../reference/c4/README.md). This page indexes the
source assets themselves.

- [`c4/system-context.svg`](c4/system-context.svg) ([description](../reference/c4/system-context.md)) shows people and external
  systems around repo2ree, without exposing its internals.
- [`c4/container.svg`](c4/container.svg) ([description](../reference/c4/containers.md)) shows the runtime units and stores
  inside repo2ree.
- [`c4/component-api-control-plane.svg`](c4/component-api-control-plane.svg) ([description](../reference/c4/component-api-control-plane.md))
  decomposes the API and its in-process supervisor.
- [`c4/component-agent.svg`](c4/component-agent.svg) ([description](../reference/c4/component-agent.md)) decomposes the
  runtime-owning workbench agent.
- [`c4/dynamic-stage-execution.svg`](c4/dynamic-stage-execution.svg) ([description](../reference/c4/dynamic-stage-execution.md)) follows one
  pipeline command across the control-plane and execution-plane boundaries.
- [`c4/dynamic-review-reproduction.svg`](c4/dynamic-review-reproduction.svg) ([description](../reference/c4/dynamic-review-reproduction.md))
  follows an independent review from a published bundle to an attempt-scoped
  verdict.
- [`workflows/authoring-lifecycle.svg`](workflows/authoring-lifecycle.svg) is a
  companion workflow distilled from the GUI and HTTP API end-to-end demos. It
  is intentionally not labelled as a C4 view.

The SVG files are currently maintained by hand. Generated diagnostic diagrams
under `dist/diagrams/` are separate, disposable views and are not documentation
sources.

The component views intentionally group modules by responsibility. They do not
promise a one-to-one mapping between boxes and source files. The dynamic view
uses components and containers from the static views and numbers interactions
in execution order.
