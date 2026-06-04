# repo2ree — Concepts

> **Status: concept reference (2026-05).** The **what** of repo2ree —
> normative definitions of the nouns, verbs, tiers, and states used
> across the project. For *why* these concepts exist see
> [POSITIONING.md](POSITIONING.md); for *how* they are implemented see
> [ARCHITECTURE.md](ARCHITECTURE.md).

## The integration this defines

repo2ree binds three substrate layers — **environments** (Docker, Nix,
VMs), **experiments** (MLflow, W&B, plain logs), and **archives**
(Software Heritage, Zenodo, PID4NFDI) — into one reproducibility
workflow. The concepts below are the *names* of that integration: the
**nouns** that travel between layers (Source, Overlay, REE, Repro
Label, Run Receipt), the **workflows** that bind them (Verify,
Archive), and the **tiers** and **states** that govern how they're
composed.

Each primitive and workflow declares which layers it integrates.

## Core nouns

### Source

The pristine repository at a fixed commit. Owned by the original author;
**never modified by repo2ree**. Lives in `/ree/workspace/` at runtime and
typically resolves to a Software Heritage identifier (SWHID) once archived.

A Source with a stable identifier (SWHID) is *Archive-ready*; a Source
that exists only locally is *Draft* (see [lifecycle states](#ree-lifecycle-states)).

### Overlay

repo2ree's contribution to the REE — sits *beside* the Source without
modifying it. Holds the declaration, generated build scripts, generated
Dockerfiles or flakes, and any other material that turns a bare
repository into a fully-specified environment. Lives in `/ree/overlays/`
at runtime; travels inline in the Archive bundle.

The Overlay model is what makes repo2ree non-invasive: a reviewer (or
the original author, or a third party) can wrap an existing repo without
committing anything back to the Source.

### REE — Reproducible Execution Environment

The *composition* of Source + Overlay + build = a runnable environment.
The unit the user thinks in. The REE is not any one file; it is the
structured tree (`/ree/`) plus the recipes that turn its inputs into its
outputs.

### Repro Label

*Integrates: Environment substrate → Lifecycle vocabulary.*

The repo's standing reproducibility disclosure. Scored on independent
axes — today: *dependency declaration*, *environment capture*; with
archival also: *source-identifier stability*, *closure-capturability*.

**Observational**: describes the repo as-is, without modifying it. A
nutrition label, not a grade. The Label reads whatever environment
substrate the repo brought (Dockerfile, flake.nix, conda env, plain
pip) and exposes it in lifecycle-layer vocabulary. **Primitive 1.**

### Run Receipt

*Integrates: Experiment substrate → Archive substrate.*

A single execution's structured, content-addressed record:

```
ree_digest      which environment exactly executed the run
action_digest   which command + inputs were issued
parameters      typed run-specific inputs (seeds, hyperparams, …)
outputs         produced files, content-addressed
traces          stdout, stderr, logs, metrics
result          the structured value the run advertised
signatures      optional executor attestation
predecessor     optional pointer to the run this re-derives
```

Receipts are immutable. They **wrap whatever the experiment substrate
produced**: an MLflow run becomes a Receipt with MLflow metadata
preserved; a Weights & Biases run becomes a Receipt pointing at the
W&B record; a plain Python script becomes a Receipt assembled from
stdout and outputs. The substrate stays the substrate; the Receipt is
the citable wrapper that pushes the run toward the archive.

Author-Receipts and reviewer-Receipts are **structurally identical**;
the `predecessor` pointer is what binds a reviewer's verification to
the author's original claim. **Primitive 2.**

## Workflows

### Verify

*Integrates: Archive substrate → Environment substrate → Experiment substrate.*

The reviewer's one-click moment. Composes the two primitives:

1. Load the repo's Repro Label; re-score against the local environment.
2. Re-execute each published Run Receipt against the same REE.
3. Each re-execution produces a new Receipt whose `predecessor` points at
   the author's.
4. Diffs are surfaced; the reviewer's Receipt set is itself depositable
   via [Archive](#archive) as a citable verification artifact.

Author and reviewer use the same machinery. There is no special "review
mode."

### Archive

*Integrates: Lifecycle artifacts → Archive substrates.*

The author's one-click deposit. Composes the primitives with
institutional archival infrastructure:

1. Compose the bundle: declaration + overlay + source-pointer + Receipts
   + Label + (artifacts by chosen [fidelity tier](#fidelity-tiers)).
2. Deposit on Zenodo via API; receive DOI.
3. Source-code components flow to Software Heritage automatically via the
   Zenodo–SWH integration; SWHIDs flow back into the bundle metadata.
4. Optionally bind a PID via PID4NFDI for NFDI-internal references.
5. The deposited bundle is now the canonical citable form of the REE.

repo2ree never archives anything itself; it composes archive-ready
bundles for services that do.

## Fidelity tiers

The author chooses a tier at Archive time. Each tier is a strict superset
of the previous. The chosen tier is recorded in the bundle metadata and
disclosed by the Label.

| Tier        | Contents                                                  | Re-runnable?           | Re-derivable?              | Storage |
|-------------|-----------------------------------------------------------|------------------------|----------------------------|---------|
| **Cite**    | declaration + overlay + source-pointer + Receipts + Label | iff upstreams alive    | iff upstreams alive        | KB–MB   |
| **Replay**  | Cite + the built runtime image                            | always (OCI + amd64)   | no                         | MB–GB   |
| **Rebuild** | Replay + inputs closure (vendored deps)                   | always                 | yes, against dead internet | GB      |

**Recommended default: Replay.** Long-term runnability without the cost
of closure capture; sufficient for most paper-supplementary use cases.

## REE lifecycle states

The REE moves through states as its archival readiness changes:

| State              | What's true                                                   | Eligible for canonical Archive?                                                |
|--------------------|---------------------------------------------------------------|--------------------------------------------------------------------------------|
| **Draft**          | Source has no stable identifier; actively being edited; pre-deposit iteration | No — bundles carry source bytes inline only as a temporary snapshot |
| **Archive-ready**  | Source resolves to an SWHID; declaration and overlay are stable | Yes                                                                          |
| **Deposited**      | Bundle deposited on Zenodo; DOI assigned; SWHIDs registered  | Already archived; future Archives create new versions                          |

Promotion Draft → Archive-ready happens when the source acquires a
stable identifier (push to a SWH-crawled forge; deposit via Zenodo's
`save_code_now`; or via SWH's direct deposit API).

## Use case → tier mapping

| Use case                                       | Recommended tier | Why                                                                                                  |
|------------------------------------------------|------------------|------------------------------------------------------------------------------------------------------|
| Paper supplementary material                   | **Replay**       | Reviewers and readers in 2034 need to *run* the artifact; rebuild rarely needed                      |
| Audit-grade artifact (regulated science)       | **Rebuild**      | Closed-world re-derivability required; bit-equal verification expected                               |
| Quick citation / preprint                      | **Cite**         | Just need a DOI; can be upgraded to Replay later when the paper finalizes                            |
| Lab onboarding / internal use                  | **Cite**         | Frequent rebuild from live upstreams; archival is secondary                                          |
| Course assignment                              | **Replay**       | Instructor wants reliable re-run year-over-year regardless of upstream drift                         |
| Long-term archival (decade-plus horizons)      | **Rebuild**      | Substrate ecosystems may not survive; closed-world rebuild is the only durable guarantee             |
| Reviewer's verification deposit                | **Cite**         | The reviewer is citing their re-derivation; the author's Replay deposit already carries the runnable artifact |
| Negative-result publication                    | **Cite** or **Replay** | The Receipt itself is the contribution; tier choice depends on whether re-runnability matters    |

## See also

- [POSITIONING.md](POSITIONING.md) — why each of these concepts exists in
  the project's strategic framing.
- [ARCHITECTURE.md](ARCHITECTURE.md) — implementation machinery (action
  envelopes, CAS, ActionCache, bundle composition).
- [REE_SERVICE_ROADMAP.md](REE_SERVICE_ROADMAP.md) — product-level
  build-out plan.
