# Frequently asked questions

## Is repo2ree a hosted IDE?

No. repo2ree is not where researchers write their code. It starts with an
existing repository or source archive and helps turn it into a reproducible,
reviewable, archivable artifact.

## Does repo2ree replace Docker, Nix, Zenodo, or Software Heritage?

No. Those are substrates. repo2ree connects source, runtime, experiment
evidence, and archive metadata so those tools can form one reproducibility
workflow.

## Why does repo2ree ask so much of the author?

The author knows how the software builds and runs; a future reviewer may not.
Recording that knowledge once prevents each reader from reconstructing it by
guesswork. Script inference reduces the effort by proposing build and run
scripts, but the author must confirm what the code does.

## Is a Repro Label a grade?

No. It is a disclosure. It should show evidence and risks: what is pinned, what
is missing, what can drift, and what a reviewer should know before trying to
run the artifact. The REE assessment separately tracks freshness and payload
state across lifecycle evidence.

## Does a passing verify script mean the result was reproduced?

Not by itself. It means that one run satisfied its declared validation. During
authoring, that creates a baseline. Reproduction requires a later run to be
compared with prior author evidence or a predecessor receipt.

## Does Seal mean the result is trusted?

No. Seal means the REE has been frozen into a stable bundle. Trust comes from
the evidence around it: run results, comparison policies, signatures, archive
records, and independent verification.

## Does Archive mean repo2ree stores the artifact forever?

No. repo2ree prepares archive-ready bundles and metadata. Long-term
preservation belongs to archives such as Software Heritage, Zenodo, Dataverse,
or institutional repositories.

## Do I need Docker?

For the current local prototype, yes. It provisions Docker-backed workbenches.
The architecture also supports a future path to stronger or institution-owned
execution environments.

## Where are contributor docs?

Contributor and operator documentation lives in the source repository. This
website is for people using repo2ree, not for local development or service
operation.
