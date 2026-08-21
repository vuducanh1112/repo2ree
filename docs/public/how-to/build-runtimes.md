# The Runtime of an REE

The runtime is the self-contained environment an REE builds so that the
repository's **experiments** can run inside it. It is the thing you package, and
the thing every other piece of evidence in the REE describes: the recipe that
produces it, the SBOM that inventories it, and the receipts that bind a result
to the environment that produced it.

This guide covers what repo2ree expects from a build, how to package software so
the build stays reproducible, which technologies fit, and the mistakes that most
often make a runtime unusable a year later.

## Three environments, and which one you are packaging

It is easy to say "the runtime" and mean three different things, so it is worth
separating them once. Building an REE involves three nested environments, and
only the innermost one is the runtime.

| | What it is | Who provides it | Does it ship? |
|---|---|---|---|
| **Workbench** | An isolated container, one per REE, where every repo2ree operation runs — acquiring source, evaluating, building, scanning, sealing. | repo2ree, from a base image; the agent injects the executor and its tools at provision time. | No. |
| **Workspace** | A directory inside that workbench (`workspace/`), materialized from the frozen source plus the REE overlay. Scripts run from its root. | repo2ree, derived from `upstream/` + `overlay/`. | Its declared contents do; the directory is derived and resettable. |
| **Runtime** | The artifact your build script produces — an image tar or equivalent — that experiments run *inside*. | **You**, via the repository's own build recipe. | Optionally. Its recipe and SBOM always do. |

The build script runs **in the workspace, not in the runtime**. It executes as a
plain subprocess from the workspace root inside the workbench, using the
workbench's tooling — notably its Docker daemon. The runtime does not exist yet
while the build script runs; producing it is the point.

Experiments are the other way around. An experiment script also starts in the
workspace, but its job is to *enter* the runtime: load the artifact, then run the
command inside it with the workspace bind-mounted, so the code and the produced
outputs live in the workspace while the environment comes from the runtime.

Three consequences follow, and they are the source of most confusing build
failures:

- **What the workbench has, the runtime does not.** `git`, `curl`, a Python
  interpreter, or the Docker CLI being available to the build script says
  nothing about the runtime. If an experiment needs a tool, the repository's
  recipe has to install it into the image.
- **Nothing you do by hand in the workbench survives.** The workbench is
  disposable and can be re-provisioned from its base image; only the REE tree
  is durable. An environment assembled by hand there is not part of the
  artifact and will not exist for anyone else. It must be in the recipe.
- **The build should touch the workspace only to write its artifact.** Other
  changes it makes are recorded as workspace drift on the build receipt, and a
  build that quietly edits source is a build nobody else can repeat.

The rest of this guide is about the third row of that table.

## What repo2ree does and does not supply

repo2ree does not invent an environment for your code. It asks you for one
script — the **runtime build script** — and everything that script needs must
already be in the source repository:

| Lives in the source repository | Lives in the REE overlay |
|---|---|
| `Dockerfile`, `environment.yml`, `flake.nix`, `apptainer.def` | `ree-scripts/build_script.sh` |
| `requirements.txt`, `poetry.lock`, `uv.lock`, `renv.lock`, `Project.toml` | `ree-scripts/activation.sh` |
| `pom.xml`, `package-lock.json`, `Cargo.lock`, `Makefile` | `ree-scripts/experiments/<slug>.sh` |

That split is deliberate. The recipe for the environment belongs to the
research project and should be reviewable, versioned, and citable with it. The
overlay only says *how to invoke* that recipe and *where to leave the result*.

If the repository has no build recipe at all, write one and commit it upstream
before authoring the REE. An REE whose environment exists only inside repo2ree
is a worse artifact than one whose environment is in the repository.

### Example

The [tutorial](../tutorials/create-your-first-ree.md) uses a small pandas
project. Everything that describes the environment is already in the source
tree, before repo2ree is involved:

```
python_hello_world/
├── Dockerfile
├── requirements.txt
└── main.py
```

`requirements.txt` declares the dependency:

```
pandas==2.2.1
```

`Dockerfile` declares the environment and how to enter it:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

The REE adds exactly one thing on top: a build script that invokes that recipe
and exports the result to the declared path.

```sh
#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
PROJECT_DIR="python_hello_world"
RUNTIME_FILE="$PROJECT_DIR/runtime.tar"

echo "Building $IMAGE_NAME:$TAG from $PROJECT_DIR..."
docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"

echo "Exporting image to $RUNTIME_FILE..."
docker save "$IMAGE_NAME:$TAG" -o "$RUNTIME_FILE"
```

Notice what the script does **not** do. It does not choose a base image, install
pandas, set a working directory, or know that the program is `main.py`. Every one
of those decisions lives in the repository, where it is versioned and reviewable
with the research code. The script only:

1. names the build context — `python_hello_world`, the project root;
2. tags the image so later scripts can refer to it;
3. exports the image to a file at the path the REE declares.

That last point is the checkable contract: `python_hello_world/runtime.tar` is
declared as the runtime artifact *before* the build runs, so a script that exits
0 without producing it fails rather than silently passing.

The example is deliberately a starting point, not a model answer. Evaluate will
report that `pandas==2.2.1` is pinned while `python:3.11-slim` is a floating tag
and the transitive dependency set is unlocked — which is exactly the gap
[Packaging rules](#packaging-rules-that-keep-a-build-reproducible) is about, and
exactly the kind of thing to fix upstream in the repository rather than in the
build script.

## The build contract

![The Build Runtime step: the declared runtime artifact path, its built status and size, and the editable build recipe below it](../tutorials/assets/create-first-ree/05-build.png)

The Build Runtime step in the app is that contract made concrete: you declare
where the build writes its runtime, author the recipe that puts it there, and
run it. A runtime build in repo2ree is defined by three things:

1. **A build script path**, workspace-relative — conventionally
   `ree-scripts/build_script.sh`.
2. **A runtime artifact path** (`runtime_path`), workspace-relative — where the
   build must leave its output as a file, e.g. `.repo2ree/artifacts/runtime.tar`
   (see [The runtime is a file](#the-runtime-is-a-file-not-a-running-thing)).
3. **A zero exit code**, plus the artifact actually existing afterwards.

Execution details you can rely on:

- the script runs as `sh <path>` **from the workspace root**, so every path in
  it is workspace-relative unless it `cd`s first;
- **no environment is injected** — no REE id, no output directory, no secrets.
  If your build needs a value, it must come from the repository or be a literal
  in the script;
- the workbench *is* the isolation boundary, so the script runs as a plain
  subprocess inside it rather than in a container of its own, with the
  workbench's Docker daemon available to it;
- the build script's bytes are digested and recorded in the definition. Editing
  the script invalidates the recorded build and requires a rebuild;
- if the script exits 0 but `runtime_path` does not exist, the build fails. A
  build that "succeeded" without producing an artifact is not a build.

The example above is a complete build script under this contract. If the
artifact path sits in a directory the repository does not already have, create it
first — `mkdir -p "$(dirname "$RUNTIME_ARTIFACT")"` before the export — since a
missing parent directory is the usual reason a `docker save` fails at the end of
an otherwise successful build.

repo2ree can propose the script for you when it finds exactly one Dockerfile at
the project root, or a `requirements.txt` project. A proposal is a starting
point that has been inferred but not executed — read it before you accept it.

## The runtime is a file, not a running thing

repo2ree does not accept "the image is on my machine" or "pull it from our
registry" as a runtime. The build script must leave a **file** at
`runtime_path`, and that file is what everything downstream reads: the digest on
the receipt, the SBOM scan, the activation script that loads it back, and — if
you choose to include it — the sealed bundle.

That means every packaging technology needs an export step at the end of the
build:

| Technology | Export step | Artifact |
|---|---|---|
| Docker | `docker save "$IMAGE_TAG" --output runtime.tar` | image tar |
| Podman | `podman save --format docker-archive "$IMAGE_TAG" -o runtime.tar` | image tar |
| Buildah | `buildah push "$IMAGE" docker-archive:runtime.tar` | image tar |
| `docker buildx` | `--output type=docker,dest=runtime.tar` (build and export in one pass) | image tar |
| A remote image you did not build | `skopeo copy docker://ghcr.io/org/img@sha256:… docker-archive:runtime.tar` | image tar |
| Apptainer / Singularity | `apptainer build runtime.sif recipe.def` | `.sif` file |
| Nix | `nix build .#dockerImage` (`dockerTools.buildLayeredImage`), then copy the result | image tar |
| Conda | `conda-pack -n env -o runtime.tar.gz` | packed env |
| Python venv | `tar czf runtime-venv.tar.gz -C /opt venv` | packed venv |
| Plain rootfs / chroot | `tar czf runtime.tar.gz -C rootfs .` | filesystem tar |

Worked recipes for Docker, Podman, Apptainer, and Nix are
[below](#recipes-by-technology). Prefer the Docker image tar unless something
forces you elsewhere: the SBOM scanner reads it, a reviewer's rebuild can
compare against it by digest, and the bundle's `run.sh` knows how to load it on
a stranger's machine.

## What ships, and what the artifact adds

The runtime artifact does **not** have to travel inside the sealed REE, and
often it should not. What always travels is everything needed to build it again
and to check that the result is the same environment:

- the **build recipe** — the repository's `Dockerfile` or equivalent in the
  frozen source snapshot, plus the build script in the overlay;
- the **SBOM** — the inventory of what the runtime actually contained, so a
  future rebuild has something to be compared against;
- the **receipts** — the build script's digest, the artifact's digest, and the
  runs that used it.

That combination is the certificate. Someone rebuilding in three years does not
have to trust a claim that the environment was right: they rebuild from the
recipe, scan their own result, and reconcile it against the recorded SBOM and
digests. Where the environment has drifted, the reconciliation names the package
that moved instead of leaving them to guess.

**Packaging the artifact turns "should rebuild" into "runs as-is".** Because the
build produces a file rather than a daemon-resident image, the REE *can* carry
that file beside the source snapshot and the receipts — the difference between
the Cite and Replay archive tiers. What that buys:

- **No third-party service on the critical path.** A registry reference is a
  promise by someone else to keep hosting something. Registries delete untouched
  tags, change retention policy, rename organizations, rate-limit anonymous
  pulls, and go away. A bundled tar depends on nobody.
- **No rebuild risk at all.** A recipe can stop building — a base image
  disappears, an index drops an old version, a build tool changes behaviour. A
  bundled artifact still runs.
- **Offline inspection.** Anyone auditing the environment later reads the file
  directly: no daemon, no network, no credentials.
- **Deposit-friendliness.** Software Heritage, Zenodo, and Dataverse take
  deposits, not registry coordinates. What sits in the bundle is what survives.

The cost is size. A multi-gigabyte image makes every later step — scan, seal,
download, deposit — slower, and may exceed what an archive accepts. Treat it as
a judgement call: seal the artifact when the runtime is small enough or the
result matters enough to guarantee, and rely on the recipe and SBOM when it is
not. Either way, produce the file — the SBOM and the digest evidence depend on
it existing, whether or not it ends up in the bundle.

## Choosing a packaging technology

Anything that can be exported to a file is a candidate. The practical choices,
in order of how well they are supported today:

**Docker image, exported with `docker save`.** The default and the best
supported. The SBOM step scans `docker-archive:` tarballs and nothing else, the
sealed bundle's `run.sh` expects one on a recipient's machine, and image digests
give the reviewer an exact-match comparison before falling back to SBOM closure.
Choose this unless you have a reason not to.

**A packed Python virtualenv** (`.tar.gz` of a venv). The docker-less path for
plain `requirements.txt` projects: the build packs a venv and every runnable
restores it instead of loading an image. Cheap and fast, but note what it means
for the separation above — the workbench base image ends up *being* the
environment, so the interpreter and system libraries are inherited rather than
pinned, and there is no container to scan for an SBOM. Build the venv *outside*
the workspace and pack only the tarball into it — the workspace is
snapshot-hashed on every change, and a venv bakes absolute paths, so it must be
restored where it was built.

**Podman.** A drop-in alternative that reads the same recipe file and exports
the same archive format, so nothing downstream can tell the difference.

**Nix, Guix, Conda / mamba, Spack.** Best used to *produce* an image tar — Nix's
`dockerTools`, a conda environment inside a Dockerfile — so you keep the
evidence chain while gaining the stronger pinning. Nix and Guix give by far the
strongest reproducibility story; Conda gives the weakest unless you commit a
fully solved lock file (`conda-lock`), because `environment.yml` re-solves
differently on every machine and date.

**Apptainer / Singularity.** A `.sif` is a legitimate runtime artifact and the
right answer for HPC, but it costs you the SBOM scan and requires Apptainer on
every recipient's machine. See the recipe below before committing to it.

**Not runtimes:** a `setup.sh` that installs into the host, a README that says
"install PyTorch", or an environment that exists only on your cluster.

### Recipes by technology

Each pair below shows the same split as the example above: the recipe file that
belongs in the **source repository**, and the build script the **REE** adds to
invoke it and export the result.

One constraint applies to all of them. The build script can only use tools the
workbench actually has, and the stock workbench is Docker-based — see
[Three environments](#three-environments-and-which-one-you-are-packaging). A
non-Docker toolchain is therefore usually invoked *through* a container, which
is what the Apptainer and Nix examples below do. If your deployment provides a
workbench image that already carries the tool, call it directly instead.

#### Docker

In the repository — `Dockerfile`:

```dockerfile
FROM python:3.11-slim@sha256:1234…
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
CMD ["python", "main.py"]
```

In the REE — `ree-scripts/build_script.sh`:

```sh
#!/usr/bin/env sh
set -eu

PROJECT_DIR="myproject"
IMAGE_TAG="ree-runtime:my-paper"
RUNTIME_ARTIFACT="$PROJECT_DIR/runtime.tar"

docker build --platform linux/amd64 --tag "$IMAGE_TAG" "$PROJECT_DIR"
docker save "$IMAGE_TAG" --output "$RUNTIME_ARTIFACT"
```

Declare `myproject/runtime.tar` as the runtime artifact. This is the path with
the fewest surprises: the SBOM step scans it directly and the bundle's `run.sh`
loads it on any Docker host.

#### Podman

Podman reads the same file, conventionally named `Containerfile` (a `Dockerfile`
works unchanged). In the repository — `Containerfile`:

```dockerfile
FROM docker.io/library/python:3.11-slim@sha256:1234…
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
CMD ["python", "main.py"]
```

In the REE — `ree-scripts/build_script.sh`:

```sh
#!/usr/bin/env sh
set -eu

PROJECT_DIR="myproject"
IMAGE_TAG="ree-runtime:my-paper"
RUNTIME_ARTIFACT="$PROJECT_DIR/runtime.tar"

podman build --platform linux/amd64 --tag "$IMAGE_TAG" "$PROJECT_DIR"

# --format docker-archive matters: podman's default export is an OCI archive,
# which the SBOM scanner and `docker load` do not read.
podman save --format docker-archive --output "$RUNTIME_ARTIFACT" "$IMAGE_TAG"
```

The exported tar is interchangeable with the one Docker produces, so
everything downstream —
SBOM, activation, `run.sh` on a recipient's machine — behaves identically. Note
that Podman resolves bare image names against its own registry list, so spell
base images fully (`docker.io/library/…`).

#### Apptainer (Singularity)

The HPC-facing option: a single `.sif` file, no daemon, and it runs unprivileged
on clusters that will not give you Docker.

In the repository — `apptainer.def`:

```
Bootstrap: docker
From: python:3.11-slim@sha256:1234…

%files
    requirements.lock /opt/requirements.lock
    main.py /opt/app/main.py

%post
    pip install --no-cache-dir --require-hashes -r /opt/requirements.lock

%runscript
    exec python /opt/app/main.py "$@"
```

In the REE — `ree-scripts/build_script.sh`:

```sh
#!/usr/bin/env sh
set -eu

PROJECT_DIR="myproject"
RUNTIME_ARTIFACT="$PROJECT_DIR/runtime.sif"
APPTAINER_IMAGE="quay.io/apptainer/apptainer:1.3.6"

# Apptainer is not in the stock workbench, so run it from a container. It needs
# --privileged to build, which the workbench's own daemon provides.
docker run --rm --privileged \
    -v "$(pwd)/$PROJECT_DIR:/work" -w /work \
    "$APPTAINER_IMAGE" \
    build --force runtime.sif apptainer.def
```

Two consequences to accept before choosing this: the SBOM step cannot scan a
`.sif` (it reads `docker-archive` tarballs), so the runtime inventory has to
come from elsewhere, and every recipient — including `run.sh` from the sealed
bundle — needs Apptainer installed. The activation and experiment scripts change
shape accordingly, running `apptainer exec runtime.sif …` instead of a
`docker load` / `docker run` pair.

If you want the SIF *and* the evidence, build a Docker image as the runtime
artifact and generate the SIF from it as a separate convenience output.

#### Nix

The strongest reproducibility story of the four: the flake lock pins the entire
dependency closure, down to the C libraries, by hash.

In the repository — `flake.nix` (with its `flake.lock` committed beside it):

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python311.withPackages (ps: [ ps.pandas ]);
    in {
      packages.${system}.runtimeImage = pkgs.dockerTools.buildLayeredImage {
        name = "ree-runtime";
        tag = "latest";
        contents = [ python pkgs.bashInteractive pkgs.coreutils ];
        config = {
          WorkingDir = "/app";
          Cmd = [ "${python}/bin/python" "/app/main.py" ];
        };
      };
    };
}
```

In the REE — `ree-scripts/build_script.sh`:

```sh
#!/usr/bin/env sh
set -eu

PROJECT_DIR="myproject"
RUNTIME_ARTIFACT="$PROJECT_DIR/runtime.tar.gz"
NIX_IMAGE="docker.io/nixos/nix:2.24.9"

# Nix is not in the stock workbench either. The container writes `result` as a
# symlink into its own store, so dereference it on the way out with `cp -L`.
docker run --rm \
    -v "$(pwd)/$PROJECT_DIR:/work" -w /work \
    "$NIX_IMAGE" \
    sh -c 'nix --extra-experimental-features "nix-command flakes" \
             build .#runtimeImage && cp -L result /work/runtime.tar.gz'

test -f "$RUNTIME_ARTIFACT"
```

`dockerTools.buildLayeredImage` emits a gzip-compressed Docker image tarball, so declare
`myproject/runtime.tar.gz` as the runtime artifact and everything downstream
works as it does for Docker — the SBOM scanner accepts `.tar.gz`.

Two things make this worth the extra machinery: the build is pinned by
`flake.lock` rather than by whatever the package index served that day, and the
images are timestamp-free by construction, so a rebuild is far more likely to
match by digest instead of falling back to an SBOM comparison.

## Packaging rules that keep a build reproducible

These are the rules that decide whether the artifact still builds in three
years.

**Pin the base image by digest, never by a moving tag.** `FROM python:3.11`
means a different environment every month; `FROM python:3.11-slim@sha256:…`
means one environment forever. Keep the tag beside the digest as a comment for
humans — the digest is what binds.

**Pin dependencies with a lock file, and copy the lock file, not the loose
list.** `pip install -r requirements.txt` with unpinned ranges, `npm install`
without `package-lock.json`, or `cargo install` without `Cargo.lock` all resolve
against the index at build time. Use `pip install -r requirements.lock`
(from `pip-compile`/`uv pip compile`), `npm ci`, `poetry install --no-root`,
`renv::restore()`, `--frozen-lockfile`.

**Pin system packages too, or accept that you have not.** `apt-get install -y
libgdal-dev` is a floating dependency exactly like an unpinned Python package.
Pin versions (`libgdal-dev=3.6.2+dfsg-1+b2`) where the distribution archive
makes it possible, and prefer a distribution whose archive is preserved
(Debian's snapshot.debian.org) when it matters.

**Fetch nothing at run time.** Every download that happens when the experiment
runs — model weights, reference data, a `git clone`, a `pip install` in an
entrypoint — is a future failure and an unrecorded dependency. Fetch during the
build, verify a checksum, and bake it in. If the data is too large to bake in,
declare it as an input and document its retrieval separately; do not hide it in
a run command.

**Build for a named platform.** An image built on an Apple-silicon laptop is
`linux/arm64` and will not run on an `linux/amd64` reviewer machine without
emulation. Pass `--platform linux/amd64` explicitly, and say so, rather than
letting the host decide.

**Keep results out of the image.** The runtime is the environment; outputs
belong in the workspace, which is bind-mounted into the container when
experiments run. An image that carries its own results makes the reviewer's
fresh run indistinguishable from your old one.

**Keep the image lean, but not at the cost of the environment.** The runtime
artifact is stored, digested, transferred, scanned, and archived. Multi-stage
builds and `--no-cache-dir` help. Deleting the compiler your code needs to
rebuild an extension does not.

**No secrets, ever.** Tokens and keys baked into a layer survive `rm` in a later
layer and ship inside a public archive. If the build genuinely needs a
credential, the artifact is not archivable in that form — restructure it.

**Make the entrypoint boring.** Prefer an image that runs a plain command over
one with a clever entrypoint wrapper. The activation and experiment scripts
supply the command explicitly, and an entrypoint that rewrites arguments makes
that indirection invisible to the reviewer.

## Pitfalls that bite in practice

- **A green build cache.** `docker build` reusing cached layers can hide a
  dependency that no longer resolves. Before sealing, rebuild once with
  `--no-cache` and confirm it still passes.
- **Non-determinism you did not ask for.** Timestamps, unsorted `COPY` globs,
  and `pip`'s wheel cache make image digests differ between two builds of the
  same source. This is normal — repo2ree falls back to comparing SBOM closure
  when digests differ — but a byte-identical rebuild is stronger evidence, and
  `SOURCE_DATE_EPOCH` plus reproducible-builds flags gets you closer.
- **Root-owned outputs.** A container running as root writes root-owned files
  into the mounted workspace. Either run as a matching non-root user or expect
  files you cannot clean up from the host.
- **The workspace mount shadows baked-in source.** If the Dockerfile `COPY`s
  the project to the same path the workspace is mounted at, the mount wins at
  run time. Bake the *environment*, mount the *code*.
- **GPU and driver assumptions.** A CUDA image binds to a host driver range,
  so an artifact that runs on your cluster may not run anywhere else. Record the
  hardware context (HBOM) and state the requirement plainly rather than letting
  a reviewer discover it.
- **A build that only works with your network.** Private registries, VPN-only
  package mirrors, and institutional proxies all produce a build that no
  reviewer can repeat.
- **An artifact path outside the workspace.** The build must leave its output at
  the declared workspace-relative path; scripts that resolve outside the
  workspace are rejected.
- **A giant runtime artifact.** A multi-gigabyte image tar makes every later
  step — SBOM scan, seal, download, deposit — slow, and may force the choice of
  sealing without the runtime. Check the size before you commit to the
  packaging.

## The evidence repo2ree builds around the runtime

The build is one step in an evidence chain, and the steps around it are what
turn "it built" into something a reviewer can act on.

### Before the build: declared dependencies

The **Evaluate** step reads the repository as it stands and inventories what it
*declares*. It parses the manifests and lock files it finds — PyPI
(`requirements.txt`, `pyproject.toml`, `poetry.lock`, `uv.lock`), Conda
(`environment.yml`), npm (`package.json`, `package-lock.json`), OS packages, and
the base images named in Dockerfiles — and classifies every row by how firmly it
is bound: **locked** (a lock file resolved it), **pinned**, **ranged**,
**unpinned**.

This is a source-level assessment, produced before anything is built. It is
where floating tags and unpinned ranges show up as findings, and it is the
cheapest place to fix them: the rules in [Packaging rules](#packaging-rules-that-keep-a-build-reproducible)
are, more or less, the list of things that move a row up that ladder.

### After the build: the SBOM

Once the runtime artifact exists, the **SBOM** step scans it and records what is
*actually inside* it. The scan reads the artifact as a `docker-archive:` tarball
with `--scope squashed` — the squashed filesystem, not just the top layer — and
writes a CycloneDX document that is digested and committed to the REE as
evidence.

That document is the certifiable inventory of the environment: the package list
a reviewer, a security audit, or an archive can read without ever running the
image. It also becomes the basis for the reviewer's comparison, since a rebuild
whose image digest differs can still be checked against the author's SBOM
closure.

If the scan produces nothing, check that `runtime_path` ends in `.tar`,
`.tar.gz`, or `.tgz` and holds a `docker save` archive — this is the concrete
reason the Docker image tar is the recommended packaging form.

### Cross-check: declared versus observed

The **cross-check** step joins the two inventories: what the repository declared
(Evaluate) against what the runtime contains (SBOM). Each declared dependency
gets a verdict:

| Verdict | Meaning |
|---|---|
| `observed` | Declared, and present in the runtime at the declared version. |
| `version-mismatch` | Declared, present, but at a different version — the loud one. |
| `not-observed` | Declared but absent. Normal for dev- and build-only dependencies; not a defect by itself. |
| `undeclared` | Present in the runtime with no manifest declaring it. |

Undeclared packages are only reported for ecosystems the repository actually
uses: an unexpected PyPI package is a real signal, while the base image's
hundreds of OS packages are noise and are counted rather than listed.

The cross-check is where the two halves of the guide meet. A `version-mismatch`
usually means a dependency was declared as a range and resolved to something
else at build time. A pile of undeclared same-ecosystem packages usually means
something was installed inside the Dockerfile that never made it into a
manifest. Both are fixable in the source repository, and both are much cheaper
to fix now than to explain later.

## Optional: test activation

Activation answers the smallest question that follows a green build: **does the
artifact actually start?** A build proves that a tar appeared at the declared
path. Activation proves that loading that tar yields something you can run a
command inside.

Mechanically it is an experiment without a scientific claim. It uses the same
two-script shape, the same reserved-overlay convention, and the same execution
rules — a run script at `ree-scripts/activation.sh` and an optional verify
script at `ree-scripts/activation.verify.sh`, both executed from the workspace
root with nothing injected, the exit code deciding the outcome:

```sh
#!/usr/bin/env sh
set -eu

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime.tar"
IMAGE_TAG="ree-runtime:latest"

# Loading from the saved artifact — not the locally built image — proves the
# artifact itself is self-contained.
docker load --input "$RUNTIME_ARTIFACT"

# Replace the trailing command with one that shows the runtime works.
docker run --rm -v "$(pwd):/workspace" -w /workspace "$IMAGE_TAG" \
  python --version
```

The differences from an experiment are all about scope. An REE has exactly one
activation rather than a named catalog; it declares no output files, so nothing
is captured or sealed from it; and a reviewer's activation records a plain
probe outcome instead of a comparison against your baseline, because the probe
*is* the whole claim.

**Keep the command finite and cheap.** `python --version`, `Rscript -e
'sessionInfo()'`, `julia --version` — something that starts, prints, and exits.
Activation is not a rehearsal of the experiment, and a long-running command here
buys nothing.

**Prefer a command that touches the dependency you care about.** An interpreter
version proves the image starts; `python -c "import pandas; print(pandas.__version__)"`
proves the environment is the one you meant to build. That extra assertion is
where activation earns its keep, because it separates "the image runs" from "the
image has what the experiment needs".

repo2ree can generate the activation script from the built runtime — it reads
the saved image and derives the load-and-run plumbing — but the scaffold is
fail-closed: it ships with an empty `set --` and exits **64** until you supply
the command. Nothing guesses what proves your runtime usable.

Activation is genuinely optional. Sealing does not demand it, and an REE without
it is incomplete rather than self-contradictory, which its own audit reports
plainly. It is still worth the two minutes: it is the cheapest failure in the
whole pipeline to catch, and a reviewer reproducing your REE hits it before any
experiment runs.

## Next

The runtime is the environment; the experiments are what you run inside it, and
where the reproducibility claim actually lives. Continue with
[Experiments in an REE](experiments.md) — the run script that enters this
runtime, the verify script whose exit code is the verdict, and the outputs a
reviewer compares against yours.
