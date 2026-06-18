# Positioning repo2ree against Code Ocean

## 1. Purpose of this document

Code Ocean is the most visible commercial reproducibility product. This document
fixes our answer: what it does well, where repo2ree differs structurally, and how
capsule import makes Code Ocean an input rather than only a competitor.

The one-line answer:

> Code Ocean answers "where can my code run?" — a destination platform.
> repo2ree answers "what is the evidence that this claim reproduces, and
> will that evidence survive?" — a verification and archival layer over
> wherever the code already runs.

## 2. What Code Ocean is

Code Ocean is a hosted cloud platform built around the **Compute Capsule**:
a self-contained unit of code, environment specification, data, and results.

| Capsule element | Contents |
|---|---|
| `metadata.yml` | Title, authors, capsule metadata |
| `environment/` | Base image choice plus conda/pip/apt configuration, or a Dockerfile |
| `code/` | The author's scripts, with a designated entry point |
| `data/` | Input data, subject to platform size limits |
| `results/` | Outputs of the last successful run |
| `REPRODUCING.md` | Generated instructions for offline re-execution |

Its headline feature is the **Reproducible Run** badge: the platform
re-executes the capsule's entry point in its hosted environment and confirms
it completed. Nature-family journals use this in peer review. Capsules can be
assigned DOIs that resolve to codeocean.com.

Commercially, Code Ocean has shifted its focus since roughly 2022 toward
enterprise pharma and biotech R&D platforms. Academic artifact evaluation is
its legacy use case, maintained largely through the publisher integration
rather than driven by its roadmap.

## 3. Where Code Ocean is genuinely strong

These set the UX bar.

| Strength | Implication for repo2ree |
|---|---|
| One-button hosted "press play" for reviewers | Verify in smoke mode must feel equally simple. A reviewer who just wants one button must get one. |
| Polished guided environment setup | Our overlay generation has to be at least as approachable as their environment editor. |
| Publisher integration with the Nature family | Venue pilots are how positioning becomes adoption; we need our NFDI artifact-evaluation pilots to play the same role. |
| A single coherent artifact (the capsule) | The REE must remain explainable in one sentence: Source + Overlay + Runtime + Artifacts. |

## 4. The weak differentiator, sharpened

"They are commercial, we are open and free" is true but insufficient: Whole
Tale and Binder are already open and free and did not displace Code Ocean in
artifact evaluation.

The sharp argument is **platform-mortality tolerance**. A capsule DOI resolves
to codeocean.com; if the platform pivots, paywalls, or shuts down, the artifact
degrades. repo2ree makes the archived artifact independent of repo2ree: source
resolves through Software Heritage, bundles live in Zenodo-style repositories,
identifiers come from DataCite/PID4NFDI, and Cite/Replay/Rebuild tiers state
what survives.

Openness matters here as the mechanism, not the message: anyone can re-host
the verification machinery, so the evidence chain has no single point of
commercial failure.

## 5. Structural gaps Code Ocean cannot close

These are architectural gaps: each follows from the capsule being a hosted
runnable, not a verifiable claim.

### 5.1 Verification semantics

The Reproducible Run badge answers exactly one question: did it execute.
There are no output contracts, no numeric tolerances, no statistical reruns,
no claim-level predicates, and no reviewer receipt that points back at the
author's run.

repo2ree's Verify asks whether the run executed, artifacts matched their
contracts, and the paper-level claim still holds. Receipts carry predecessor
pointers. The unit is not "capsule that runs"; it is "claim with declared
equivalence semantics."

### 5.2 Disclosure without migration

Code Ocean can say nothing about a repository until the author has ported it
into a capsule. The Repro Label observes a repository as-is: a venue or
reviewer can label every submission with zero author cooperation. Their entry
price is full migration; ours is a repository pointer.

### 5.3 Data sovereignty and compute locality

Code Ocean is a hosted US cloud platform. Our first audience is NFDI:
institutions with GDPR constraints, restricted medical and licensed corpora,
and existing HPC. Two consequences:

| Gap | repo2ree answer |
|---|---|
| Data that legally cannot leave the institution | Self-hosted execution plane; the workbench runs where the data lives. |
| HPC clusters where Docker is banned | Planned Apptainer/Singularity substrate; Code Ocean does not serve HPC at all. |

### 5.4 Restricted and large data as a modeled case

Capsules assume data fits inside platform limits. repo2ree models common CS/ML
cases directly: large public data by pointer and checksum, managed data via
DataLad identifiers, and restricted data with expected digests plus an explicit
"environment reproduced, restricted data unavailable" outcome.

### 5.5 Provenance depth

Capsules carry no action digests, content-addressed input roots, execution
attestation, or verification lineage. repo2ree's typed actions, expected-output
checks, and target receipt layer connect to the Reproducible Builds / SLSA /
in-toto world.

### 5.6 Substrate respect

A researcher with a careful Nix flake or Snakemake pipeline should not flatten
it into a capsule. repo2ree uses and records existing substrates: more precise
substrates yield better Labels; tracked runs yield richer Receipts.

### 5.7 A vacated niche

Code Ocean's commercial gravity is enterprise life-science R&D. Academic
artifact evaluation is ground it is leaving, not defending. Our venue-linked
adoption plan (NFDI artifact-evaluation pilots) walks into that vacancy.
Re-verify their current product focus before using this claim externally.

## 6. Subsume, don't compete: the capsule importer

The capsule export format is stable and documented, and it maps almost 1:1
onto the REE model:

| Capsule element | REE element |
|---|---|
| `code/` | Source |
| `environment/` (Dockerfile or base image + package lists) | Overlay: generated build recipe |
| `metadata.yml` | Declaration |
| `data/` | Data inputs, by digest or pointer per the data model |
| `results/` | Baseline outputs, wrapped in comparison contracts |
| Entry point + Reproducible Run | A degraded Run Receipt (no traces, no action digest) |

Importing a capsule is an upgrade path, not a port: the author gains a Label,
real Receipts on re-execution, comparison contracts over existing results, and
an archive bundle that outlives any platform.

The importer pattern generalizes:

| Prior format | Maps to |
|---|---|
| Code Ocean capsule | Source + Overlay + baseline outputs |
| Whole Tale tale | Source + Overlay + data pointers |
| Binder / repo2docker config | Overlay build recipe |
| RO-Crate | Declaration + metadata + data pointers |

"repo2ree ingests prior reproducibility formats" is stronger than one converter:
a capsule becomes another substrate, alongside a Dockerfile, flake, or Binder
config.

## 7. Positioning summary

| Axis | Code Ocean | repo2ree |
|---|---|---|
| Unit | Compute Capsule (hosted runnable) | REE (verifiable, citable claim object) |
| Verification | Did it execute | Executed / artifacts matched / claim holds |
| Entry price | Migrate into the platform | Point at the existing repository |
| Disclosure | None before migration | Repro Label on the repo as-is |
| Data | Inside the capsule, size-capped | Modeled: included, pointed-to, or restricted |
| Compute | Their US cloud | Wherever the workbench runs, incl. self-hosted and HPC |
| Provenance | Capsule + timestamp | Typed commands now; action digests, CAS, receipts, and verification lineage as the target |
| Archive | DOI resolving to their platform | Software Heritage + Zenodo + DataCite; usable without repo2ree |
| Substrates | Their base images, Docker only | Uses and records Docker, Nix, conda, uv, Apptainer, trackers |
| Business exposure | Single commercial platform | Open layer over durable public infrastructure |

The sentence to use when asked directly:

> Code Ocean hosts your code so a reviewer can press play. repo2ree turns
> the runs behind your paper's claims into citable, independently verifiable
> evidence that survives any platform — including ours. And if you already
> have a Code Ocean capsule, we import it.
