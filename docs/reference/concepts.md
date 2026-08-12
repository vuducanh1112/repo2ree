# repo2ree — Concept Reference

> **Status: current concepts plus explicitly marked target vocabulary.** The
> **what** of repo2ree — definitions of the nouns, verbs, tiers, and states used
> across the project. For *why* these concepts exist see
> [research/POSITIONING.md](../research/POSITIONING.md); for *how* they are implemented see
> [architecture.md](architecture.md).

## The integration this defines

repo2ree binds three substrate layers — **environments** (Docker, Nix,
VMs), **experiments** (MLflow, W&B, plain logs), and **archives**
(Software Heritage, Zenodo, PID4NFDI) — into one reproducibility
workflow. The concepts below are the *names* of that integration: the
**nouns** that travel between layers (Source, Overlay, REE, Repro
Label, Run Receipt), the **workflows** that bind them (Verify, Archive), the
**Seal** operation that freezes them, and the **tiers** and **states** that
govern how they're composed.

Each primitive and workflow declares which layers it integrates.

## Vocabulary boundary

The product uses four related terms for four different evidentiary claims:

| Term | Evidence and claim |
|---|---|
| **Evaluate** | Observes the source repository before build. It produces declaration findings and independent dependency, environment, and machine axes. |
| **REE assessment** | Reports whether each definition, receipt, and bundled payload is present, current, stale, omitted, or not applicable. It is not a reproduction verdict. |
| **Validation** | One run and its optional verify script passed the author-declared check. An author validation creates evidence and a comparison baseline. |
| **Reproduction** | A later execution is compared with prior author evidence. A durable reproduction claim therefore needs baseline or predecessor identity, not only a passing verify script. |

These boundaries are normative. In particular, a successful first author run
must be called **validated**, not **reproduced**.

## Core nouns

### Source

The pristine repository at a fixed commit. Owned by the original author;
**never modified by repo2ree**. Lives as a source snapshot under
`/ree/upstream/`; `/ree/workspace/` is the materialized build/run view. A
deposited Source should resolve to a Software Heritage identifier (SWHID) when
available.

A Source with a stable identifier (SWHID) is *Archive-ready*; a Source
that exists only locally is *Draft* (see [lifecycle states](#ree-lifecycle-states)).

### Overlay

repo2ree's contribution to the REE — sits *beside* the Source without
modifying it. Holds the declaration, generated build scripts, generated
Dockerfiles or flakes, and any other material that turns a bare
repository into a fully-specified environment. Lives in `/ree/overlay/`
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

The repo's standing reproducibility disclosure, produced by Evaluate and shown
on independent axes — today: *dependency declaration*, *environment capture*,
and *machine declaration*; with archival also: *source-identifier stability*
and *closure-capturability*.

**Observational**: describes the repo as-is, without modifying it. A
nutrition label, not a grade. The Label reads whatever environment
substrate the repo brought (Dockerfile, flake.nix, conda env, plain
pip) and exposes it in lifecycle-layer vocabulary. **Primitive 1.**

### REE assessment

The assembled REE's derived view of source, evaluation, hardware, runtime,
SBOM, activation, and experiment evidence. For each step it distinguishes the
receipt's freshness from the payload's presence in the bundle. Unlike Verify,
it does not compare a later run with prior evidence.

### Run Receipt

*Integrates: Experiment substrate → Archive substrate.*

A successful author operation already produces an immutable typed receipt with
operation identity, timing, relevant input and artifact digests, and result
evidence. Review operations produce their own typed receipts plus explicit
comparison records. The target independently citable wrapper adds:

```
ree_digest      which sealed REE executed the run
action_digest   which command + inputs were issued
parameters      typed run-specific inputs (seeds, hyperparams, …)
outputs         produced files, content-addressed
traces          stdout, stderr, logs, metrics
result          the structured value the run advertised
signatures      optional executor attestation
predecessor     optional pointer to the run this re-derives
```

Current receipts are immutable and carried by the REE or review attempt. The
target citable receipt can also **wrap whatever the experiment substrate
produced**: an MLflow run becomes a Receipt with MLflow metadata
preserved; a Weights & Biases run becomes a Receipt pointing at the
W&B record; a plain Python script becomes a Receipt assembled from
stdout and outputs. The substrate stays the substrate; the Receipt is
the citable wrapper that pushes the run toward the archive.

Author and reviewer receipts are currently distinct types because review
receipts bind an evidence basis and sit beside comparison records. In the target
portable wrapper, a `predecessor` pointer binds a reviewer's verification to
the author's original claim. That verification receipt can be signed by the
reviewer, executor, or venue as a claim about what was re-derived and under
which comparison policy. **Primitive 2.**

An author receipt may record that its declared validation passed. It becomes
reproduction evidence only when a later receipt or comparison names it as the
baseline or predecessor.

### Seal identity and target manifest

The implemented Seal operation stores a `ReeSeal` in `ree/ree.json`. Its
`ree_digest` is the SHA-256 digest of the canonical REE subject, including the
definition, receipts, bundle inventory, and review evidence. The deterministic
ZIP carries that same sealed document; there is no separate Seal Manifest file
in the current bundle.

The target archival format generalizes that identity into a canonical Seal
Manifest over the source identity, overlay, runtime artifact, dependency closure
when present, Label, and Receipts:

```text
ree_digest = sha256(canonical_seal_manifest)
```

In both forms, the digest names the REE. It does not by itself mean the REE is trusted,
reproducible, signed, or deposited. Signatures are separate attestations over
the digest. See [research/sealing.md](../research/sealing.md).

## Workflows

### Verify

*Integrates: Archive substrate → Environment substrate → Experiment substrate.*

The implemented reviewer lifecycle is:

1. Load a sealed REE into a workbench and start an isolated review attempt.
2. Reacquire source, rebuild the runtime, test activation, and rerun experiments.
3. Record reviewer receipts and compare source identity, runtime digest or SBOM
   closure, and experiment criteria/output evidence with the author baseline.
4. Surface per-step evidence basis and verdicts without changing author evidence.

The target extension packages those receipts and comparisons with predecessor
links and signatures so the review itself can be cited or deposited.

### Seal

*Integrates: Lifecycle artifacts → Trust vocabulary.*

The freeze point before Archive. Today Seal records `ree_digest` over the
canonical REE subject and writes the immutable bundle. The target Seal Manifest
makes the component digest inventory a separately named archival object. After
sealing, authoring mutations are rejected; changing the subject requires a new
draft and seal.

Signing is append-only: authors, executors, reviewers, venues, institutions, and
archive adapters can each sign typed claims over the same `ree_digest`.
Signatures are not included in the digest they sign.

### Archive

*Integrates: Lifecycle artifacts → Archive substrates.*

The target author deposit/export workflow composes the primitives with
institutional archival infrastructure:

1. Compose the bundle: declaration + overlay + source-pointer + Receipts
   + Label + Seal Manifest + (artifacts by chosen [fidelity tier](#fidelity-tiers)).
2. Export or deposit the bundle through Zenodo, Dataverse, or an institutional
   repository adapter.
3. Bind source to Software Heritage when possible and record SWHIDs in metadata.
4. Record the `ree_digest`, signatures, DOI/PID, and archive-binding metadata.
5. Optionally bind a PID via PID4NFDI for NFDI-internal references.
6. The deposited bundle becomes the canonical citable form of the REE.

repo2ree never archives anything itself; it composes archive-ready
bundles for services that do.

## Fidelity tiers

These are target archive tiers, each a strict superset of the previous. The
current seal UI/API independently selects source, runtime, and result payloads;
it does not yet record one of these tier names.

| Tier        | Contents                                                  | Re-runnable?           | Re-derivable?              | Storage |
|-------------|-----------------------------------------------------------|------------------------|----------------------------|---------|
| **Cite**    | declaration + overlay + source-pointer + Receipts + Label | iff upstreams alive    | iff upstreams alive        | KB–MB   |
| **Replay**  | Cite + the built runtime image                            | always (OCI + amd64)   | no                         | MB–GB   |
| **Rebuild** | Replay + inputs closure (vendored deps)                   | always                 | yes, against dead internet | GB      |

**Recommended default: Replay.** It preserves long-term runnability without the
cost of full dependency-closure capture.

## REE lifecycle states

The implementation exposes `draft` and `sealed` as REE status and separately
derives whether a seal has archive attestations. The following four-state model
is target archival-readiness vocabulary:

| State              | What's true                                                   | Eligible for canonical Archive?                                                |
|--------------------|---------------------------------------------------------------|--------------------------------------------------------------------------------|
| **Draft**          | Source has no stable identifier; actively being edited; pre-deposit iteration | No — bundles carry source bytes inline only as a temporary snapshot |
| **Archive-ready**  | Source resolves to an SWHID; declaration and overlay are stable | Yes                                                                          |
| **Sealed**         | Seal Manifest and `ree_digest` exist; edits create a new seal | Yes                                                                          |
| **Deposited**      | Bundle deposited or exported; archive identifiers recorded  | Already archived; future Archives create new versions                          |

Promotion Draft → Archive-ready happens when the source acquires a stable
identifier, usually through a forge already crawled by Software Heritage or an
explicit SWH save/deposit request.

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

- [POSITIONING.md](../research/POSITIONING.md) — why each of these concepts exists in
  the project's strategic framing.
- [architecture.md](architecture.md) — implementation machinery and target
  hardening (action envelopes, CAS, ActionCache, bundle composition).
- [sealing.md](../research/sealing.md) — Seal Manifest, signatures, and long-term validation.
- [REE_SERVICE_ROADMAP.md](../research/REE_SERVICE_ROADMAP.md) — product-level
  build-out plan.
