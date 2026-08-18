# Public concept reference

These are the public names repo2ree uses. They define the terms used throughout
the tutorials and guides without exposing internal implementation vocabulary.

## Vocabulary boundary

Four related terms describe different evidence and must not be used as
synonyms:

| Term | Meaning |
|---|---|
| **Evaluate** | A source-repository assessment. It reports declarations, risks, and independent dependency/environment/machine axes before a build proves anything. |
| **REE assessment** | A derived per-step view of evidence freshness and payload presence. It is not an independent reproduction verdict. |
| **Validation** | One run satisfied its declared check: the run script exited successfully and, when present, the author-provided verify script passed. |
| **Reproduction** | A later run is compared with prior author evidence or a predecessor receipt. A validated author run creates the baseline; it is not itself a reproduction. |

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

## Runtime artifact

The runnable environment built from the declared instructions. It may be a
Docker/OCI image archive, a packed virtual environment, or another artifact
that the REE's self-contained scripts know how to restore and enter.

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
and archive metadata. [What is an REE?](../explanation/what-is-an-ree.md)
explains the idea; [Anatomy of an REE](ree-anatomy.md) gives its directory
layout and the `ree.json` schema.

## Repro Label

A source-level disclosure produced by Evaluate. It explains what is declared,
pinned, drifting, or missing on independent axes. It is a nutrition label, not
the aggregate REE assessment.

## REE assessment

A derived view of the assembled REE across source, evaluation, hardware,
runtime, SBOM, activation, and experiments. It reports evidence as current,
stale, missing, or not applicable and separately reports whether payload bytes
are present, omitted, or missing.

## Run Receipt

The immutable typed record of one successful operation: its identity, timing,
inputs, relevant digests, and result evidence. Author and reviewer operations
already persist receipts, while the independently citable wrapper described by
the long-term design still needs predecessor lineage, signatures, and a deposit
format. An experiment run also records a digest of its declared outputs,
captured into a per-experiment results store — the baseline a reviewer diffs against and the
signal that flags a result whose bytes drifted before it was sealed.

A successful author run whose verify script passes is **validated**. Calling it
**reproduced** requires a later run related to this baseline or receipt.

## Verify

The reviewer or reader workflow: acquire source into an isolated attempt,
rebuild and compare the runtime, test activation, re-run declared experiments,
execute the author-provided verify scripts, and keep receipts plus comparison
verdicts without changing the author's evidence.

## Seal

The freeze point before sharing or archiving. Seal creates an immutable
downloadable bundle and a canonical `ree_digest` over the REE subject and its
bundle inventory. The target design extends that identity with detached
signatures, timestamp evidence, and archive attestations.

## Archive

The workflow that prepares a sealed REE for durable repositories such as
Software Heritage, Zenodo, Dataverse, or institutional archives. repo2ree
prepares the bundle and metadata; the archive preserves it.
