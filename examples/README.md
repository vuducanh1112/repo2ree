# Examples

Shared example inputs. Everything here is read by more than one place — the
GUI showcase and instant suites, the system tier, the API walkthrough, and by
hand when trying the app — so it lives at the repository root rather than inside one suite.

## `projects/`

The projects the suites author REEs from. Each folder holds `source/`, an
ordinary source tree with no REE metadata or receipts that the suites pack as an
upload, and `recipe/`, the scripts that run it which the suites do not write as
script inference proposes them. Every recipe has a
`check_working_environment.sh`, stating what its scripts need of the machine they run on;
the suites run it before the build. Which scripts those are, and what each project
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

The instant project for a machine with a Docker daemon whose paths are the
machine's own. Its Dockerfile builds `FROM scratch`: the recipe's build copies the
machine's static `busybox` into the build context, so the daemon runs a real
`docker build` (with a `RUN` step) and `docker run`, pulling and downloading
nothing. Its check asks for both. It prints the same output as `instant/`.

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

A project built and run with rootless Podman, on a machine where
`ree` runs scripts directly (`podman`) and Podman is the only engine they can
use. Script inference probes that, so its build is `podman build` on the
`Containerfile`, which pins its Python base image by digest, saved as the
experiment environment, and its activation loads that image and runs each
experiment in it with `podman run`; the recipe holds only the experiment and
its verify script. Run by `just test-showcase-api 1 podman/`.

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
/api/v1/rees/{id}/load-ree-bundle`).

### `ree-hello-world.zip`

The REE the Python Docker showcase authors, authored through `ree` on the
testbed's `docker` machine (`testbed/environments/docker`), carrying its real
author evidence: the source snapshot, the overlay scripts with the project's
check of the working environment, the SBOM, the reproducibility report, the
captured experiment result, and the author receipts from that run.

It is sealed with its source and results but not its experiment environment:
that is a Docker image export of hundreds of MB, too large to version. Loading
the bundle and building the experiment environment reproduces it.

Its source was acquired by upload, so the manifest carries a `swhid` but no
origin URL. A source review of this REE therefore reports that the author
baseline has no independently acquirable origin — the honest verdict for an
upload-acquired source, and the reason a review fixture with a URL origin is
still worth adding.

It is the baseline the reviewer suites review
(`gui/tests/showcase/review.spec.ts` and the Python Docker review showcase). With
no experiment environment, the review's build has to rebuild it from the
author's recipe.
