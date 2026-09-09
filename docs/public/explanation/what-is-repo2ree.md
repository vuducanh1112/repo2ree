# What is repo2ree?

repo2ree helps authors create a
[Reproducible Execution Environment](what-is-an-ree.md) and helps reviewers test
one. It connects tools that already describe source, software environments,
experiments, and archives.

| Layer | Examples |
|---|---|
| Environment | Docker, Nix, conda, uv, Apptainer |
| Experiment | scripts, workflow engines, run trackers |
| Archive | Software Heritage, Zenodo, Dataverse |

Each layer solves a useful problem. None alone records which source, runtime,
command, result, and check belong to one computational claim. The REE supplies
that binding.

## Authoring

An author chooses a compute location and provisions an isolated workbench. In
that workbench, the author:

1. acquires and freezes the source;
2. records project and hardware metadata;
3. evaluates reproducibility risks in the source;
4. builds and inventories the runtime;
5. tests activation;
6. declares experiments, outputs, and verification criteria;
7. seals a downloadable bundle.

Each operation leaves a receipt. When an input changes, repo2ree can identify
which evidence is stale.

repo2ree can generate scripts when the repository or built runtime provides
enough evidence. For example, it can derive Docker build and loading commands.
Generated activation and experiment scripts are fail-closed: repo2ree supplies
the runtime plumbing but leaves the meaningful command blank. The author must
decide what proves the runtime usable and what constitutes the experiment.

This division keeps routine work small without asking inference to make a
scientific decision.

See [Create your first REE](../tutorials/create-your-first-ree.md) for the full
workflow. See [The runtime of an REE](../how-to/build-runtimes.md) for runtime
packaging guidance.

## Reviewing

A reviewer imports a sealed bundle into a new workbench and starts a review
attempt. The review uses the author's declarations but keeps new execution state
separate from the sealed evidence.

The reviewer can reacquire source, rebuild the runtime, compare its digest or
SBOM, test activation, and rerun experiments. Each stage records its own result
and comparison. This separates questions that a single “reproduced”
badge would blur:

- Did the same source arrive?
- Did the runtime rebuild to the same environment?
- Could the runtime start?
- Did the author's check pass on fresh outputs?
- Were the output bytes identical?

The standalone `run.sh` in every bundle can execute the lifecycle without
repo2ree. A repo2ree review adds structured comparison against the author's
evidence.

## Reproducibility Readiness

Before a build, **Reproducibility Readiness** analyzes the repository's
declarations. It looks for manifests, lock files, environment definitions,
virtual-machine definitions, floating image tags, and unpinned dependencies.

The report presents three independent levels:

- **Dependencies**: how precisely the source declares software dependencies;
- **Environment**: whether a container or declarative environment is present;
- **Machine**: whether a virtual-machine definition captures the wider system.

The report observes without changing the repository or demanding a specific
packaging tool. It is a risk assessment, not a verdict on the science. A low
level identifies missing evidence and suggests concrete work,
such as committing a lock file or pinning a base-image digest.

Readiness evaluates source declarations. The REE audit answers a different
question: whether an assembled REE's execution evidence is present and current.
Only a review tests reproduction.

## Compute stays with its owner

repo2ree separates coordination from execution. The API and GUI form the
control plane. A connected provider provisions workbenches on infrastructure
owned by a lab, institution, facility, or cloud account.

The provider advertises a compute location and provisions or releases
workbenches there. It connects outward to the control plane on a capacity-only
connection and never receives an REE command. Each workbench opens a separate
outbound execution connection, receives the commands for one REE, and returns
logs and results directly. Infrastructure credentials and the host container
socket stay on the provider side of that boundary.

This design allows computation to run near restricted data. The current
provider uses Docker on one host and creates one workbench per REE allocation.
Scheduler, cluster, and cloud integrations, general resource matching, and
VM-backed isolation are extension points rather than shipped capabilities.

See [Federated compute](../reference/architecture/federated-compute.md) for the
architecture.

## Relationship to other tools

repo2ree does not replace development environments, workflow engines, container
builders, or archives. It consumes their outputs and records how they support a
specific result.

- Hosted capsule and “tale” systems combine code and an environment in a
  runnable service. An REE instead makes verification criteria and author
  baselines explicit in a portable bundle.
- Binder and repo2docker create interactive environments from repositories.
  They do not preserve experiment evidence or define what result should pass.
- ReproZip captures an execution after the fact. repo2ree uses declared recipes
  and checks that readers can inspect before and after execution.
- Renku, JupyterHub, devcontainers, and Codespaces support the work that happens
  before publication. A well-described project from any of them can become an
  REE.
- RO-Crate and other metadata formats can describe inputs to an REE. They do not
  replace its executable scripts and receipts.

The important boundary is portability. A sealed REE is a directory of ordinary
files with a documented layout and a standalone reproducer. You can store it
outside the repo2ree service that created it.

## Depositing and sharing

repo2ree is not an archive. The **Deposit & Share** step describes targets such
as Software Heritage, Zenodo, and Dataverse, while the sealed bundle remains the
object to preserve.

repo2ree currently supports Software Heritage presence checks. Uploading a
bundle there requires institutional deposit credentials. The Zenodo and
Dataverse capability models and UI are present, but live draft and publish
operations are not wired up yet. Authors can still download a sealed bundle and
deposit it through the archive's own interface.

Archives provide durable storage and identifiers. repo2ree prepares the bundle
and records the archive deposit that binds to its content digest.

## What repo2ree is not

repo2ree is not a hosted IDE, notebook server, or replacement for a laboratory's
normal authoring environment. It starts when an author needs to make a
computational project understandable, runnable, checkable, and shareable.

It also does not decide whether a scientific claim is valid. The author supplies
the experiment and its criterion; repo2ree records and executes them.
