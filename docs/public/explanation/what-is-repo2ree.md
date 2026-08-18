# What is repo2ree?

repo2ree is an integration layer for reproducible computational research: it
helps an author create a
[Reproducible Execution Environment](what-is-an-ree.md), and gives everyone
after them a way to check it.

Researchers already have capable tools at three layers:

| Layer | Existing tools |
|---|---|
| Environment | Docker, Nix, conda, uv, Apptainer |
| Experiment | scripts, workflow engines, MLflow, W&B, logs |
| Archive | Software Heritage, Zenodo, Dataverse, DataCite |

Nothing binds them. A build system describes an environment but does not grade
it. A tracker records a run but does not tie it to a rebuildable environment. An
archive preserves files but does not compose them into something a reader can
re-run. repo2ree leaves each substrate in place and supplies the binding, in
the form of an REE.

## Authoring an REE

Authoring is a guided pass over a repository that ends in a downloadable REE.
You specify how to obtain the source code, how to build the runtime, how the
built runtime is activated, which command is the experiment, and what counts as
a passing result. Each step runs in an isolated workbench and leaves a receipt.

The work sits with the author deliberately, for three reasons:

| | |
|---|---|
| **Information** | The author knows which of the twelve scripts is the experiment, which flags matter, and what "it worked" means. A reader is guessing. |
| **Multiplicity** | One author, many readers over the artifact's life. Work done once upstream is work not repeated by each of them. |
| **Decay** | The author's knowledge is perishable. Within a year it is gone, including from the author. Capturing it is only cheap while it is fresh. |

Two obligations follow. The first is to keep the cost small: repo2ree reads the
repository and proposes build and activation scripts for you to confirm rather
than compose. It stops deliberately short of choosing an experiment command,
because it cannot know what your software does, and a wrong guess that runs
produces evidence worse than none.

The second is to pay the author back in the same transaction. The sealed bundle
has to be worth something to the person who made it: runnable by their future
self, ready for deposit, citable. Effort that only benefits downstream readers
is a design defect, not a virtue.

See [Create your first REE](../tutorials/create-your-first-ree.md) for the
walkthrough, or [Build and run an REE](../how-to/build-and-run.md) for the
individual steps.

## Reviewing an REE

A reviewer loads a sealed bundle and reproduces it. repo2ree acquires the source
again, rebuilds the runtime from the author's recipe, tests activation, re-runs
each declared experiment, and executes the author's verify scripts. Every step
is compared against the author's baseline: source identity, runtime digest or
SBOM closure, activation outcome, and experiment results.

repo2ree has no special review mode. A review attempt is an ordinary REE tree of
its own, and the reviewer runs the same operations the author ran, producing the
same kind of receipts. Two things make it a review. The attempt is isolated, so
the author's evidence is read and never written, and each step ends in a
recorded comparison rather than only a receipt.

This is what the authoring discipline buys. Because the experiment was named and
its verify script declared, "did it reproduce" has an answer that does not depend
on a reviewer's judgment about which script to run. Where a result differs, the
disagreement is located in a specific step with specific digests on both sides.

See [Verify a result](../how-to/verify.md).

## Grading reproducibility

Before anything is built, repo2ree can assess a repository as it stands. Evaluate
scans for dependency declarations, manifests, lockfiles, runtime hints, and
concrete risks such as floating image tags, unpinned installs, and missing
base-image digests. It scores independent axes for dependencies, environment,
and machine.

Two properties matter more than the score.

It is **observational**. The Label describes a repository without changing it and
without requiring the author to have used any particular tool. A Nix-built
project earns a high Label because Nix is rigorous; a `FROM python:3.11`
Dockerfile earns a low one because the tag floats. Nothing needs porting or
migrating first, so a venue or a reviewer can label a submission with no author
cooperation at all.

It is **disclosure, not a verdict**. A low Label does not mean the science is
wrong; it means the artifact carries risks that should be explained, fixed, or
captured elsewhere. The threats it names are concrete enough to act on, which
gives a low Label an improvement path: pin the digest, commit the lockfile, or
have repo2ree generate a recipe with pinning built in. The diagnostic is the
product; generation is one remedy inside it.

Evaluate grades the *source*. It is separate from the REE assessment, which
reads an assembled REE and reports which evidence is current and which has gone
stale. Neither proves a reproduction; that takes a review.

See [Evaluate a repository](../how-to/evaluate.md).

## Compute that stays where the data is

repo2ree separates coordination from execution. The API and GUI form a control
plane that decides what should run; the actual work happens inside a workbench
provisioned by an **agent** that the resource owner installs inside their own
boundary. A private machine, a laboratory, a university cluster, a facility, or
a cloud account each runs its own agent.

The agent is a gateway, not the compute. It translates repo2ree operations into
calls to whatever runtime or scheduler exists locally, and advertises only the
capabilities its owner chooses to expose. It connects outward, so no institution
has to open an inbound endpoint. Infrastructure credentials stay on the owner's
side: cloud keys, kubeconfig, scheduler access, the container socket. The
repo2ree API never receives them.

That split is what lets the work go to the data rather than the reverse. Corpora
that legally cannot leave an institution can still be used in an REE, because
the workbench runs inside the institution. Clusters where Docker is unavailable
are an adapter problem rather than an exclusion.

See [Federated compute](../reference/architecture/federated-compute.md) for the
architecture.

## How repo2ree compares

Several projects address neighbouring parts of this problem. Four questions
separate them: what each asks of you before it says anything, what it means when
it reports that something reproduced, where the computation happens, and what a
reader still holds once the service behind it is gone.

**[Code Ocean](https://codeocean.com/)** is the closest comparator, and a source
of ideas. A Compute Capsule bundles code, environment, data, and results into one
hosted runnable, and its Reproducible Run badge appears in peer review at
Nature-family journals. It sets the usability bar: one button, and a reviewer
gets an answer.

Capsules version their experiment results inside the platform. An REE instead
carries the author's verify scripts and per-experiment output baselines, so a
review reports separately whether the run happened and whether the claim held.

Code Ocean also ships a run script that reproduces a capsule on a local machine,
outside the platform. That idea shaped ours: every REE bundle carries a
standalone run script.

**[Whole Tale](https://wholetale.org/)** binds narrative, code, data, and
environment into a "tale" that runs inside the platform. The same two points
apply: verification means the tale ran, and the entry price is porting the
project into a tale first.

**[Binder](https://mybinder.org/) and
[repo2docker](https://repo2docker.readthedocs.io/)** build an ephemeral session
on demand from a repository. That is a different goal: nothing is meant to
persist, and nothing is claimed about results. A Binder link works while the
service and its base images remain.

**[ReproZip](https://www.reprozip.org/)** takes the opposite approach: it
captures one execution post hoc by tracing it, and packs the trace for replay.
No authoring discipline is required, which is its appeal, and nothing
declarative comes out of it. An `.rpz` replays, but it cannot say what the run
was supposed to prove.

**[Renku](https://renkulab.io/), [JupyterHub](https://jupyter.org/hub),
[devcontainers](https://containers.dev/), and
[Codespaces](https://github.com/features/codespaces)** are not rivals at all.
They answer "how do I work reproducibly?", a question that comes *before*
repo2ree's. Renku records provenance, dataset versions, and workflow executions
continuously as you work, so a Renku-authored project arrives with code, data,
and provenance already in a working state, and earns a better Repro Label for
it. The two questions stack: repo2ree starts when the work exists and asks how
to disclose, verify, and archive it.

### Compute goes to the data

This is where the architectures diverge most sharply, and it is easy to
misread as a self-hosting question.

Renku and BinderHub are open source, so an institution can deploy its own
instance. What it gets is an island: a second, separate platform, with its own
users, its own projects, and no relationship to the deployment next door.
Code Ocean and Whole Tale do not offer even that: computation happens in their
cloud, on their terms.

repo2ree splits the control plane from the execution plane. One coordinating
service can dispatch work to agents run by many different owners, each keeping
its own credentials, quotas, and hardware, and each connecting outward rather
than exposing an endpoint. A university does not have to run a whole platform to
contribute compute; it runs an agent. A dataset that cannot legally leave the
building is still usable, because the workbench comes to it.

That is a different shape of problem than "can I self-host this?", and it is
the one an institutional consortium actually has. Today the agent drives Docker
and provisions a workbench per REE on its host; scheduler, cluster, and cloud
adapters are designed extension points rather than shipped features. See
[Federated compute](../reference/architecture/federated-compute.md) for the
design.

### Platform mortality

"We are open, they are commercial" is true of Code Ocean and insufficient.
Renku, Whole Tale, and Binder are open too, and none of them displaced it in
artifact evaluation.

The argument that holds is what survives the platform. A capsule DOI resolves to
one company's domain; a tale lives in a Whole Tale instance; a Binder link
rebuilds only while the service and the base images remain. An REE is a
directory of ordinary files with a documented layout, its source resolvable
through [Software Heritage](https://www.softwareheritage.org/) and its bundle
deposited in repositories built to outlive any single vendor, repo2ree
included. Openness is the mechanism, not
the message: anyone can re-host the machinery, so the evidence chain has no
single point of failure.

### Prior formats are inputs

A Code Ocean capsule maps almost directly onto an REE: `code/` to source,
`environment/` to an overlay build recipe, `metadata.yml` to declarations, and
`results/` to baseline outputs. The same holds for Whole Tale tales, Binder
configs, and [RO-Crate](https://www.researchobject.org/ro-crate/) metadata.
Importing one is an upgrade rather than a port: the author keeps what they built
and gains a Label, receipts on re-execution,
and a bundle that outlives the platform it came from.

## What repo2ree is not

repo2ree is not a hosted IDE, notebook server, JupyterHub, or replacement for a
lab's authoring environment. Software development and experiments belong in your
preferred environment. repo2ree starts when there is an artifact to make
understandable, runnable, and shareable.

It is also not an archive. repo2ree prepares bundles and metadata for archiving
services such as [Zenodo](https://zenodo.org/) and
[Dataverse](https://dataverse.org/), which supply the durable storage and the
identifiers. Live deposit adapters for those services are planned work.
