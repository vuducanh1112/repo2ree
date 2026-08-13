# How to evaluate a repository

Evaluate is the first public-facing question repo2ree answers:

> How reproducible does this repository look before anyone spends hours trying
> to rebuild it?

The current app scans the repository and reports reproducibility evidence such
as dependency declarations, manifest files, runtime hints, and risks. The result
is the seed of a Repro Label: a source-level assessment on independent axes.

## When to use it

Use Evaluate when you want to:

- understand whether a repository is ready for review or archival work;
- see which dependencies and manifests repo2ree detects;
- identify missing or weak reproducibility evidence before building;
- communicate reproducibility state without pretending it is a pass/fail grade.

## What it tells you

Evaluate should be read as disclosure. A low or incomplete result does not mean
the science is wrong. It means the artifact has reproducibility risks that need
to be explained, fixed, or captured elsewhere.

Typical findings include missing lockfiles, floating image tags, loosely
declared dependencies, absent runtime instructions, or incomplete environment
metadata.

## Relationship to the REE assessment

Evaluate and the REE assessment answer different questions. Evaluate reports
what the source repository declares. The assessment reads the REE definition,
receipts, and bundle contents to report current evidence and available payloads.
Evaluate can inform later runtime-SBOM reconciliation, but it does not validate
a result or prove a reproduction.

## What it does not prove

Evaluate does not prove that the repository builds, that a run satisfies its
declared validation, that a later run reproduces prior evidence, or that an
archive can preserve every dependency. Those questions need the build, run,
verify, and archive workflows.

For the deeper design, see [Repro Label](../reference/concepts.md#repro-label).
