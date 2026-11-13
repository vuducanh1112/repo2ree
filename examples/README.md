# Examples

Shared example inputs. Everything here is read by more than one place — the
GUI showcase and instant suites, the system tier, the API walkthrough, and by
hand when trying the app — so it lives at the repository root rather than inside one suite.

## `projects/`

The projects the suites author REEs from. Each folder holds `source/`, an
ordinary source tree with no REE metadata or receipts that the suites pack as an
upload, and `recipe/`, the scripts that run it which the suites do not write as
script inference proposes them. Which scripts those are, and what each project
needs deployed, is in `testbed/src/repo2ree_testbed/showcases.py`. The real-world projects pin what they fetch: base images by
digest, Python packages by hash.

### `instant/`

The project to reach for when a test needs the whole pipeline but not a real
toolchain. It runs on the standard library alone, and its `requirements.txt`
declares no packages, so it builds on any bench with Python and downloads
nothing. Script inference takes the pip/venv branch
(`root-pip-requirements-v1`): the generated build creates a venv, installs the
empty requirements without reaching an index, and packs the venv (about 4 MB)
as the runtime. `main.py` prints fixed output, so an experiment can verify it
exactly.

Driven through core's handlers with networking disabled, source to seal takes
about 4 s, the build about 2 s. Compare `python_docker/`, whose Docker
build pulls a base image and installs pandas and takes 40 s or more.

The SBOM steps are not covered yet: the scanner reads only `docker-archive:`
runtimes, and this runtime is a packed venv.

### `instant_docker/`

The instant project for a bench with its own Docker daemon, the product's
default. Its Dockerfile builds `FROM scratch`: the recipe's build copies the
bench's busybox and musl loader into the build context, so the bench's daemon
runs a real `docker build` (with a `RUN` step) and `docker run`, pulling and
downloading nothing. It prints the same output as `instant/`.

### `slurm/`

The instant project for a Slurm cluster. Its build is the same packed venv, made
on the machine the workbench runs on; the recipe's activation and experiment
submit `job.sh` with `srun`, and the verify script also checks the run happened
in a job. The submission is the author's own: the product runs these scripts
like any others. Run in more depth by `just test-e2e-slurm`.

### `apptainer/`

The instant project for a cluster with Apptainer. The recipe's build makes a SIF
from `runtime.def`, whose root filesystem is the machine's own Python and system
directories, downloading nothing; its activation and experiment enter that SIF in
a job with `srun apptainer exec`.
Submission and container entry are the author's own. Run by `just test-e2e-slurm`.

### `podman/`

A project whose recipe uses rootless Podman, on a machine where the workbench
runs scripts directly (`podman-host`). Its build runs `podman build` on the
`Containerfile`, which pins its Python base image by digest, and saves the
image as the experiment environment; its activation loads that image and runs
each experiment in it with `podman run`. Podman is the author's own tool here:
the product runs these scripts like any others. Run by
`just test-showcase-api 1 podman/`.

### `stochastic/`

An instant project whose result changes on every run: a Monte Carlo estimate of
pi from a freshly drawn seed, which it prints. Its verify script checks the
estimate within a tolerance, so a reviewer's rerun is `reproduced`, not
`identical`.

## `origins/`

`ree-e2e-fixture/` is the project the suites fetch from an origin URL. Each
test stack serves it itself, by git and as a tarball, with a fixed commit
author and date (`repo2ree_testbed.stack.origins`), so the fetch needs no
internet and always yields the same commit.

## `rees/`

Complete REEs, packaged the way `ree-archive` downloads them — the shape the
app loads back (workbench step → "Load REE bundle", or `POST
/api/v1/rees/{id}/ree:load`).

### `ree-hello-world.zip`

The REE the Python hello-world demo authors
(`gui/tests/demo/ree-create-python-hello-world.spec.ts`), carrying its real
author evidence: the frozen source snapshot, the four overlay scripts, the SBOM,
the reproducibility report, the captured experiment result, and the six author
receipts from that run.

Two deliberate differences from what the demo downloaded:

- **Unsealed.** The seal stamps are stripped, so loading it yields an editable
  REE rather than a read-only artifact.
- **No runtime artifact.** The demo's `runtime.tar` is a 327 MB Docker image
  export, too large to version, so it is dropped and the manifest records
  `runtime_included: false` with the runtime path pointing back at its workspace
  location. Loading the bundle and building the runtime reproduces it.

Its source was acquired by upload, so the manifest carries a `swhid` but no
origin URL. A source review of this REE therefore reports that the author
baseline has no independently acquirable origin — the honest verdict for an
upload-acquired source, and the reason a review fixture with a URL origin is
still worth adding.

It is the baseline the reviewer suite reviews
(`gui/tests/showcase/review.spec.ts`). That is what its two omissions
buy: with no runtime artifact the build step has to genuinely rebuild from the
author's recipe, and unsealed means the review runs against an ordinary REE
rather than a frozen one. Because its receipts come from a real earlier run,
they also exercise evidence the current code did not write — one of them
predates the `verify_exit_code` field, and the experiment review has to read the
author's claim out of `status` instead.
