# repo2ree Public Documentation

> Status: public docs draft, 2026-06. These pages are written for a website
> audience. They describe what repo2ree is, what the current prototype can do,
> and which pieces are still target design.

repo2ree turns research repositories into reusable, verifiable, citable
execution artifacts. It is not a new workbench for writing code. It is the
layer that takes code, runtime instructions, experiment runs, and archive
metadata and binds them into a Reproducible Execution Environment, or REE.

## Explanation

- [Understanding repo2ree](explanation/what-is-repo2ree.md)

## How-to guides

- [Evaluate a repository](how-to/evaluate.md)
- [Build and run an REE](how-to/build-and-run.md)
- [Verify a result](how-to/verify.md)
- [Archive and share an REE](how-to/archive.md)

## Reference

- [Current capability status](reference/current-status.md)
- [Public concept reference](reference/concepts.md)
- [Frequently asked questions](reference/faq.md)

## Tutorials

A guided first-REE tutorial is not written yet. The current how-to guides assume
the reader already knows which task they need to complete; the GUI golden-path
demo and API walkthrough are the executable source for a future tutorial.

## Deeper background

These public docs are the short, website-facing layer. The heavier design and
paper-oriented notes stay one level up:

- [Concept reference](../reference/concepts.md)
- [Research notes](../research/README.md)
- [Positioning](../research/POSITIONING.md)
- [Architecture](../reference/architecture.md)
- [Component architecture](../reference/components.md)
- [Sealing and signatures](../research/sealing.md)
- [Archive and dependency preservation](../research/archive.md)

Contributor setup, deployment, and test instructions are separate:
[engineering docs](../engineering/README.md).
