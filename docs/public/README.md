# repo2ree documentation

repo2ree turns research repositories into reusable, verifiable, citable
execution artifacts. It binds code, runtime instructions, experiment runs, and
archive metadata into a Reproducible Execution Environment (REE). It is not an
environment for writing code.

New here? Read [What is an REE?](explanation/what-is-an-ree.md) for the problem
and the object that answers it, then work through
[Create your first REE](tutorials/create-your-first-ree.md).

repo2ree is an active prototype. These pages describe both what works today and
what the target design adds; [Current capabilities](reference/current-status.md)
says which is which.

## Explanation

Background on the problem repo2ree addresses and the shape of its answer.

- [What is an REE?](explanation/what-is-an-ree.md) — the central concept: what
  the object is and why it is shaped that way.
- [What is repo2ree?](explanation/what-is-repo2ree.md)

## Tutorials

Guided, end-to-end lessons for readers who have not built an REE before.

- [Overview](tutorials/README.md)
- [Create your first REE](tutorials/create-your-first-ree.md) — use the GUI to
  turn a Python source archive into a sealed, runnable bundle.

## How-to guides

Task recipes for a specific goal, once you know your way around.

- [Evaluate a repository](how-to/evaluate.md)
- [Build and run an REE](how-to/build-and-run.md)
- [Verify a result](how-to/verify.md)
- [Archive and share an REE](how-to/archive.md)

## Reference

Lookup material: vocabulary, current scope, and how the system is put together.

- [Concepts](reference/concepts.md)
- [Anatomy of an REE](reference/ree-anatomy.md) — the directory layout and the
  `ree.json` schema.
- [Current capabilities](reference/current-status.md)
- [System architecture](reference/architecture/README.md)
- [Frequently asked questions](reference/faq.md)

## Project documentation

This website contains end-user documentation. Contributor operations,
engineering decisions, detailed designs, and research notes remain in the
source repository.
