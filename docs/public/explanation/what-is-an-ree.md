# What is an REE?

A Reproducible Execution Environment (REE) is a portable description of a
computational result. It binds source code to a runtime recipe, experiment
commands, verification criteria, and evidence from the author's runs.

## Why an REE exists

Research code often looks reproducible but leaves important questions open:

- Which source revision produced the result?
- Which compiler, system libraries, and transitive dependencies were present?
- Which command and arguments did the author run?
- What output counts as success?
- Can the work still run if a registry or hosting service disappears?

Repositories, containers, workflow tools, and archives each answer part of this
problem. An REE connects them and records the tests that link each part.

## What an REE contains

The downloadable bundle created by
[Create your first REE](../tutorials/create-your-first-ree.md) has this shape:

```text
run.sh                         standalone reproduction commands
REPRODUCING.md                 instructions for using run.sh
ree/
├── ree.json                   declarations, receipts, and seal metadata
├── snapshot.tar.gz            frozen source, when included
├── acquire_source.sh          restores or fetches the source
├── materialize_workspace.sh   creates a clean workspace
├── overlay/
│   └── ree-scripts/
│       ├── build_script.sh
│       ├── activation.sh
│       └── experiments/
│           ├── python-hello.sh
│           └── python-hello.verify.sh
├── artifacts/
│   ├── runtime.tar             built runtime, when included
│   ├── sbom.json
│   └── reproducibility-report.json
└── results/
    └── python-hello/
        └── result.txt          author baseline, when included
```

The parts have distinct roles:

- **Source** identifies the code. A bundled snapshot avoids dependence on the
  original host.
- **Overlay scripts** say how to build, activate, run, and verify the work.
- **Artifacts** hold derived evidence such as the runtime, SBOM, and readiness
  report. The runtime itself is optional at seal time.
- **Results** hold optional author baselines for later comparison.
- **Receipts in `ree.json`** bind scripts and outputs by digest and record what
  each operation produced.
- **`run.sh`** recreates the lifecycle without a repo2ree installation.

For every field and receipt, see
[Anatomy of an REE](../reference/ree-anatomy.md).

## Source, overlay, and workspace

An REE keeps the acquired source immutable. Authoring scripts live in a separate
overlay. repo2ree combines both layers into a mutable workspace:

```text
frozen source + REE overlay -> workspace
```

Builds and experiments run from the workspace root. repo2ree derives the
workspace, so it can discard and recreate it. This prevents generated files and
old run output from becoming part of the source by accident.

The separation also avoids rewriting the original repository. An author can
improve the reproduction instructions while preserving the exact published
source. When possible, authors should still commit project improvements such as
a lock file or Dockerfile upstream.

## Declarations and evidence

Declarations state intent: which script to run, where the runtime should appear,
which outputs matter, and how to verify them.

Receipts record observed execution: script digests, runtime and result digests,
tool versions, and outcomes. If a declaration changes, repo2ree marks dependent
evidence stale. A reviewer can therefore distinguish a current result from one
produced by an older script.

## Reproducing without repo2ree

A sealed bundle includes a portable POSIX `run.sh` and human-readable
instructions. The script can acquire source, materialize a clean workspace,
build or restore the runtime, test activation, and run experiments.

It does not make every computer compatible. The recipient still needs a POSIX
shell, basic archive tools, and the runtime backend used by the scripts, such as
Docker. Hardware-dependent work may also require the hardware described by the
REE.

The standalone script executes the recorded checks. A formal repo2ree review
adds comparison with the author's receipts and baselines.

## What an REE is not

An REE is not an archive. It is an object that an archive can preserve and
identify.

It is also not proof that the science is correct or that every machine will
produce the same bytes. Instead, it makes narrower claims checkable: what ran,
in which environment, what it produced, and which criterion passed. When a
later run differs, the evidence helps locate the disagreement.
