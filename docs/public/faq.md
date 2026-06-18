# FAQ

## Is repo2ree a hosted IDE?

No. repo2ree is not where researchers write their code. It starts with an
existing repository or source archive and helps turn it into a reproducible,
reviewable, archivable artifact.

## Does repo2ree replace Docker, Nix, Zenodo, or Software Heritage?

No. Those are substrates. repo2ree connects source, runtime, experiment
evidence, and archive metadata so those tools can form one reproducibility
workflow.

## Is a Repro Label a grade?

No. It is a disclosure. It should show evidence and risks: what is pinned, what
is missing, what can drift, and what a reviewer should know before trying to
run the artifact.

## Does Seal mean the result is trusted?

No. Seal means the REE has been frozen into a stable bundle. Trust comes from
the evidence around it: run results, comparison policies, signatures, archive
records, and independent verification.

## Does Archive mean repo2ree stores the artifact forever?

No. repo2ree prepares archive-ready bundles and metadata. Long-term
preservation belongs to archives such as Software Heritage, Zenodo, Dataverse,
or institutional repositories.

## Do I need Docker?

For the current local prototype, yes. The current demo provisions Docker-backed
workbenches. The architecture is designed so future runners can execute in
stronger or institution-owned environments.

## Where are contributor docs?

Contributor and operator docs are under [docs/engineering](../engineering/development.md).
The public docs are meant for website readers, not local development setup.
