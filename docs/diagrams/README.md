# Architecture diagrams

This directory contains diagrams that are part of the documentation itself.
Standalone, committed SVG files let readers view them without a renderer or the
development environment.

- [`c4/system-context.svg`](c4/system-context.svg) shows people and external
  systems around repo2ree, without exposing its internals.
- [`c4/container.svg`](c4/container.svg) shows the runtime units and stores
  inside repo2ree.
- [`c4/component-api-control-plane.svg`](c4/component-api-control-plane.svg)
  decomposes the API and its in-process supervisor.
- [`c4/component-agent.svg`](c4/component-agent.svg) decomposes the
  runtime-owning workbench agent.
- [`c4/dynamic-stage-execution.svg`](c4/dynamic-stage-execution.svg) follows one
  pipeline command across the control-plane and execution-plane boundaries.
- [`c4/dynamic-review-reproduction.svg`](c4/dynamic-review-reproduction.svg)
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
