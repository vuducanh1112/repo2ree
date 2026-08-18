# What is an REE?

A Reproducible Execution Environment is an object defining a research project's
source code, the instructions for building the necessary runtime environment and
the instructions to run computational experiments.

## The problem it addresses

Published research code is usually reproducible in principle and not in
practice. The failures are mundane and they compound:

- **Code without its environment.** A repository records what the author wrote,
  not what they ran it against. The compiler version, the system libraries, and
  the dozens of transitive dependencies that resolved on the day are nowhere in
  the repository, and any of them can change the result.
- **Environments without provenance.** A container image fixes the environment
  and forgets where it came from. A reviewer holding one cannot tell which
  commit it was built from, or rebuild it if it disappears from the registry.
- **"What do I run?" answered in prose, or not at all.** A README is the usual
  place to look, and it is often missing, half-written, or describing the
  repository as it stood two years ago. Even a careful one leaves the question
  open: "run the training script" does not say which of the twelve scripts,
  with which arguments, in which order, or what the output looks like when it
  worked. And because the answer is prose, nothing can act on it — no tool can
  execute a README, check it, or notice when the code moves on and the text
  stays behind.
- **Claims with nothing behind them.** "All experiments run in under an hour on
  a single GPU" is a sentence in a paper. Nothing links it to a run that
  actually happened, so nothing can confirm or refute it short of redoing the
  work.
- **Decay.** Dependencies move, registries prune, services go offline. An
  artifact that was reproducible at publication quietly stops being so as the
  world around it changes.

Each of these has a good tool addressing it. The gap is that the tools do not
produce one object, so nothing holds the pieces together, and nothing states
which pieces were checked against which.

## What an REE contains

An REE is a directory holding the reference to the source code, the recipe for
building the runtime and running experiments inside it, the produced evidence,
and the manifest tying everything together.

Here is an example REE built in
[Create your first REE](../tutorials/create-your-first-ree.md) from a small
pandas script:

```text
run.sh                                      7.8 KB   reproduce it, without repo2ree
REPRODUCING.md                              3.7 KB   what run.sh does, for a human
ree/
├── ree.json                                4.9 KB   declarations, receipts, inventory, seal
├── snapshot.tar.gz                           743 B  the frozen source
├── acquire_source.sh                       2.2 KB   unpacks the snapshot into upstream/
├── materialize_workspace.sh                1.1 KB   merges upstream/ + overlay/
├── overlay/
│   └── ree-scripts/
│       ├── build_script.sh                   338 B  builds the runtime
│       ├── activation.sh                     340 B  proves the runtime can be entered
│       └── experiments/
│           ├── python-hello.sh               357 B  the experiment
│           └── python-hello.verify.sh         170 B  what counts as passing
├── artifacts/
│   ├── sbom.json                           1.0 MB   packages found in the runtime
│   └── reproducibility-report.json        15.6 KB   the Evaluate findings
└── results/
    └── python-hello/
        └── result.txt                        425 B  what the experiment produced
```

- **`run.sh`** — a POSIX script that provides a "one click" command to recreate
  the whole lifecycle: acquire source, create a workspace, build the runtime,
  test activate the runtime, run experiments.
- **`ree.json`** — the manifest file containing the metadata.
- **`snapshot.tar.gz`** — optional included source, so the REE is immune to
  unavailable code hosting.
- **`overlay/`** — the authored scripts specifying how the runtime is built,
  test activated, and how experiments are run.
- **`artifacts/`** — a Software Bill of Materials (SBOM) to describe the
  runtime. A reproducibility report of the source code.
- **`results/`** — optionally included results of the experiments to ensure
  rerunning experiments produce the "same" (however the author defines it)
  results.

Instead of text files describing how to reproduce the scientific results, all
relevant "instructions" are executable scripts, offering a streamlined review
experience.

For the full layout, the `ree.json` schema, and what each receipt records, see
[Anatomy of an REE](../reference/ree-anatomy.md). The rest of this page is
about why the object is shaped this way.

## Source and recipes stay separate

The obvious way to make a project reproducible is to fix it by specifying all
these things around experiment running in an executable way and committing it to
the original repository.

An REE keeps them apart instead. The acquired source is immutable, instead a
workspace is materialized by combining the source and the overlay which contains
all these reproducibility scripts. The workspace is mutable and where all file
changes happen during builds and experiments. It is derived, so it is
disposable: delete it and it rebuilds from the other two.

This separation also keeps the original source repository clean. Changes to
surrounding reproducibility concerns, e.g. swapping docker for podman, can be
done in isolation.

## Declaration and evidence

All the defined scripts are things that the author declared. The REE
additionally contains receipts that capture what running the declared scripts
produced. This way anyone trying to reproduce the findings can compare
re-executed results with what the author did before.

## Reproducible without repo2ree

A sealed bundle carries a reproducer script and human instructions at its top
level, and the same acquire and materialize scripts the workbench itself uses.
Running the `run.sh` script can be done on any machine, so even if this project
dies, old archived REEs can still be reproduced this way.

## What an REE is not

An REE is not an archive. It is a better object for an archive to preserve —
Software Heritage, Zenodo, and Dataverse still supply the durable storage and
the identifiers.

It is not a guarantee that the science is right, or that a result will
reproduce on your machine. Some results genuinely depend on hardware repo2ree
can only describe, not supply, which is why the hardware context is recorded
rather than assumed away. What an REE offers is a much narrower and more
useful thing: precise, checkable statements about what was run, on what, and
what came out — enough that a disagreement can be located instead of argued
about.
