# Architecture diagrams

Architecture diagrams are standalone, committed SVG files so readers can view
them without a renderer or development environment. The canonical system maps
live beside their published descriptions:

- [The repo2ree ecosystem](../public/reference/architecture/ecosystem.md)
- [Services, workbenches, and data stores](../public/reference/architecture/services-and-storage.md)
- [How the control plane is organized](../public/reference/architecture/control-plane.md)
- [How the workbench agent is organized](../public/reference/architecture/workbench-agent.md)
- [Federated compute through connected agents](../public/reference/architecture/federated-compute.md)
- [How a pipeline stage runs](../public/reference/architecture/pipeline-stage-execution.md)
- [How independent reproduction works](../public/reference/architecture/independent-reproduction.md)
- [`workflows/authoring-lifecycle.svg`](workflows/authoring-lifecycle.svg) is a
  companion workflow derived from the GUI and HTTP API end-to-end demos.

The SVG files are currently maintained by hand. Generated diagnostic diagrams
under `dist/diagrams/` are separate, disposable views and are not documentation
sources.

Component views group modules by responsibility, not source file. Dynamic views
reuse elements from the static views and number interactions in execution order.
