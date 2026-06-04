# repo2ree — Positioning

> **Status: positioning statement (2026-05).** The **why** of repo2ree —
> strategic framing, audience, and relationship to neighbouring tools.
> For *what* each named concept means see [CONCEPTS.md](CONCEPTS.md);
> for *how* it's implemented see [ARCHITECTURE.md](ARCHITECTURE.md).

## In one sentence

repo2ree is the **integration layer for reproducible CS research**: it
binds the three layers researchers already use — environments (Docker /
Nix / VMs), experiments (parameterized runs with traces), and archive
(Zenodo / Software Heritage) — into one continuous loop. **Repro Labels**
disclose what you've got; **Run Receipts** record what you ran; **Verify**
lets others re-derive your claim; **Archive** deposits the bundle on
Zenodo with a DOI and source on SWH.

## Context

Developed within **NFDIxCS** — the German National Research Data
Infrastructure consortium for computer science. The mandate is *durable,
federated, FAIR-aligned infrastructure that composes with existing
research-data tooling rather than replacing it.* That mandate is the
reason the project is shaped as an integration layer rather than a
stand-alone product.

The audience starts inside the NFDI ecosystem (partner institutions,
Zenodo / institutional repository deposit, base services like PID4NFDI
and IAM4NFDI) and grows outward through bottom-up author and reviewer
adoption, with eventual integration into Artifact Evaluation tracks at
CS venues as upside rather than table stakes.

## The gap

The research-code world has two structural failures that no widely-adopted
tool addresses:

- **Reproducibility is unobservable.** A repo either builds for you or it
  doesn't. There is no *measurement* of how reproducible it is, what
  makes it fragile, or what would improve it — no signal for reviewers,
  future maintainers, or the author's own future self.
- **A "run" of code is not a thing.** Papers report numbers; repos
  sometimes reproduce builds; *the act of running this code with these
  parameters in this environment and getting these outputs* is not a
  structured, durable, citable object anywhere in the current toolchain.

Both failures are **integration failures**: the build system can describe
the environment but not score it; the experiment tracker can record runs
but not bind them to the environment; the archive can preserve files but
not compose them into a re-runnable bundle. No layer alone closes either
gap.

## Three layers, one integration

Reproducible CS research needs three layers, each with mature tools:

| Layer           | What it provides                                | Mature substrates                                                                       |
|-----------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| **Environment** | Build and run the code in a specified state     | Docker, Nix, Bazel, conda, uv, Apptainer, Kata VMs                                      |
| **Experiment**  | Run computations and capture what they produced | Snakemake, Nextflow, CWL, REANA *(workflow shape)*; MLflow, W&B, Neptune, Aim *(tracking shape)*; plain scripts |
| **Archive**     | Preserve and identify the artifact long-term    | Software Heritage, Zenodo, DataCite, PID4NFDI                                           |

Nothing ties them together. Researchers stitch the stack manually — and
most don't bother.

**repo2ree is the integration layer**: the connective tissue that binds
these three layers into one continuous reproducibility loop. The
substrates stay what they are; repo2ree adds the vocabulary, the
bindings, and the workflows that turn three separate tools into one
citable artifact.

The four named surfaces below are the points where the layers meet.

## Design principles

Two principles run through every surface and shape every architectural
choice.

### Not a work environment

repo2ree is **not** where you write code. It is not a JupyterHub, not a
hosted IDE, not a notebook server, not a development platform you log
into to do research. The frontend's overlay editor is for managing what
repo2ree adds *beside* your source — build scripts, declarations,
generated recipes — not for primary code authoring.

Tools that bake reproducibility into the act of writing code (Renku,
Code Ocean's editor, JupyterHub deployments, devcontainer setups) are
**upstream** of repo2ree, not in competition with it. A project
authored in a reproducibility-aware environment arrives at repo2ree
with code and data already in a working state and (often) rich
provenance already captured; repo2ree's job starts where authoring
ends.

The negative claim is itself a positive design choice: it keeps the
project focused on the lifecycle moments that matter (Label → Verify →
Archive), makes "works on any repo, anywhere" achievable, and avoids
lock-in. Users keep their preferred editor / hub / hosted env;
repo2ree certifies the artifact that emerges from it.

### One-click: bring a script, get a Receipt

Every interaction with repo2ree must reduce to a single declarative
input. No new DSL to learn; no code instrumentation required; no
platform to log into; no per-tool integration to write.

| Surface                | What you provide                                            | What you get back                                  |
|------------------------|-------------------------------------------------------------|----------------------------------------------------|
| **Repro Label**        | A pointer to the repo                                       | A scored Label and a list of concrete threats      |
| **Build the runtime**  | A `build_runtime_script` (the script you'd run locally)     | A built runtime image and a build Receipt          |
| **Run a workflow**     | A command (the command you'd type locally)                  | A Run Receipt with parameters, traces, outputs     |
| **Verify**             | One click                                                   | A new Receipt diffed against the original          |
| **Archive**            | One click + tier choice                                     | A Zenodo DOI, an SWHID, a deposited bundle         |

The principle is **bring a script, get a Receipt** — and equivalently
for the other surfaces. The user is never asked to learn repo2ree's
internal model; they bring what they already have, and repo2ree wraps
it.

This is the line that distinguishes repo2ree from both the platform
tools (Renku, Code Ocean) that ask you to *adopt their environment* and
the build-discipline tools (Nix, Bazel) that ask you to *learn their
authoring language*.

## Four nameable surfaces: two primitives, two workflows

Two **primitives** — the artifacts — and two **workflows** — the
flagship moments. Primitives are the things you cite and deposit;
workflows are how the integration becomes visible to a reviewer or a
funder.

| Surface         | Kind      | What it is                                                                                                          |
|-----------------|-----------|---------------------------------------------------------------------------------------------------------------------|
| **Repro Label** | Primitive | The repo's standing reproducibility disclosure — a nutrition label.                                                 |
| **Run Receipt** | Primitive | A single execution's structured record — environment, inputs, outputs, result.                                      |
| **Verify**      | Workflow  | One click: re-derive a Receipt on your own compute, get a comparable, citable diff.                                 |
| **Archive**     | Workflow  | One click: deposit the Label, Receipts, and the REE bundle on Zenodo with a DOI; source flows to Software Heritage. |

---

### Repro Label

*Integrates: Environment substrate → Lifecycle vocabulary.*

> *Every repo carries a Label that says how reproducible it actually is —
> independent of who built it or what they used to build it.*

Like a nutrition label, the Repro Label **describes** the repo without
changing it. Independent axes — dependency declaration, environment
capture — score the repo as-is. Threats are concrete and actionable:
floating image tags, missing lockfiles, unpinned `pip install`s,
network-fetched-without-checksum installers, missing base-image digests.

The Label is *observational*: it works on any repo without requiring
the author to have used any particular tool. A Nix-built repo earns a
high Label because Nix is rigorous; a `FROM python:3.11` Dockerfile
earns a low one because the tag floats. The Label says so out loud.

**Improvement path.** A low Label can be raised two ways:

1. **The user fixes their substrate.** Pin the digest, commit the
   lockfile, switch to `--require-hashes`. repo2ree says what to fix;
   re-scores.
2. **repo2ree generates a recipe** — a Dockerfile or `flake.nix` from
   declared intent, with pinning baked in by construction. The generated
   file gets committed to the repo; the Label improves; the user can
   continue without repo2ree.

Generation is a *remediation tactic* inside the Label, not the headline.
The diagnostic is the product.

The Label is realised today in the
[Evaluate page](frontend/src/shell/ui/app-shell/pages/evaluate/EvaluatePage.tsx).

---

### Run Receipt

*Integrates: Experiment substrate → Archive substrate.*

> *Every execution produces a Receipt. Cite the Receipt the way you cite
> a DOI — and anyone can fetch the exact run, environment included.*

Today: papers report Table 3 row 4. To reproduce, you `git clone`, hope,
and read between the lines for hyperparameters. The *run* that produced
the number is not a structured thing anyone publishes.

A Run Receipt is the structured thing:

```
ree_digest      which environment exactly executed the run
action_digest   which command + inputs (per the action envelope)
parameters      typed run-specific inputs (seeds, hyperparams, data version)
outputs         produced files, content-addressed
traces          stdout, stderr, structured logs, metrics
result          the structured value the run advertised
signatures      optional executor attestation
predecessor     optional pointer to the run this re-derives
```

The Receipt **wraps whatever the experiment substrate produced**. An
MLflow-instrumented run becomes a Receipt with MLflow metadata
preserved; a Weights & Biases run becomes a Receipt that points at the
W&B record; a plain Python script becomes a Receipt assembled from
stdout and outputs. The substrate stays the substrate; the Receipt is
the citable wrapper that binds the run to its environment and pushes it
toward the archive.

Each Receipt is content-addressed and immutable. What this changes:

- **Citable runs.** A paper cites `Receipt 10.5281/zenodo.XYZ` instead
  of "Table 3, third row." A reader fetches that exact run —
  environment and all — and inspects it.
- **Comparable runs.** A reviewer re-runs the headline on their compute
  and publishes a new Receipt with `predecessor` pointing at the
  author's. Same Action, different Platform, different result = a
  structurally visible discrepancy, not a forum argument.
- **Negative results survive.** A run with a worse number is still a
  complete artifact.
- **Benchmark integrity.** A Papers-with-Code successor can index
  *verified* Receipts instead of self-reported numbers.

The machinery — typed action envelope, content-addressed inputs and
outputs, signable result — is in
[ARCHITECTURE.md](ARCHITECTURE.md#the-wire-form-a-typed-action-envelope).

---

### Verify

*Integrates: Archive substrate → Environment substrate → Experiment substrate.*

> *Click Verify. The repo's Receipts re-derive on your compute. The diff
> is the review.*

Verify is the *composition* of the two primitives that gives reviewers
(and authors, and readers) the headline experience:

```
1. Click Verify on a paper's repo
2. The Repro Label is loaded and re-scored against the local environment
3. Each published Run Receipt is re-executed against the same REE
4. Each re-execution produces a new Receipt (predecessor → author's)
5. Differences are diffed and the verification artifact is itself a
   Receipt set, depositable as the reviewer's own contribution
```

Author and reviewer use the **same machinery, symmetrically**. There is
no special "review mode"; the reviewer just produces their own Receipts
and publishes the predecessor links.

**Why this matters for the project.** Verify is the *demoable artifact*
— the moment that makes the abstract "we provide reproducibility
infrastructure" immediately visible to a funder, a partner institution,
or a venue chair.

---

### Archive

*Integrates: Lifecycle artifacts → Archive substrates.*

> *Click Archive. The REE composes into a bundle, deposits to Zenodo
> with a DOI, and source-code components flow to Software Heritage with
> SWHIDs. The bundle is the citable artifact; the service is just how
> you got it there.*

Archive composes the primitives with **institutional archival
infrastructure**. repo2ree never runs its own permanent archive; it
composes with Software Heritage (source code), Zenodo (bundles and
DOIs), and NFDI base services (PIDs, identity).

The bundle is a **composition manifest** rather than a self-contained
tarball: source by SWHID *pointer* (because SWH owns source archival),
overlay and Receipts inline (because they are repo2ree's contribution),
artifacts by **fidelity tier**:

| Tier        | Contents                                                  | Best for                                              |
|-------------|-----------------------------------------------------------|-------------------------------------------------------|
| **Cite**    | declaration + overlay + source-pointer + Receipts + Label | Drafts, citation-only artifacts                       |
| **Replay**  | Cite + the built runtime image                            | Paper supplementary material — *the default*          |
| **Rebuild** | Replay + inputs closure (vendored deps)                   | Audit-grade, dead-internet-tolerant archival          |

Each tier is a strict superset of the previous. The Label discloses
which tier was deposited — an observable reproducibility property
visible to reviewers at a glance.

**Why composition, not duplication.** SWH and Zenodo already exist, are
funded, and are durable. The NFDI mandate is to compose with existing
research-data infrastructure, not duplicate it. The Zenodo–SWH
integration means a single deposit gives you a DOI, automatic
source-code archival in SWH, and SWHIDs bound to the deposited bundle —
without repo2ree maintaining any of it.

**Why this matters for the project.** Archive is what makes the
sustainability claim structural rather than aspirational: bundles
survive the service because they live on Zenodo + SWH, not in
repo2ree's storage.

---

## Deference at every layer

Being the *integration* layer means deferring to substrates at all
three layers:

- **Environment.** Researchers keep using Docker, Nix, Bazel, conda, or
  none of the above. The
  [BuildRuntime page](frontend/src/shell/ui/app-shell/pages/build-runtime/BuildRuntimePage.tsx)
  is script-centric: the user picks, writes, or generates a build
  script that invokes whatever build system the repo brought.
- **Experiment.** Researchers keep using MLflow, Weights & Biases,
  Neptune, plain prints, or no tracking. The Run Receipt wraps whatever
  the run produced — it doesn't prescribe how the run logs metrics or
  which tracking system is in use.
- **Archive.** Long-term preservation lives at Software Heritage
  (source), Zenodo (bundles), and DataCite / PID4NFDI (identifiers).
  repo2ree composes archive-ready bundles; it doesn't store anything
  permanently.

A Nix-built repo earns a high Repro Label — *exactly as intended* — and
its Run Receipts inherit Nix's reproducibility floor. An
MLflow-instrumented run becomes a Receipt with the tracker's metadata
preserved. A repo with no tracking yields a Receipt assembled from
stdout, outputs, and exit code.

The integration story is always `<your substrates> + repo2ree`, never
`repo2ree vs. anything`. The only thing each substrate has to provide
is its native job: build the environment, capture the run, preserve the
artifact. Everything else — turning those into a Label, a Receipt, a
Verify, an Archive — is the integration layer's job.

## Comparator landscape

repo2ree's relationship to neighbouring tools falls into three buckets:
**substrates we integrate**, **lifecycle peers** we differentiate from,
and **cultural / analogue precedents** that frame the work.

### Substrates we integrate

| Substrate                                              | Layer       | Relationship                                                                                                                |
|--------------------------------------------------------|-------------|-----------------------------------------------------------------------------------------------------------------------------|
| Nix / Bazel / Docker / conda / uv / apt                | Environment | repo2ree runs whatever the repo brought; the Label grades its reproducibility floor.                                        |
| Snakemake / Nextflow / CWL / REANA (workflows) · MLflow / W&B / Neptune (tracking) · plain scripts | Experiment | The Run Receipt wraps whatever the substrate ran — workflow DAG, ML run, or single command — and preserves its metadata. |
| Software Heritage / Zenodo / DataCite / PID4NFDI       | Archive     | The Archive workflow deposits via these services and consumes their PIDs. The SWH–Zenodo integration is leveraged directly. |

### Upstream authoring environments

Tools that bake reproducibility into the act of writing code. These
produce well-shaped inputs *for* repo2ree, not competing outputs.

| Environment                                           | What it does                                                                          | Relationship                                                                                                            |
|-------------------------------------------------------|---------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| **Renku**                                             | Hosted JupyterLab + GitLab; continuous provenance, dataset versioning, workflow recording | A Renku-authored project arrives at repo2ree with code and data already in a working state; the Label rewards the provenance Renku captured |
| **Code Ocean (editor mode)**                          | Hosted IDE for authoring compute capsules                                             | repo2ree can certify and archive the result without users adopting Code Ocean's publishing pipeline                     |
| **JupyterHub / Open OnDemand**                        | Institutional hosted notebook environments                                            | Provide the working environment with code and data; repo2ree wraps the artifact that emerges                            |
| **devcontainer / GitHub Codespaces / Gitpod**         | Containerised dev environments tied to the repo                                       | The environment-as-code happens *before* repo2ree; the Repro Label rewards a well-specified devcontainer                |

These tools answer "how do I work reproducibly?" repo2ree answers "now
that I've worked, how do I prove and archive it?" The two questions
stack.

### Lifecycle peers

| Tool                          | Overlap                                | Where repo2ree differs                                                                                          |
|-------------------------------|----------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| **repo2docker / Binder**      | Auto-build from repo                   | Ephemeral notebook sessions; no Label, no Receipt, no Verify, no Archive; no substrate-deference.              |
| **Code Ocean (publish mode) / Whole Tale** | Hosted reproducibility platforms | Closed platforms; no grading axis; runs not citable outside the platform; no substrate plurality.               |
| **ReproZip / Sciunit**        | Capture and replay execution           | Post-hoc syscall trace; no declarative authoring; no integration with experiment-tracking or archive layers.    |

### Cultural and analogue precedents

| Reference                          | Relationship                                                                                                                          |
|------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| **Artifact Evaluation tracks**     | Same goal, automated. The AE practice repo2ree generalises beyond AE-track venues to every CS paper.                                  |
| **Papers with Code**               | Indexes *claimed* results without verification. repo2ree makes the run a structured, verifiable artifact a successor index can use.   |
| **rebuilderd / SLSA / in-toto**    | Same family (signed verification of builds); different unit (research repo + run, not a Debian package or a CI build).                |

## Related work

> *Draft for paper-shaped use. This section overlaps the comparator
> landscape above in coverage but presents the same material as prose
> grouped by approach, suitable as the starting point for a Related Work
> section in a paper.*

The reproducibility-of-computation problem has been approached from many
angles. None of the existing projects provide the specific integration
that repo2ree contributes — graded reproducibility as a public property
of the repository, runs as content-addressed citable artifacts with
predecessor lineage, and one-click cross-substrate re-derivation — but
several occupy adjacent space that warrants honest comparison. This
section groups related work by approach and articulates where repo2ree
differs.

### Authoring-time reproducibility environments

A line of work attempts to make the act of writing research code itself
reproducibility-aware. [Renku](https://renkulab.io/) (Swiss Data
Science Center) hosts a JupyterLab + GitLab environment that captures
provenance continuously: every file save, kernel restart, dataset
access, and workflow execution is recorded. [Code Ocean](https://codeocean.com/)
provides a similar hosted editor for authoring "compute capsules."
[devcontainer](https://containers.dev/), [GitHub Codespaces](https://github.com/features/codespaces),
and [Gitpod](https://www.gitpod.io/) specify the working environment as
code tied to the repo. [JupyterHub](https://jupyter.org/hub) and
[Open OnDemand](https://openondemand.org/) are institutional hosted
notebook deployments. [ReproZip](https://www.reprozip.org/) takes the
opposite tack: rather than recording at authoring time, it traces a
running execution post-hoc via syscall interception and packages the
inputs into a re-runnable bundle.

These tools answer "how do I work reproducibly?" — a different question
from the one repo2ree addresses. Renku and similar require adoption of
the hosted environment, which is incompatible with both the
*Not a Work Environment* design principle and the use case of grading
third-party or legacy repositories. repo2ree treats these systems as
**upstream**: a Renku-authored project arrives at repo2ree with code,
data, and provenance in a working state, and the Repro Label rewards
the captured discipline.

### Hosted reproducibility platforms

A second line of work hosts the entire research artifact on platform
infrastructure. [Whole Tale](https://wholetale.org/) (NSF) provides
"scholarly middleware" — containerized research environments linked to
dataset PIDs and archive DOIs. Code Ocean also occupies this space in
its publishing mode, producing runnable capsules with DOIs.
[Binder / MyBinder](https://mybinder.org/) auto-builds ephemeral
notebook environments from a repository for reader-facing execution.

These platforms produce credible reproducible artifacts but require
adoption of the platform itself. They lack substrate plurality (a user
cannot bring an arbitrary Nix flake or conda environment), lack a
graded reproducibility axis (artifacts are binary "works"/"doesn't"),
and tie citability to the platform's own infrastructure. repo2ree
differs in three ways: it works on any repository regardless of
authoring environment, it grades reproducibility as a measured property
of the repository rather than a platform feature, and it deposits
citable artifacts on existing archival infrastructure
(Zenodo / Software Heritage) rather than on its own service.

### Build, workflow, and tracking substrates

A third body of work addresses individual layers that repo2ree treats
as integration substrates rather than competitors. At the **environment
layer**: [Nix](https://nixos.org/) and [Guix](https://guix.gnu.org/)
provide hermetic build semantics with cryptographic input-addressing
of build outputs; [Bazel](https://bazel.build/) provides remote
execution and content-addressed caching. At the **workflow layer**:
[Snakemake](https://snakemake.readthedocs.io/) and
[Nextflow](https://nextflow.io/) provide DSLs that specify and execute
computational pipelines; the [Common Workflow Language](https://www.commonwl.org/)
is a portable workflow specification consumed by multiple engines;
[REANA](https://reanahub.io/) (CERN) executes CWL / Snakemake / Yadage
workflows on Kubernetes-backed clusters, originally developed for HEP
analysis preservation; [WorkflowHub](https://workflowhub.eu/) indexes
workflow definitions and assigns identifiers to them. At the
**tracking layer**: [MLflow](https://mlflow.org/),
[Weights & Biases](https://wandb.ai/), [Neptune](https://neptune.ai/),
and [Aim](https://aimstack.io/) record machine-learning runs with
parameters, metrics, and artifacts.

Each of these tools produces strong reproducibility properties within
its layer, but none binds the three layers together. A Snakemake
pipeline does not produce a reproducibility-graded Repro Label. An
MLflow run is not a Zenodo-citable artifact bound to a
Software-Heritage-archived environment. A Nix flake does not produce a
reviewer-facing one-click Verify workflow. repo2ree's contribution is
precisely this binding: it consumes whichever of these substrates the
repository brought, grades them on consistent axes, wraps their runs
into uniformly-shaped Receipts, and pushes the composition into
long-term archival infrastructure.

### Verification and attestation systems

A fourth line of work, originating in software supply-chain security,
provides cryptographic verification of build outputs. The
[Reproducible Builds](https://reproducible-builds.org/) project and
[rebuilderd](https://github.com/kpcyrd/rebuilderd) coordinate
independent rebuilders that produce signed attestations of bit-equal
builds for Debian, Arch, and similar package ecosystems.
[SLSA](https://slsa.dev/) (Supply-chain Levels for Software Artifacts)
defines a tiered framework for build-provenance claims.
[in-toto](https://in-toto.io/) specifies a metadata format for
end-to-end software supply-chain attestations.

These systems share a family resemblance with the Run Receipt —
content-addressed inputs and outputs, signed attestations,
predecessor-style provenance chains — but operate at the **package**
unit (a Debian deb, a Python wheel, a CI build output), not at the
research-repository unit. They also focus on verification of
deterministic builds, where most CS research code is non-deterministic
by construction (GPU floating point, network non-determinism in
installs, time-dependent randomness). repo2ree adopts the structural
patterns (typed action envelopes, content-addressing, signed results)
but applies them at a different granularity (the research repository +
its run) and at a different default fidelity (input-identity
reproducibility, with bit-identity opt-in for the subset of substrates
that support it).

### Archive infrastructure and cultural precedents

A fifth line of work concerns long-term preservation and community
practice. [Software Heritage](https://www.softwareheritage.org/)
(Inria + UNESCO) archives source code at internet scale with intrinsic
content-addressed identifiers (SWHIDs). [Zenodo](https://zenodo.org/)
(CERN) provides DOI-bearing deposit for arbitrary research artifacts.
[DataCite](https://datacite.org/) and [PID4NFDI](https://www.pid4nfdi.de/)
issue handles for research-data resources.
[RO-Crate](https://www.researchobject.org/ro-crate/) is a W3C-community
packaging standard for research objects with JSON-LD metadata.
[DataLad](https://www.datalad.org/) versions data and computation as
git-annex datasets with optional DOI deposit.
[Papers with Code](https://paperswithcode.com/) indexes
(paper, repository, benchmark, claimed result) tuples for ML research.
[ACM Artifact Evaluation tracks](https://www.acm.org/publications/policies/artifact-review-and-badging-current)
describe the community process for reviewer-verified reproducibility.

repo2ree composes with this infrastructure rather than replacing any of
it. The Archive workflow deposits bundles on Zenodo (gaining DOIs and
inheriting the Zenodo–SWH integration), references SWHIDs for source
pointers, and produces RO-Crate-shaped bundles consumable by existing
tooling. Papers with Code becomes a target audience for a successor
index: self-reported results are replaced by verified Run Receipts. ACM
AE tracks become an adoption target: the cultural practice of reviewer
reproducibility becomes automatable via the Verify workflow.

### Summary

The space surveyed above is fragmented: each project addresses a slice
of the reproducibility problem at a distinct layer, with distinct
assumptions about who the user is, what they bring, and where the
artifacts live. repo2ree contributes the *integration layer* that binds
these otherwise separate concerns into a single workflow centred on
four named surfaces: graded reproducibility as a public property of the
repository (Repro Label), execution as a content-addressed citable
artifact with predecessor lineage (Run Receipt), one-click
cross-substrate re-derivation (Verify), and composition-not-duplication
archival deposit (Archive). None of these surfaces is, in isolation, a
wholesale novel concept — the structural patterns are borrowed from the
Bazel Remote Execution API, Nix, RO-Crate, the SLSA family, and the
reproducible-builds movement. The novelty is the binding: making the
four surfaces consistent across substrates, accessible without platform
adoption, and aligned with existing archival infrastructure.

## Audience

Bullseye: **CS researchers and reviewers** who care whether their results
survive a year, a reviewer, or a re-run — and the partner institutions
of NFDIxCS that underwrite that durability.

### Use cases

- **Paper supplementary material as Receipts, not READMEs.** Each
  numerical claim is a citable Receipt digest with a Zenodo PID.
- **Self-audit before submission.** Authors check their Label and
  remediate before reviewers see the repo.
- **Reviewer Verify.** A reviewer re-derives the headline and publishes
  their own Receipt set with predecessor links.
- **Artifact Evaluation tracks** at venues that want automated rather
  than volunteer-driven verification.
- **Lab onboarding.** New students start from a known-reproducible REE
  per project, not three weeks of "did you install CUDA 11.8 or 12.4?".
- **Long-tail maintenance.** Re-run a 2021 result in 2026; the delta is
  a structured artifact, not "it broke."
- **Benchmark hygiene.** A successor aggregator indexes Receipts by
  digest; results are verifiable, not self-reported.

### Not for

- Production deployment of a service.
- Polyglot monorepos with thousands of build targets.
- Greenfield projects where Nix-from-scratch is the right answer — use
  Nix, then bring repo2ree for the Label, Receipts, Verify, and Archive
  on top.

## Adoption pathway

The infrastructure works **without** venue cooperation. AE-track
integration is upside, not a prerequisite. Adoption proceeds bottom-up —
the Software Heritage / DataCite / ORCID pattern:

1. **NFDIxCS endorsement.** The format is the consortium's recommended
   way of documenting CS reproducibility. Partner institutions adopt by
   default.
2. **Author adoption.** Researchers deposit Receipts on Zenodo with
   PIDs, regardless of venue. Each Receipt is independently citable
   from day one.
3. **Reviewer adoption.** Reviewers click Verify on any submission
   whose author published Receipts, whether or not the venue has
   integrated anything.
4. **Aggregator adoption.** Successors to Papers with Code index
   Receipts directly; benchmarks become verifiable rather than
   self-reported.
5. **Venue adoption (eventually, optional).** AE tracks integrate when
   it's free for them to do so — when authors and reviewers are already
   using the format. NFDIxCS provides the institutional channel for
   negotiating that integration at scale rather than venue by venue.

Build the infrastructure, accumulate critical mass through institutional
endorsement and bottom-up use, let venue integration follow on its own
timeline.

## Sustainability

NFDI funding is bounded; the infrastructure must survive past it. Two
design commitments make this tractable:

- **Content-addressed artifacts.** Repro Labels and Run Receipts are
  immutable, content-addressed blobs. They survive on Zenodo,
  institutional repositories, and Software Heritage even if the
  repo2ree service itself goes away. The artifacts are durable; the
  service is rehydratable.
- **Substrate-deference at every layer.** Because repo2ree doesn't
  replace any environment, experiment, or archive substrate,
  sunsetting the service doesn't break repos or invalidate deposits.
  Generated recipes (Dockerfile, `flake.nix`) are committed to the
  repo and continue to work standalone; deposited bundles continue to
  resolve on Zenodo / SWH.

The forward-compatible commitments in
[ARCHITECTURE.md](ARCHITECTURE.md#content-addressed-state-cas-and-the-action-cache)
(signed-result schema slot, resolver abstraction, content-addressed
blob transport) are also what make federated and post-service-life
adoption possible.

## Honest limits

- **Grading is only as good as the graders.** Each substrate type needs
  real inspection of its lockfile or manifest. That grading machinery
  is the central investment behind the Repro Label and is in progress,
  not finished.
- **Receipts are immutable but executors aren't.** A Receipt signed by
  an untrusted executor still requires trust in *that executor* —
  unless the Action is bit-reproducible, in which case independent
  re-derivations can attest to the same outputs (the
  reproducible-builds model).
- **Substrate floor still applies.** If the repo's environment
  substrate is a floating-tag Dockerfile, Receipts produced against it
  are only as reproducible as the pulls happened to be at the time.
  The Label will say so loudly.
- **Bit-for-bit determinism is opt-in, not the default claim.** Default
  is input-identity caching
  ([ARCHITECTURE.md](ARCHITECTURE.md#content-addressed-state-cas-and-the-action-cache));
  bit-equal verification via action re-execution is only meaningful for
  substrates whose builds are themselves bit-reproducible.
- **GPU and hardware variation are out of scope.** Software-deterministic
  to the extent the substrate is; floating-point identity across GPU
  models or CPU vendors is not promised.
- **Archive horizon ~10 years on commodity hardware.** Beyond that
  needs emulation, which the archive format permits but the project
  does not provide.
- **CS-scoped by design.** Born inside NFDIxCS; tuned to CS-specific
  substrates and reproducibility threats. Other disciplines may benefit
  but are not the target — other NFDI consortia serve their own
  communities with their own tooling.

## One-line summary

repo2ree is the **NFDIxCS integration layer for reproducible CS
research**: it binds environments, experiments, and archives — through
*Repro Labels* disclosing what you've got, *Run Receipts* recording
what you ran, *Verify* letting anyone re-derive your claim, and
*Archive* depositing the whole bundle on Zenodo and SWH — into one
continuous reproducibility loop.
