# repo2ree — Current Product Gaps

> Status: implementation-grounded research roadmap, 2026-08. This is a product
> analysis, not the implementation contract. Current behavior is documented in
> the public capability status and engineering references.

repo2ree now has both sides of its central loop. Authors can acquire source,
evaluate it, build and inspect a runtime, validate activation and experiments,
capture typed receipts, and seal a portable bundle. Reviewers can load that
bundle, reproduce source/build/activation/experiments in an isolated attempt,
and retain receipts plus comparison verdicts without changing author evidence.

The next step is no longer “add a review loop.” It is to make the evidence that
loop already produces portable, citable, and durable beyond one service node.

## Current foundation

- Successful author operations produce immutable typed receipts in the portable
  REE aggregate (`core/domain/ree/receipt.py`).
- Review operations produce attempt-scoped receipts and comparisons for source,
  runtime/SBOM closure, activation, and experiments
  (`core/evidence/review/`, `core/operations/handlers/review/`).
- The GUI exposes the gated review chain and per-experiment verdicts.
- Seal records a canonical `ree_digest`, bundle-entry inventory, and immutable
  ZIP, then writes a durable node-local REE index entry.
- Bundles ship `run.sh` and `REPRODUCING.md`, so reproduction is possible without
  installing repo2ree.

## Pillar 1 — Portable and citable verification evidence

Review evidence currently lives under the workbench's review-attempt namespace.
Make it an artifact that can leave that workbench and retain its meaning:

- define a portable verification envelope over reviewer receipts, comparisons,
  evidence basis, and the author `ree_digest`;
- add explicit predecessor/baseline identity where a comparison refers to an
  author receipt;
- include or content-address logs and selected output evidence;
- export a review independently, without mutating or resealing the author's REE;
- render a stable human-readable report from the same typed evidence.

The important distinction already exists in code and must survive export:
`independent` evidence supports a reproduction claim, while `bundled` evidence
certifies the integrity or ability to replay what the bundle already carried.

## Pillar 2 — Archive deposits and attestations

The adapter interfaces, provider models, archive UI, and REE index exist, but
live external deposits are not wired. Complete one provider end to end before
expanding the abstraction:

- create and publish a draft deposit;
- bind the archive-issued identifier to the exact `ree_digest`;
- append that binding to the durable REE index;
- expose retry/idempotency and failure semantics;
- verify archive presence after publication.

Zenodo is the narrowest first vertical slice. Software Heritage source-presence
checks and Dataverse can follow once the binding contract has been exercised by
one real service.

## Pillar 3 — Trust over time

The current seal gives content identity, not external trust. Extend it without
changing the digest it names:

- detached typed signatures over `ree_digest`;
- timestamp evidence and algorithm identifiers;
- digest-migration attestations when algorithms age;
- scheduled rebuild/review jobs that report drift against earlier evidence;
- retention rules for the indexed bundle bytes, not only their metadata.

## Pillar 4 — Discovery, reuse, and version relations

The durable REE index now provides a real starting point for consumer discovery.
It lists seals and archive bindings, but does not yet provide:

- search and filtering by catalog metadata, runtime, or evidence standing;
- explicit version/predecessor relations between different sealed subjects;
- fork/re-instantiate workflows that preserve lineage;
- resolution from a DOI/PID or peer index entry to retrievable bundle bytes.

## Lower-priority ecosystem work

- Standard exports such as RO-Crate, CodeMeta, OCI artifacts, or Nix flakes.
- Rebuild-tier dependency closure capture and replay after upstream disappearance.
- Hardware-aware placement based on declared and observed HBOM constraints.
- Multi-user ownership, authorization, quotas, and policy enforcement.

## Recommendation

Build the portable verification envelope and one live archive-deposit vertical
slice next. Together they turn the already-implemented review verdict from
workbench-local evidence into a citable claim bound to a sealed REE.
