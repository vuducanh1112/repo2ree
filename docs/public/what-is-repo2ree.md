# What is repo2ree?

repo2ree is an integration layer for reproducible computer-science research.
It takes a repository and helps turn it into a Reproducible Execution
Environment, or REE: source code, build/run instructions, runtime evidence,
experiment results, and archive metadata in one reusable object.

Researchers already use good tools for pieces of this job:

| Layer | Existing tools |
|---|---|
| Environment | Docker, Nix, conda, uv, Apptainer |
| Experiment | scripts, workflow engines, MLflow, W&B, logs |
| Archive | Software Heritage, Zenodo, Dataverse, DataCite |

repo2ree does not replace those tools. It connects them.

## Who it is for

Authors use repo2ree to disclose how reproducible a repository is, build a
runtime, capture experiment evidence, and prepare a shareable artifact.

Reviewers and readers use repo2ree to inspect the artifact, re-run declared
commands, and compare the result against published expectations.

Venues and institutions can use repo2ree as a reproducibility layer over their
own compute and archival infrastructure.

## What you bring and what you get

| You bring | repo2ree returns |
|---|---|
| A repository or source archive | A workspace with source, metadata, and reproducibility findings |
| Build instructions | A runtime image or runtime artifact |
| Experiment commands | Run evidence and output checks |
| Hardware and software context | HBOM and SBOM records |
| A finalized artifact | A sealed, downloadable REE bundle |
| Archive identifiers | Metadata that ties the bundle to durable repositories |

## What repo2ree is not

repo2ree is not a hosted IDE, notebook server, JupyterHub, or replacement for a
lab's authoring environment. You keep your editor and your research workflow.
repo2ree starts when there is an artifact to make understandable, runnable, and
shareable.

It is also not a permanent archive. Archives preserve objects and identifiers.
repo2ree prepares a better object for them to preserve.
