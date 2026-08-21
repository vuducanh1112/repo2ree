# repo2ree - Reproducible Execution Environments

> **Status: research thesis and target product description.** This document
> develops the complete REE model; it is not a current support matrix. See the
> [architecture reference](../engineering/reference/architecture.md) for the
> explicit implementation/target boundary.

## 1. One-sentence description

repo2ree is the integration layer for reproducible computer-science research:
it turns a repository, its execution environment, its experiment runs, and its
archival record into one reusable, verifiable, citable artifact.

## 2. Executive summary

Computer-science research already has mature tools for the pieces:
Docker/Nix/conda for environments, workflow and tracking tools for experiments,
and Software Heritage/Zenodo/DataCite/PID4NFDI for archival identity. These are
ecosystem references, not a v1 support matrix. The missing piece is integration.

repo2ree does not ask researchers to move into a new work environment, adopt a
new DSL, or abandon their build and tracking tools. It records and runs the
artifacts they already have:

| User brings | repo2ree returns |
|---|---|
| A repository | A Repro Label describing its reproducibility standing |
| A build script | A runnable Reproducible Execution Environment |
| An experiment command | A Run Receipt with inputs, outputs, traces, and provenance |
| A published receipt | A Verify workflow that re-runs and compares the claim |
| A finalized REE | A Seal Manifest with a stable `ree_digest` |
| An archive choice | A deposited bundle with persistent identifiers |

The project has four user-facing surfaces plus one lifecycle operation:

| Concept | Kind | Purpose |
|---|---|---|
| Repro Label | Primitive | A public disclosure of how reproducible a repository is. |
| Run Receipt | Primitive | A durable record of one execution and what it produced. |
| Verify | Workflow | A reviewer or reader re-runs a published claim and gets a comparable receipt. |
| Seal | Lifecycle operation | An author freezes the REE contents into a stable digest. |
| Archive | Workflow | An author deposits the sealed REE bundle through durable archive infrastructure. |

v1 scope is narrower: fixed source repositories, Docker/OCI runtimes, plain
experiment commands, Software Heritage source pointers, and Zenodo-style archive
bundles. Other substrate adapters are planned work.

Long term, papers should cite source, environment, comparison semantics, and the
runs behind their results. Reviewers should be able to re-derive them; archives
should stay usable without repo2ree.

## 3. Problem, gaps, and related work

### The problem

Research code has two structural reproducibility failures.

First, reproducibility is unobservable. A repository either builds for a
reviewer or it does not; there is rarely a public measure of what is pinned,
drifting, missing, or fixable.

Second, a run of code is rarely durable. Papers report numbers, repositories
contain scripts, and trackers may contain logs, but "this command, with these
parameters, in this environment, produced these outputs" is not usually portable
or citable.

Both failures are integration failures. Environment tools, trackers, and
archives each cover part of the lifecycle; repo2ree binds source, environment,
run, output, claim, and review lineage into one reproducibility object.

### The gaps repo2ree closes

repo2ree focuses on the gaps between existing tools:

| Gap | Consequence | repo2ree response |
|---|---|---|
| No public reproducibility disclosure | Reviewers cannot tell whether a repo is fragile until they try it. | Repro Label |
| No citable execution object | Results are detached from the run that produced them. | Run Receipt |
| No symmetric reviewer workflow | Reproduction often becomes informal notes or private failure reports. | Verify |
| No integrated archive bundle | Source, environment, outputs, and identifiers are scattered. | Archive |
| No substrate-neutral lifecycle | Reproducibility workflows often require one preferred platform. | Source + Overlay + REE composition |

The usual shorthand for reproducibility is:

```text
same inputs + same environment -> same outputs
```

For research code, that equation is often false in practice. GPUs,
floating-point reduction order, thread scheduling, randomized framework
defaults, timestamps, filesystem ordering, external services, and hidden seeds
can all produce different bytes from the same declared inputs. repo2ree's job is
to make the relevant parts explicit: inputs, environment, command, outputs,
comparison rule, and provenance.

### Related work

repo2ree relates to several families of tools.

Authoring-time environments such as Renku, Code Ocean editor mode,
JupyterHub, Open OnDemand, devcontainers, Codespaces, and Gitpod help
researchers work reproducibly. repo2ree is downstream: once the work exists, it
discloses, verifies, reuses, and archives the artifact.

Hosted platforms such as Code Ocean publish mode, Whole Tale, and Binder provide
runnable artifacts or sessions. repo2ree is substrate-neutral and
archive-oriented: it composes with the repository, environment, tracker, and
archive the researcher already uses.

Build, workflow, and tracking systems such as Nix, Guix, Bazel, Docker,
Snakemake, Nextflow, CWL, REANA, MLflow, W&B, Neptune, and Aim are substrates.
repo2ree records their outputs in one lifecycle.

Verification and attestation systems such as Reproducible Builds, rebuilderd,
SLSA, and in-toto provide patterns: content-addressed inputs, structured
provenance, signed claims, and independent verification. repo2ree applies them
to research repositories and claim-producing runs.

Archival infrastructure, such as Software Heritage, Zenodo, DataCite, PID4NFDI,
RO-Crate, and DataLad, provides durable storage and identifiers. repo2ree does
not replace those services. It prepares source, execution records, metadata, and
artifacts for preservation.

## 4. Reproducibility semantics

### Verify compares claims, not just bytes

Verify must not assume that every useful reproduction is bitwise identical.
Some artifacts should be byte-exact: lockfiles, source snapshots, declared
inputs, container image manifests, small deterministic outputs, and published
tables intended as exact files. Other artifacts need domain-aware comparison:
numeric tolerances, statistical intervals, repeated-run distributions, schema
checks, or manual review.

A Run Receipt therefore needs an output contract. For each advertised output, the
receipt should say what kind of comparison is meaningful:

| Contract | Match rule | Example |
|---|---|---|
| Byte exact | Content digest must match. | A generated CSV used directly in the paper. |
| Structured | Parse, normalize, and compare selected fields. | JSON metrics or benchmark tables. |
| Numeric tolerance | Compare with absolute or relative tolerance. | Runtime, accuracy, loss, memory use. |
| Statistical | Compare distributions or confidence intervals across repeated runs. | Stochastic training or simulation. |
| Claim assertion | Re-evaluate a paper-level predicate. | "Method A remains better than baseline B." |
| Manual | Preserve evidence but do not auto-pass or auto-fail. | Visual plots, qualitative examples, proprietary outputs. |

The Verify result should distinguish at least three questions:

| Question | Meaning |
|---|---|
| Did it execute? | The command ran in the declared environment. |
| Did the declared artifacts match? | Outputs satisfied their comparison contracts. |
| Does the claim still hold? | The paper-level assertion holds under the declared semantics. |

This prevents harmless timestamp or log differences from failing a verification
run, while also preventing vague reproducibility claims. If an output is
nondeterministic, the author should declare the expected nondeterminism, seed
controls, run count, and tolerance. If no meaningful comparator is declared,
Verify should report the output as unchecked rather than silently treating it as
reproduced.

### Repro Label is disclosure, not ranking

The Repro Label should publish observations on independent axes, not a single
aggregate score. A venue, reviewer, or search engine may still sort artifacts,
but repo2ree should avoid pretending that a linear grade captures the actual
tradeoffs.

Useful axes include dependency declaration, environment capture, data
availability, source-identifier stability, command clarity, output-comparison
coverage, closure capturability, and archive readiness. Each axis should expose
evidence and concrete risks: missing lockfiles, floating image tags, unpinned
package installs, network fetches without checksums, restricted datasets, absent
comparison contracts, or missing base-image digests.

## 5. Positioning

### Integration layer, not replacement

repo2ree is an integration layer across three substrate layers:

| Layer | What it provides | Example substrates |
|---|---|---|
| Environment | Build and run code in a specified state | Docker, Nix, Bazel, conda, uv, Apptainer, Kata VMs |
| Experiment | Run computations and capture what they produced | Snakemake, Nextflow, CWL, REANA, MLflow, W&B, Neptune, Aim, plain scripts |
| Archive | Preserve and identify artifacts long-term | Software Heritage, Zenodo, DataCite, PID4NFDI |

The table names the broader ecosystem, not the v1 adapter set. The minimal
viable substrate set is:

| v1 substrate | Scope |
|---|---|
| Docker / OCI | Build and run a declared runtime image. |
| Plain scripts | Execute author-provided shell commands and capture receipts. |
| Software Heritage pointer | Identify archived source when available. |
| Zenodo-style bundle | Deposit or export the composed archive bundle. |

Nix, Bazel, conda, uv, Apptainer, workflow engines, experiment trackers, and
specialized archives are planned adapters. They should improve fidelity when
present, but the core product must be useful before those integrations exist.

The relationship is always:

```text
your substrates + repo2ree -> reusable execution environment
```

repo2ree does not compete with a well-written Nix flake, a careful Dockerfile,
or an MLflow run. It uses and records them. More precise substrates improve
Repro Label observations; tracked runs produce richer Run Receipts; preserved
source identifiers strengthen archive bundles.

### Not a work environment

repo2ree is not where researchers write code. It is not a hosted IDE, a
JupyterHub, a notebook server, or a development platform. Its editor-like views
are for managing what repo2ree contributes beside the source:
declarations, overlays, generated recipes, build scripts, experiment specs, and
archive metadata.

Researchers keep their existing authoring workflow. repo2ree begins after
authoring: at disclosure, verification, reuse, and archival deposit.

### Bring a script, get a receipt

The interaction model should stay declarative and familiar:

| Moment | User provides | User gets |
|---|---|---|
| Label | Repository pointer | Reproducibility disclosure and concrete threats |
| Build runtime | The script they would run locally | Built runtime image and build evidence |
| Run experiment | The command they would type locally | Run Receipt with parameters, traces, outputs, and result |
| Verify | A published REE or receipt set | Reviewer receipts and diffs |
| Archive | Tier choice and metadata | Deposit-ready bundle; DOI/SWHIDs when archive adapters are wired |

The user need not learn repo2ree's internal model. The model exists to make the
result verifiable and citable.

### Audience and adoption

The first audience is NFDI: CS researchers, partner institutions, reviewers,
data stewards, and services that need durable, federated, FAIR-aligned
infrastructure. The wider audience is any author, reviewer, venue, or reader who
wants citable execution evidence.

The first adoption target should be narrower than "all researchers": one or two
artifact-evaluation pilots with NFDI-aligned CS partners. Authors publish
receipts for selected claims, reviewers run bounded Verify, and institutions use
Archive to preserve accepted artifacts.

## 6. What is an REE and core concepts

### REE

An **REE**, or **Reproducible Execution Environment**, is the composition of a
source repository, a repo2ree overlay, a built runtime, and the artifacts that
record execution inside that runtime.

An REE is not a single file. It is a structured reproducibility object:

```text
Source + Overlay + Runtime + Artifacts = REE
```

It is the unit a user cites, verifies, archives, and reuses.

### Source

The **Source** is the pristine repository at a fixed commit. It belongs to the
original author and is not modified by repo2ree. At runtime, it lives under the
REE workspace. Once archived, it should resolve to a stable source identifier,
usually a Software Heritage identifier.

### Overlay

The **Overlay** is repo2ree's contribution beside the source. It holds
declarations, generated build scripts, generated Dockerfiles or flakes,
experiment specifications, and other material that turns a plain repository into
a specified execution environment.

repo2ree can use an existing repository without writing repo2ree-specific files
back into the original source tree.

### Runtime

The **Runtime** is the built environment that executes the repository: an OCI
image in the Docker-oriented flow, or another substrate's output later. What
matters is that it is specified, built from known inputs, and tied to the
actions and outputs it produced.

### Artifacts

**Artifacts** are the outputs and evidence produced by repo2ree actions:
runtime images, SBOMs, dependency observations, run outputs, traces, logs,
metrics, result manifests, labels, and receipts.

### Repro Label

The **Repro Label** is the repository's standing reproducibility disclosure. It
observes the repository as-is and publishes independent axes such as dependency
declaration, environment capture, source-identifier stability, comparison
coverage, data availability, and closure capturability.

It is observational, not a ranking. It reports concrete risks such as floating
image tags, missing lockfiles, unpinned package installs, network fetches without
checksums, missing comparison contracts, restricted inputs, or missing base-image
digests.

### Run Receipt

The **Run Receipt** is a single execution's structured, content-addressed
record:

```text
ree_digest      which sealed REE executed the run
action_digest   which command and inputs were issued
parameters      typed run-specific inputs
outputs         produced files, content-addressed
traces          stdout, stderr, logs, metrics
result          the structured value the run advertised
comparators     output contracts and equivalence semantics
signatures      optional executor attestation
predecessor     optional pointer to the run this re-derives
```

Receipts are immutable. Author receipts and reviewer receipts have the same
shape; the predecessor pointer binds a verification run to the original claim.
A signed verification receipt turns "I reran it" into a durable claim: who
verified which predecessor, against which sealed REE, under which comparison
policy, with what verdict.

### Verify

**Verify** is the reviewer-facing workflow:

1. Load the REE and its published receipts.
2. Re-evaluate the Repro Label observations against the verifier's environment.
3. Re-execute each published Run Receipt against the same REE.
4. Produce new receipts whose predecessor pointers reference the originals.
5. Compare outputs using the receipt's declared contracts.
6. Report execution failures, artifact diffs, unchecked outputs, and
   claim-level comparison results.
7. Optionally sign the verification receipt as reviewer, executor, venue, or
   institution evidence.

No special reviewer mode exists. Authors and reviewers use the same machinery.
The difference is the signed claim attached to the receipt.

### Data and restricted inputs

Data must be modeled explicitly. Many research failures come from data rather
than code: multi-hundred-GB datasets, private or licensed corpora, changing
benchmark mirrors, access-controlled APIs, and files that are legal to use but
not legal to redistribute.

repo2ree should treat data inputs explicitly:

| Data case | v1 behavior |
|---|---|
| Small redistributable data | Include by digest in the bundle when the selected tier allows it. |
| Large public data | Record stable pointers, checksums, version metadata, and retrieval instructions. |
| DataLad or similar managed data | Preserve dataset identifiers and required retrieval commands. |
| Restricted data | Record access requirements, expected digests, and unverifiable status for reviewers without access. |
| Live services | Record endpoint, query, timestamp, response digest when captured, and drift risk. |

For v1, full data archiving is out of scope except for small redistributable
inputs. Replay bundles may point to large or restricted datasets instead of
containing them. The Label and Verify result must make that limitation visible:
"environment reproduced but restricted data unavailable" is a useful outcome,
but it is not the same as end-to-end reproduction.

### Archive

**Archive** is the author-facing deposit workflow. It consumes the sealed REE
and composes the declaration, overlay, source pointer, receipts, Label, Seal
Manifest, signatures, and selected artifacts into a bundle for durable archival
services.

repo2ree does not run the permanent archive. Source code belongs in Software
Heritage; bundles and DOIs belong in Zenodo; persistent identifiers come from
DataCite or PID4NFDI. repo2ree prepares and connects the pieces.

### Seal and signatures

**Seal** is the freeze point before Archive. It creates a canonical Seal
Manifest and computes:

```text
ree_digest = sha256(canonical_seal_manifest)
```

The manifest hashes the REE contents by component: source identity, overlay,
runtime artifact, dependency closure when present, Label, Receipts, and selected
fidelity tier. It should hash a stable inventory of content digests, not a zip
or tarball whose byte layout may drift.

Sealing and signing are separate:

| Mechanism | Answers |
|---|---|
| Seal digest | Which exact REE is this? |
| Signature | Who claims what about this REE, when, under which policy? |
| DOI/PID | Where is this REE retrievable and citable? |

Signatures are append-only attestations over `ree_digest`, not part of the
digest they sign. Useful signatures include author approval, executor
attestation, reviewer verification, venue/institution acceptance, and archive
binding. Long-term archives must preserve the signature envelope, key or
certificate material, timestamp evidence, verification policy, and hash
algorithm identifiers.

See [sealing.md](sealing.md) for the detailed lifecycle.

### Fidelity tiers

The archive bundle can preserve different amounts of material:

| Tier | Contents | Re-runnable? | Re-derivable? | Typical use |
|---|---|---|---|---|
| Cite | Declaration, overlay, source pointer, receipts, label | If upstreams are alive | If upstreams are alive | Quick citation, reviewer verification deposit |
| Replay | Cite + built runtime image | Yes | No | Paper supplementary material |
| Rebuild | Replay + captured input/dependency closure | Yes | Yes | Audit-grade or dead-internet-tolerant archival |

Replay is the practical default for most papers: it preserves long-term
runnability without requiring full dependency-closure capture.

### Cost, quotas, and responsibility

Verification and archiving have real costs. Reviewer reruns can require paid GPU
time, large egress, and storage for runtime images or datasets. Archives also
have quotas and preservation policies. A multi-GB runtime image or 500GB dataset
cannot be assumed to fit archive limits or review budgets.

repo2ree should report cost before deposit or verification:

| Cost item | What repo2ree should expose |
|---|---|
| Runtime image size | Expected archive footprint and quota risk. |
| Data footprint | Included bytes versus external pointers. |
| Compute estimate | CPU/GPU needs, wall time, and memory from the author receipt. |
| Verification mode | Smoke run, selected receipt, full rerun, or statistical rerun. |
| Payment boundary | Author, reviewer, institution, venue, or external compute grant. |

The v1 default is not "every reviewer reruns every GPU training job." Authors
publish receipts and comparison contracts; reviewers run smoke or selected
verification paths; venues and institutions decide when to fund full reruns.

### Lifecycle states

An REE moves through archival-readiness states:

| State | Meaning | Canonical archive? |
|---|---|---|
| Draft | Source has no stable identifier or is still actively changing. | No |
| Archive-ready | Source has a stable identifier and the declaration/overlay are stable. | Yes |
| Sealed | Seal Manifest and `ree_digest` exist; edits create a new seal. | Yes |
| Deposited | Bundle has been deposited and identifiers have been assigned. | Already archived |

## 7. Architecture

### Control plane and execution plane

The target architecture is a control plane driving an isolated execution plane.

The **control plane** includes the GUI, API, service layer, and host CLI.
It owns user intent, manifests, optimistic concurrency, lifecycle decisions,
job dispatch, logs, metadata, and archive/deposit orchestration.

The **execution plane** is an isolated workbench for each REE. It owns the
durable REE tree, builds the runtime image, runs experiments, generates SBOMs,
evaluates dependency observations, and writes artifacts.

The split is:

```text
gui / api / host cli
        |
        | typed command envelope
        v
isolated workbench
        |
        v
core execution logic, runtime build, experiment runs, artifacts
```

### Working environment layout

Inside the workbench, the REE has a stable tree:

```text
/ree
+-- upstream/    # extracted source snapshot
+-- overlay/     # declarations, generated recipes, experiment specs
+-- workspace/   # materialized upstream + overlay view
+-- artifacts/   # runtime image, SBOMs, observations, receipts, outputs, traces
+-- runs/        # per-command logs and results
```

`upstream/` and `overlay/` are the sources of truth; `workspace/` is derived.
The tree is the durable state. The running workbench is rehydratable: it can be
torn down and recreated from the persisted tree or, later, from
content-addressed storage.

### Isolation model

Untrusted repository code must not receive the host Docker socket. The current
main path uses a privileged Docker-in-Docker workbench; the target hardening
model is a VM-backed workbench, such as Kata Containers, where Docker activity
happens against a daemon inside the workbench rather than the host daemon.

In the current implementation, a separately deployed agent owns Docker and
launches the workbench; the API and supervisor do not hold the Docker socket.
Future agents may use another container or VM runtime. Build scripts and
experiment commands still run inside the isolated execution plane.

### REAPI alignment

The action model below intentionally resembles Bazel's Remote Execution API:
Command, InputRoot, Platform, Action, content-addressed storage, and action
caching. repo2ree should adopt REAPI concepts and compatible representations
where practical rather than inventing a parallel execution standard.

This section does not propose rebuilding Bazel. It defines which execution
concepts repo2ree needs. REAPI or a local REAPI-shaped subset should handle
deterministic action identity, digests, CAS, and cache invalidation. repo2ree's
specific work is Repro Labels, Run Receipts, comparison semantics, data
limitations, verification lineage, and archive bundles.

### Typed action envelope

Commands should cross the control/execution boundary as structured data, not as
interpolated shell strings. A command envelope identifies:

```text
Command:
  operation       build_runtime | generate_sbom | evaluate | run_experiment
  args            typed operation-specific inputs
  workbench_image digest of the workbench image
  output_paths    artifacts to capture

InputRoot:
  Merkle digest of workspace plus relevant overlay slice

Platform:
  runtime, CPU, memory, and other execution constraints

Action:
  command_digest
  input_root_digest
  platform_digest
  timeout
```

The resulting `action_digest` names exactly what was attempted. That digest can
be used for provenance, caching, replay, verification, and future signing.

### Content-addressed artifacts

Once actions and inputs have stable digests, outputs can be stored in a
content-addressed store:

```text
CAS:
  blobs/<sha256>    files, logs, run bundles, SBOMs
  trees/<sha256>    directory snapshots

ActionCache:
  action_digest -> ActionResult
```

This gives repo2ree correct invalidation and repeatability. Editing an
experiment spec does not rebuild the runtime unless the runtime action's inputs
changed. Re-runs compare output digests instead of informal claims. For
nondeterministic outputs, the digest preserves evidence; the comparator decides
equivalence for the declared claim.

### Component model

The implemented package shape has three libraries plus the agent runtime host,
the executor, and the API. The user-facing host CLI remains target work:

| Type | Name | Role | Deployed |
|---|---|---|---|
| Library | protocol | Typed command, result, and log-event contract. | Host and workbench |
| Library | core | Execution logic and `/ree` operations. | Workbench |
| Library | supervisor | Workbench lifecycle, registry, dispatch, transport. | Host |
| Runtime host | repo2ree-agent | Owns the runtime, provisions workbenches, injects the executor, and ferries protocol frames. | Agent host |
| Entry point | repo2ree-exec | Injected in-bench executor that reads commands and runs core. | Workbench |
| Entry point | repo2ree | User-facing host CLI that drives workbenches. | Host, planned |
| Entry point | api | Hosted HTTP API over service/supervisor logic. | Host |

The dependency rule is simple: host-side code speaks the protocol and manages
workbench intent through the agent; effectful execution logic lives inside the
workbench.

### Archive bundle

The archive bundle is a composition manifest rather than a monolithic permanent
store:

```text
bundle/
+-- metadata              # FAIR / RO-Crate-shaped metadata
+-- declaration/          # user intent and REE declaration
+-- overlay/              # repo2ree contribution beside the source
+-- source/               # normally a source identifier, not source bytes
+-- receipts/             # run receipts and verification lineage
+-- label/                # Repro Label snapshot
+-- artifacts/            # runtime image and closures according to tier
```

The division of responsibility is deliberate:

| Layer | Durable location |
|---|---|
| Source | Software Heritage |
| Bundle and DOI | Zenodo |
| Persistent identifiers | DataCite / PID4NFDI |
| Live execution state | repo2ree workbench and artifact store |

The service should be useful while running, but the archived artifact should not
depend on the service continuing to exist.
