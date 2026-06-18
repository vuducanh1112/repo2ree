# repo2ree — Positioning

> **Status: positioning statement (2026-05).** The **why** of repo2ree —
> strategic framing, audience, and relationship to neighbouring tools.
> For *what* each named concept means see [CONCEPTS.md](../CONCEPTS.md);
> for *how* it's implemented see [ARCHITECTURE.md](../ARCHITECTURE.md).

## In one sentence

repo2ree is the **integration layer for reproducible CS research**: it
binds the three layers researchers already use — environments (Docker /
Nix / VMs), experiments (parameterized runs with traces), and archive
(Zenodo / Software Heritage) — into one continuous loop. **Repro Labels**
disclose what you've got; **Run Receipts** record what you ran; **Verify**
lets others re-derive your claim; **Archive** prepares the bundle for
Zenodo/Dataverse-style deposit and SWH-backed source identity.

## Context

repo2ree is developed within **NFDIxCS**, the German National Research Data
Infrastructure consortium for computer science. Its mandate is durable,
federated, FAIR-aligned infrastructure that composes with existing tooling. That
is why repo2ree is an integration layer, not another destination platform.

The first audience is NFDI: partner institutions, repository deposit workflows,
PID/IAM base services, and Artifact Evaluation pilots.

## The gap

Research code has two structural failures:

- **Reproducibility is unobservable.** A repo either builds for you or it
  doesn't. There is no *measurement* of how reproducible it is, what
  makes it fragile, or what would improve it — no signal for reviewers,
  future maintainers, or the author's own future self.
- **A "run" of code is not a thing.** Papers report numbers; repos
  sometimes reproduce builds; *the act of running this code with these
  parameters in this environment and getting these outputs* is not a
  structured, durable, citable object anywhere in the current toolchain.

Both are **integration failures**. Build systems describe environments but do
not score them. Trackers record runs but do not bind them to reusable
environments. Archives preserve files but do not compose them into a re-runnable
claim object.

## Three layers, one integration

Reproducible CS research already has mature tools at three layers:

| Layer           | What it provides                                | Mature substrates                                                                       |
|-----------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| **Environment** | Build and run the code in a specified state     | Docker, Nix, Bazel, conda, uv, Apptainer, Kata VMs                                      |
| **Experiment**  | Run computations and capture what they produced | Snakemake, Nextflow, CWL, REANA *(workflow shape)*; MLflow, W&B, Neptune, Aim *(tracking shape)*; plain scripts |
| **Archive**     | Preserve and identify the artifact long-term    | Software Heritage, Zenodo, DataCite, PID4NFDI                                           |

Nothing ties them together. repo2ree leaves substrates in place and adds the
vocabulary, bindings, and workflows that turn them into one citable artifact.

## Design principles

Two principles shape the product.

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

Users keep their editor, hub, or hosted environment; repo2ree certifies the
artifact that emerges.

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
| **Archive**            | One click + tier choice                                     | A sealed, deposit-ready bundle; DOI/SWHID once adapters run |

The user brings what they already have; repo2ree wraps it.

## Four nameable surfaces: two primitives, two workflows

Two primitives are cited and deposited; two workflows make them useful.

| Surface         | Kind      | What it is                                                                                                          |
|-----------------|-----------|---------------------------------------------------------------------------------------------------------------------|
| **Repro Label** | Primitive | The repo's standing reproducibility disclosure — a nutrition label.                                                 |
| **Run Receipt** | Primitive | A single execution's structured record — environment, inputs, outputs, result.                                      |
| **Verify**      | Workflow  | One click: re-derive a Receipt on your own compute, get a comparable, citable diff.                                 |
| **Archive**     | Workflow  | One click: seal and prepare/deposit the Label, Receipts, and REE bundle through archival infrastructure. |

Seal is the freeze point inside Archive: it creates the content digest that
signatures and deposits refer to.

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
ree_digest      which sealed REE executed the run
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
[ARCHITECTURE.md](../ARCHITECTURE.md#the-wire-form-a-typed-action-envelope).

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

---

### Archive

*Integrates: Lifecycle artifacts → Archive substrates.*

> *Click Archive. The REE composes into a bundle shaped for Zenodo,
> Dataverse, or institutional deposit, with source identified through
> Software Heritage when possible. The bundle is the citable artifact;
> the service is just how you got it there.*

Archive composes the primitives with **institutional archival
infrastructure**. repo2ree never runs its own permanent archive; it
composes with Software Heritage (source code), Zenodo/Dataverse-style
repositories (bundles and DOIs), and NFDI base services (PIDs, identity).

The bundle is a **composition manifest** rather than a self-contained
tarball: source by SWHID *pointer* (because SWH owns source archival),
overlay and Receipts inline (because they are repo2ree's contribution), a Seal
Manifest that names the exact content, and artifacts by **fidelity tier**:

| Tier        | Contents                                                  | Best for                                              |
|-------------|-----------------------------------------------------------|-------------------------------------------------------|
| **Cite**    | declaration + overlay + source-pointer + Receipts + Label | Drafts, citation-only artifacts                       |
| **Replay**  | Cite + the built runtime image                            | Paper supplementary material — *the default*          |
| **Rebuild** | Replay + inputs closure (vendored deps)                   | Audit-grade, dead-internet-tolerant archival          |

Each tier is a strict superset of the previous. The Label discloses
which tier was deposited — an observable reproducibility property
visible to reviewers at a glance.

SWH, Zenodo, Dataverse, and institutional repositories already exist. Archive
composes with them instead of duplicating them.

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
  (source), Zenodo/Dataverse/institutional repositories (bundles), and
  DataCite / PID4NFDI (identifiers).
  repo2ree composes archive-ready bundles; it doesn't store anything
  permanently.

A Nix-built repo earns a high Repro Label — *exactly as intended* — and
its Run Receipts inherit Nix's reproducibility floor. An
MLflow-instrumented run becomes a Receipt with the tracker's metadata
preserved. A repo with no tracking yields a Receipt assembled from
stdout, outputs, and exit code.

The story is `<your substrates> + repo2ree`, never `repo2ree vs. anything`.

## Comparator landscape

repo2ree's relationship to neighbouring tools falls into three buckets:
**substrates we integrate**, **lifecycle peers** we differentiate from,
and **cultural / analogue precedents** that frame the work.

### Substrates we integrate

| Substrate                                              | Layer       | Relationship                                                                                                                |
|--------------------------------------------------------|-------------|-----------------------------------------------------------------------------------------------------------------------------|
| Nix / Bazel / Docker / conda / uv / apt                | Environment | repo2ree runs whatever the repo brought; the Label grades its reproducibility floor.                                        |
| Snakemake / Nextflow / CWL / REANA (workflows) · MLflow / W&B / Neptune (tracking) · plain scripts | Experiment | The Run Receipt wraps whatever the substrate ran — workflow DAG, ML run, or single command — and preserves its metadata. |
| Software Heritage / Zenodo / Dataverse / DataCite / PID4NFDI | Archive | The Archive workflow prepares bundles for these services and consumes their identifiers. |

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

> *Paper-shaped prose version of the comparator landscape above.*

Adjacent tools solve important pieces. repo2ree's claim is the binding:
graded repository disclosure, citable Run Receipts with lineage, and
cross-substrate re-derivation.

### Authoring-time reproducibility environments

[Renku](https://renkulab.io/), [Code Ocean](https://codeocean.com/) editor
mode, [JupyterHub](https://jupyter.org/hub), [Open OnDemand](https://openondemand.org/),
[devcontainers](https://containers.dev/), Codespaces, and Gitpod make authoring
more reproducible. [ReproZip](https://www.reprozip.org/) captures a run
post-hoc.

These tools answer "how do I work reproducibly?" repo2ree answers "now that the
work exists, how do I disclose, verify, reuse, and archive it?" It treats these
systems as upstream; the Repro Label rewards the discipline they captured.

### Hosted reproducibility platforms

[Whole Tale](https://wholetale.org/), Code Ocean publish mode, and
[Binder / MyBinder](https://mybinder.org/) host runnable artifacts or sessions.
They are valuable, but they ask users to adopt the platform. repo2ree works on
repositories regardless of authoring environment, grades reproducibility as a
repository property, and deposits through existing archive infrastructure.

### Build, workflow, and tracking substrates

Environment tools such as Nix, Guix, Bazel, Docker, conda, and uv; workflow
tools such as Snakemake, Nextflow, CWL, REANA, and WorkflowHub; and trackers
such as MLflow, W&B, Neptune, and Aim are substrates. They are strong inside
their layers.

repo2ree binds those layers: it grades the repository, wraps runs into Receipts,
and pushes the composition into archival infrastructure.

### Verification and attestation systems

[Reproducible Builds](https://reproducible-builds.org/),
[rebuilderd](https://github.com/kpcyrd/rebuilderd), [SLSA](https://slsa.dev/),
and [in-toto](https://in-toto.io/) supply the pattern language:
content-addressed inputs and outputs, signed attestations, and provenance
chains.

repo2ree applies those patterns to research repositories and their runs, not
only packages or CI outputs. Its default fidelity is input identity; bit identity
is opt-in for substrates that support it.

### Archive infrastructure and cultural precedents

Software Heritage archives source with SWHIDs; Zenodo, Dataverse, DataCite, and
PID4NFDI provide deposit and identifiers; RO-Crate and DataLad shape research
objects and data; Papers with Code and ACM Artifact Evaluation show the cultural
demand.

repo2ree composes with this infrastructure. Archive prepares DOI-bearing
bundles, references SWHIDs, and produces RO-Crate-shaped metadata. Verify turns
artifact-evaluation practice into a repeatable workflow.

### Summary

The space is fragmented. repo2ree's novelty is the binding: Label, Receipt,
Verify, and Archive made consistent across substrates, usable without platform
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

Adoption should work without venue cooperation:

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

Build institutional and bottom-up use first; venue integration can follow.

## Sustainability

Two commitments make repo2ree survivable past any one service:

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

## Honest limits

- **Grading depends on real graders.** Each substrate type needs real lockfile
  or manifest inspection. That machinery is in progress.
- **Receipts are immutable; executors are trust roots.** A Receipt from an
  untrusted executor still requires trust in that executor unless independent
  bit-reproducible re-derivations agree.
- **Substrate floor still applies.** If the repo's environment
  substrate is a floating-tag Dockerfile, Receipts produced against it
  are only as reproducible as the pulls happened to be at the time.
  The Label will say so loudly.
- **Bit-for-bit determinism is opt-in.** Default is input-identity caching
  ([ARCHITECTURE.md](../ARCHITECTURE.md#content-addressed-state-cas-and-the-action-cache)).
  Bit-equal verification only applies to bit-reproducible substrates.
- **GPU and hardware variation are out of scope.** Software-deterministic
  to the extent the substrate is; floating-point identity across GPU
  models or CPU vendors is not promised.
- **Archive horizon ~10 years on commodity hardware.** Beyond that
  needs emulation, which the archive format permits but the project
  does not provide.
- **CS-scoped by design.** Born inside NFDIxCS; tuned to CS substrates and
  reproducibility threats. Other disciplines may benefit but are not the target.

## One-line summary

repo2ree is the **NFDIxCS integration layer for reproducible CS research**:
Label what you have, Receipt what you ran, Verify the claim, Archive the bundle.
