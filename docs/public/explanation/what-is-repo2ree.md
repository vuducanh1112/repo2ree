# What is repo2ree?

repo2ree is an integration layer for reproducible computer-science research: it
helps an author turn a repository into a
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
re-run. repo2ree leaves each substrate in place and supplies the binding.

## Authoring an REE

Authoring is a guided pass over a repository that ends in a sealed bundle. You
point repo2ree at source, it evaluates what the repository declares, and you
fill in what a README would leave implicit: where the build lives, how the built
runtime is activated, which command is the experiment, and what counts as a
passing result. Each step runs in an isolated workbench and leaves a receipt.

repo2ree asks for convention where the ecosystem offers none — a reserved build
script, a reserved activation script, and named experiments whose verify scripts
define the claim. That records knowledge the author already has in a form a
machine can act on later.

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
has to be worth something to the person who made it — runnable by their future
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
same kind of receipts. What makes it a review is that the attempt is isolated —
the author's evidence is read and never written — and that each step ends in a
recorded comparison rather than only a receipt.

This is what the authoring discipline buys. Because the experiment was named and
its verify script declared, "did it reproduce" has an answer that does not depend
on a reviewer's judgment about which script to run. Where a result differs, the
disagreement is located in a specific step with specific digests on both sides.

See [Verify a result](../how-to/verify.md).

## Grading reproducibility

Before anything is built, repo2ree can assess a repository as it stands. Evaluate
scans for dependency declarations, manifests, lockfiles, runtime hints, and
concrete risks — floating image tags, unpinned installs, missing base-image
digests — and scores independent axes for dependencies, environment, and
machine. The result is the seed of a **Repro Label**.

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
stale. Neither one proves a reproduction — that takes a review.

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
has to open an inbound endpoint. Infrastructure credentials — cloud keys,
kubeconfig, scheduler access, the container socket — stay on the owner's side
and are never handed to the repo2ree API.

That split is what lets the work go to the data rather than the reverse. Corpora
that legally cannot leave an institution can still be used in an REE, because
the workbench runs inside the institution. Clusters where Docker is unavailable
are an adapter problem rather than an exclusion.

Today the agent drives Docker and provisions a workbench per REE on its host.
Scheduler, cluster, and cloud adapters are designed extension points rather than
shipped features — see [Current capabilities](../reference/current-status.md)
for the line between the two, and
[Federated compute](../reference/architecture/federated-compute.md) for the
design.

## How repo2ree compares

The nearest neighbour is Code Ocean, whose Compute Capsule bundles code,
environment, data, and results into a hosted runnable, and whose Reproducible
Run badge is used in peer review at Nature-family journals. It sets the usability
bar: one button, and a reviewer gets an answer.

The differences are structural rather than competitive.

| | Hosted platform | repo2ree |
|---|---|---|
| Entry price | Migrate the project into the platform | Point at the repository you already have |
| Disclosure | Nothing to say until migration is done | A Repro Label on the repository as-is |
| Verification | Did it execute | Did it execute, did artifacts match their contracts, does the claim still hold |
| Compute | The platform's cloud | Wherever an agent runs, including self-hosted and institutional |
| Archive | An identifier resolving to the platform | Software Heritage, Zenodo, and DataCite; the bundle opens without repo2ree |

The sharpest of these is the last. "We are open, they are commercial" is true and
not enough — Whole Tale and Binder are open too. The argument that holds is
tolerance of platform mortality: a capsule identifier resolves to one company's
domain, and if that company pivots or shuts down, the artifact degrades. An REE
is a directory of ordinary files with a documented layout, its source resolvable
through Software Heritage and its bundle deposited in repositories that outlive
any single vendor. Openness is the mechanism here, not the slogan: anyone can
re-host the machinery, so the evidence chain has no single commercial point of
failure.

Prior formats are inputs rather than rivals. A Code Ocean capsule maps almost
directly onto an REE — `code/` to source, `environment/` to an overlay build
recipe, `metadata.yml` to declarations, `results/` to baseline outputs — and the
same holds for Whole Tale tales, Binder configs, and RO-Crate metadata.

Tools that make *authoring* reproducible — Renku, JupyterHub, devcontainers,
Codespaces — sit upstream of repo2ree rather than opposite it. They answer "how
do I work reproducibly?"; repo2ree answers "now that the work exists, how do I
disclose, verify, and archive it?" The two questions stack, and a project that
arrives from one of those environments earns a better Label for it.

## What repo2ree is not

repo2ree is not a hosted IDE, notebook server, JupyterHub, or replacement for a
lab's authoring environment. You keep your editor and your research workflow.
repo2ree starts when there is an artifact to make understandable, runnable, and
shareable.

It is also not a permanent archive. Archives preserve objects and identifiers.
repo2ree prepares a better object for them to preserve.
