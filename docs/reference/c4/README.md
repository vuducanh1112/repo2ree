# C4 architecture views

These pages pair each C4 diagram with the text needed to interpret it. Start at
the highest useful level and move inward only when you need more detail:

1. [System context](system-context.md) — people and systems around repo2ree.
2. [Containers](containers.md) — deployable runtime units and their stores.
3. Component views:
   - [API and control plane](component-api-control-plane.md)
   - [Workbench agent](component-agent.md)
4. Dynamic views:
   - [Execute one pipeline stage](dynamic-stage-execution.md)
   - [Reproduce a published REE](dynamic-review-reproduction.md)

The views describe the same system at different levels; a box changing between
views is usually being opened to show its internals, not replaced by another
system. The component boxes group architectural responsibilities and do not
promise a one-to-one mapping to source modules.

For cross-cutting details such as isolation, the `/ree` layout, state ownership,
and target design, see the [execution and isolation architecture](../architecture.md).
For package boundaries and dependency rules, see the
[component and package architecture](../components.md).

