# Concepts

These are the public names repo2ree uses. For the fuller design reference, see
[CONCEPTS.md](../CONCEPTS.md).

## Source

The original repository or source archive. repo2ree treats it as upstream
material and does not require changing it.

## Overlay

The material repo2ree adds beside the source: declarations, generated files,
runtime instructions, and packaging metadata. The overlay is how repo2ree can
make an existing project reproducible without rewriting the project itself.

## Workspace

The active working tree inside the REE workbench. It is where source and overlay
are materialized so commands can build, run, and inspect the artifact.

## Runtime image

The runnable environment built from the declared instructions. In the current
prototype this is Docker/OCI-shaped.

## SBOM

A Software Bill of Materials: a structured inventory of software packages and
dependencies found in the runtime.

## HBOM

A Hardware Bill of Materials: a structured description of the machine context
that can matter for reproduction, such as CPU, GPU, memory, storage, and
network details.

## REE

A Reproducible Execution Environment. Publicly, this is the object a researcher
can share: source identity, overlay, runtime evidence, run evidence, labels,
and archive metadata.

## Repro Label

A disclosure of reproducibility standing. It should explain what is pinned,
what is drifting, what evidence exists, and what risks remain. It is a
nutrition label, not a single grade.

## Run Receipt

The target durable record of one execution: command, inputs, parameters,
runtime, outputs, logs, result, and provenance. The current prototype has the
execution pieces; the durable receipt object is still being shaped.

## Verify

The reviewer or reader workflow: re-run a declared result, compare it against
the published expectation, and keep the new evidence as a verification record.

## Seal

The freeze point before sharing or archiving. In the current prototype, Seal
creates a sealed downloadable bundle. The target design gives the sealed REE a
canonical manifest and stable digest that signatures and archives can refer to.

## Archive

The workflow that prepares a sealed REE for durable repositories such as
Software Heritage, Zenodo, Dataverse, or institutional archives. repo2ree
prepares the bundle and metadata; the archive preserves it.
