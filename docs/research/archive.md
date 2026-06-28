# repo2ree - Archive and Dependency Preservation

> **Status: proposed / feature-space.** This document separates two ideas that
> are easy to blur: archiving the REE as a citable research object, and
> archiving the dependency closure that makes the REE re-derivable after
> upstream package ecosystems drift or disappear.

Archiving the REE itself is mostly deposit work: compose the bundle and send it
to Zenodo, Dataverse, or an institutional repository. Dependency preservation is
harder. A deposited REE can be citable and still fail to rebuild once package
indexes, container tags, Git URLs, wheels, tarballs, or system packages
disappear.

```text
Can repo2ree capture enough of the dependency universe to rebuild the REE
without trusting today's upstream package services?
```

That is the difference between a durable citation and a durable computation.

## The core distinction

### Archiving the REE

Archiving the REE is a deposit workflow. It produces a durable, citable record
of the reproducibility object:

| REE component | Typical archive treatment |
|---|---|
| Source | Pointer to Software Heritage when available, or source bytes for draft snapshots |
| Declaration and overlay | Inline in the deposited bundle |
| Repro Label | Inline snapshot of reproducibility observations |
| Run Receipts | Inline receipts, outputs, comparison rules, and provenance |
| Runtime image | Included for Replay-tier deposits |
| Dependency closure | Included only for Rebuild-tier deposits |
| Seal Manifest | Inline; records the `ree_digest` over the chosen contents |
| Signatures | Inline or sibling attestations over `ree_digest` |
| Identifiers | DOI / PID from Zenodo, Dataverse, DataCite, PID4NFDI, or institutional services |

repo2ree prepares the bundle; archival repositories preserve it.

### Sealing before deposit

Archive should consume a sealed REE, not a mutable workspace. Sealing creates a
canonical Seal Manifest and computes:

```text
ree_digest = sha256(canonical_seal_manifest)
```

That digest binds the selected archive tier: Cite seals declaration, overlay,
source pointer, Label, and Receipts; Replay also seals the runtime image digest;
Rebuild also seals the dependency-closure digest.

Signing is separate. A signature is a typed claim over `ree_digest`: author
approval, executor attestation, reviewer verification, institution acceptance,
or archive binding. Signatures are not included in the digest they sign, so they
can be added after deposit as sibling attestations or new archive versions.

For long-term validation, preserve the signature envelope, public key or
certificate chain, timestamp evidence, verification policy, revocation evidence
when available, and digest algorithm identifiers. See [sealing.md](sealing.md).

### Archiving dependencies

Archiving dependencies is a reproducibility workflow. It asks whether the REE
can be rebuilt from a captured closure rather than from live upstream services.

This is not solved by a DOI. A DOI can identify a zip file containing a
Dockerfile, lockfile, and receipts, but it does not guarantee that:

- `ubuntu:22.04` still resolves to the same base layers.
- `pip install -r requirements.txt` can still fetch the same wheels or sdists.
- An `apt` repository still exposes the same package index.
- A transitive dependency has not been yanked, republished, or hidden behind a
  changed resolver.
- A build script does not download a model, binary, tarball, Git submodule, or
  installer from an untracked URL.
- A private or restricted package can legally be redistributed.

The dependency archive is the per-REE closure that answers those questions as
far as possible.

## Why dependencies are harder

Archives preserve blobs and identifiers. They do not know why a wheel, `.deb`,
OCI layer, or npm tarball was needed, which resolver selected it, or whether a
future rebuild used it. repo2ree can add that missing semantic layer:

```text
declared -> resolved -> fetched -> content-addressed -> replayed offline
```

A Rebuild-tier REE should pass an offline rebuild against its captured closure.

## Archive tiers revisited

The existing tiers still hold, but dependency preservation makes their
differences sharper:

| Tier | What survives | What still depends on live upstreams |
|---|---|---|
| Cite | The declaration, source pointer, Label, and Receipts | Rebuild and often rerun |
| Replay | The built runtime image and receipts | Re-deriving the runtime from source |
| Rebuild | Runtime image plus captured source/input/dependency closure | Only excluded data, hardware, and policy-bound resources |

Replay preserves runnability. Rebuild preserves re-derivability.

## The dependency archive object

A Rebuild-tier bundle needs a first-class dependency archive, not an unstructured
`vendor/` directory. A useful object should contain five layers:

| Layer | Purpose | Examples |
|---|---|---|
| Declarations | What the repository said it needed | `pyproject.toml`, `uv.lock`, `requirements.txt`, `package-lock.json`, `environment.yml`, `Dockerfile`, `apt` package lists |
| Resolution metadata | What the ecosystem resolver selected | package name, version, index URL, platform tag, solver inputs, registry metadata snapshot |
| Fetched blobs | The actual bytes required by the build | wheels, sdists, npm tarballs, conda packages, `.deb` files, OCI layers, Git archives, model files |
| Provenance | Where each blob came from and how it was validated | original URL, digest, fetch time, redirects, declared checksum, license signal, access mode |
| Replay map | How future rebuilds consume the captured closure | local package index, OCI layout, apt repo snapshot, pip/uv cache, rewrite rules |

The archive should be content-addressed internally. Every captured blob gets a
digest; manifests point at digests rather than paths. That lets repo2ree dedupe
large closures, verify the archive after deposit, and prove that a rebuild used
the captured bytes.

## Vanished package indexes

The most concrete dependency-archive use case is an old package disappearing
from a large package index such as PyPI. The failure usually looks simple:

```text
pip install old-package==1.2.3
# no matching distribution found
```

But there are several different things that may have vanished:

| Missing thing | Why it matters |
|---|---|
| Index metadata | The resolver no longer knows which files belonged to the release. |
| Wheel | The installable artifact for a specific Python, ABI, OS, and architecture is gone. |
| Source distribution | The package source as published to PyPI is gone. |
| Project source repository | The upstream VCS URL is gone, moved, or no longer has the release tag. |
| Build dependencies | The tools needed to build the package from source have also drifted. |
| System toolchain | Compilers, headers, CUDA, BLAS, Rust, Fortran, or OS packages are no longer equivalent. |

Software Heritage helps with one layer: preserving source code. That is
important, but it does not by itself restore a package. A future installer needs
an installable distribution, or it needs a reproducible way to rebuild that
distribution from source.

For Python, the practical ladder is:

| Fallback level | What repo2ree uses | What repo2ree must record |
|---|---|---|
| 1. Exact wheel | Captured wheel from PyPI or another index | filename, package metadata, tags, URL, digest |
| 2. Exact sdist | Captured source distribution | sdist digest, build backend, build requirements, produced wheel digest |
| 3. Source archive | SWHID or captured VCS archive for the release | mapping from package version to source revision, build recipe, produced wheel digest |
| 4. Source plus patch | Archived source plus compatibility patch | patch provenance, reason, changed output contract |
| 5. Not rebuildable | Metadata only | explicit Label finding and missing requirement |

Default first defense: capture the exact wheel or sdist while the package index
is alive. SWH is the fallback for source, not a replacement for package
distribution capture.

### Source-to-package receipts

When repo2ree must rebuild a vanished package from source, the output should be
a first-class receipt, not an invisible repair step:

```text
package: old-package
version: 1.2.3
source: swh:1:rev:...
build_env: sha256:...
build_command: python -m build --wheel
build_dependencies:
  - setuptools==...
  - wheel==...
  - cython==...
system_dependencies:
  - gcc...
  - libopenblas-dev...
output_wheel: sha256:...
target_tags:
  - cp310-cp310-manylinux_2_28_x86_64
```

That receipt lets a future verifier distinguish three claims:

- The original package artifact was preserved exactly.
- The package source was preserved and repo2ree rebuilt a wheel under an
  explicit equivalence contract.
- The source is present, but the package is not currently rebuildable.

Source fallback can change semantics: wheels may include compiled extensions,
generated C, vendored assets, or build-time feature detection. The honest claim
is "rebuilt under this receipt," not "the PyPI artifact came back."

### Local package service during rebuild

During offline rebuild, package managers should see familiar local services:

| Ecosystem | Local replay service |
|---|---|
| Python | PEP 503-style simple index or wheelhouse |
| npm | local registry/cache |
| apt | local apt repository snapshot |
| conda | local conda channel |
| OCI | local registry or OCI layout |

For PyPI, `pip` or `uv` points at a local index containing preserved or rebuilt
wheels. The manifest records which is which.

## Closure capture strategies

There are two complementary ways to capture dependencies.

### 1. Substrate-native capture

Each ecosystem gets an adapter that understands its native lockfiles,
resolvers, caches, and offline-install story.

| Substrate | Capture approach | Offline replay shape |
|---|---|---|
| Python / pip / uv | Export locked requirements with hashes; download wheels and sdists; preserve SWH source fallback where available | local wheelhouse, uv cache, or simple index |
| Conda / mamba | Capture explicit package specs and packages | local conda channel |
| npm / pnpm / yarn | Capture lockfile and tarballs | local registry/cache |
| apt / Debian | Capture package indexes and `.deb` files | local apt repo snapshot |
| OCI / Docker | Save base image layers and resolved digests | OCI layout or local registry |
| Git dependencies | Capture commit archives or SWHIDs | local archive plus source pointer |
| Direct URLs | Capture content with declared or observed checksum | CAS fetch rewrite |

This path is incremental and aligns with the Repro Label.

### 2. Recording network capture

All outbound build traffic passes through a recording proxy that stores each
fetched response by content digest and records the request metadata.

This catches ad hoc downloads that adapters miss, but adds TLS interception,
custom CAs, secret redaction, cache policy, and legal review.

The likely path is hybrid:

```text
v1: substrate-native capture for the ecosystems the Label already understands
v2: optional recording proxy to catch unknown fetches and direct URLs
```

Use the proxy as a detector first: "14 unclassified URLs during build" is
already useful.

### 3. Nix as a unifying backend

Nix is tempting because it already has closures, a content-addressed store, and
binary substitution. If a repo ships a good flake or derivation, repo2ree can
treat the Nix closure as the dependency archive:

```text
flake.lock + derivations + store paths + narinfo/NAR closure
```

Replay shape: restore the store closure, disable upstream fetches, build or
substitute exact inputs.

But Nix does not erase ecosystem semantics. Translating `pyproject.toml`,
`package-lock.json`, `environment.yml`, or Dockerfiles still requires the
original resolver, artifacts, native extensions, scripts, platform tags, and
index metadata.

The implementation stance should be:

| Case | Nix role | repo2ree behavior |
|---|---|---|
| Repo already has a flake/derivation | Primary capture backend | archive the Nix closure and score highly if offline rebuild passes |
| Repo has lockfiles Nix can import faithfully | Optional normalization backend | generate/record the translation and compare against native build outputs |
| Repo has Docker/conda/pip/npm only | Not a shortcut | use ecosystem adapters first; Nix may be a later export target |
| Repo uses ad hoc network fetches | Detector, not solution | the fetches still need capture, checksums, or exclusion |

Nix is a powerful substrate, not a universal dependency archive. Keep the
product adapter-based: Python, apt, OCI, Nix, direct URL.

## Offline rebuild as the acceptance test

A dependency archive is credible only if repo2ree can rebuild against it with
upstream network access disabled.

The Rebuild-tier acceptance test should be:

1. Build the runtime once with normal access while capturing the closure.
2. Build it again in a sandbox where package ecosystems and arbitrary outbound
   network are unavailable.
3. Serve only the captured dependency archive through local indexes, local OCI
   registries, local caches, or CAS rewrite rules.
4. Compare the rebuilt runtime against the original by digest when possible, or
   by declared runtime equivalence when bit identity is not expected.
5. Record the result in the Repro Label and archive metadata.

This makes Rebuild falsifiable: rebuilt from this closure, under these
constraints, with this result.

## New Label axes

Dependency archiving should surface as Label axes, not as a hidden export
option. Useful axes:

| Axis | Question |
|---|---|
| Declaration strength | Are dependencies declared in structured files, with versions and hashes? |
| Resolution stability | Can the selected transitive dependencies be reconstructed from lockfiles and metadata? |
| Fetch observability | Did the build perform network fetches outside known package managers? |
| Closure capturability | Can repo2ree collect the required blobs and metadata? |
| Offline rebuild | Does the REE rebuild with upstream network disabled? |
| Redistribution risk | Are captured dependencies redistributable, restricted, private, or unknown? |
| Architecture specificity | Is the closure tied to OS, CPU, GPU, libc, CUDA, or driver versions? |

These axes let a user see why one REE is merely citable while another is
dead-internet-tolerant.

## New REE workflow

Given source for a new REE, dependency archiving should produce both artifacts
and a score:

```text
source repo
  -> dependency inventory
  -> reproducibility pre-score
  -> online capture build
  -> dependency closure
  -> local replay services
  -> offline rebuild
  -> final Label + archive tier
```

### 1. Establish source identity

First record the source root:

| Check | Evidence |
|---|---|
| Commit identity | Git commit, dirty-tree status, submodule state |
| Archive identity | SWHID when available, or SWH archival request status |
| Overlay identity | Generated Dockerfile, scripts, runtime declaration, experiment commands |
| Build entrypoint | The command that turns source + overlay into a runtime image |

If the source is a dirty tree or moving branch, the dependency archive may still
help, but the REE is not archive-grade.

### 2. Inventory dependency surfaces

Static inventory finds dependency systems and hidden fetch surfaces.

| Surface | Examples | First scoring signal |
|---|---|---|
| Python | `pyproject.toml`, `uv.lock`, `poetry.lock`, `requirements.txt` | lockfile and hash strength |
| OS packages | `apt-get install`, `apk add`, `yum install` in Dockerfiles/scripts | pinned repository and package versions |
| OCI images | `FROM python:3.11`, `FROM ubuntu@sha256:...` | digest pinning |
| Node | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` | lockfile completeness |
| Conda | `environment.yml`, explicit spec files | explicit builds and channels |
| Git dependencies | submodules, `git+https`, build scripts cloning repos | commit pinning and SWH coverage |
| Direct downloads | `curl`, `wget`, model downloads, installers | declared checksum |
| Private sources | internal registries, authenticated URLs | publication and escrow risk |

This produces the first Label draft; it does not prove capturability.

### 3. Produce a pre-capture score

Before building, show a preliminary score:

| Axis | Strong signal | Weak signal |
|---|---|---|
| Source stability | commit + SWHID | branch, local snapshot, dirty tree |
| Declaration strength | lockfiles with hashes | free-form install scripts |
| Version pinning | exact versions and image digests | ranges, tags, latest |
| Fetch predictability | known package managers | arbitrary network during build |
| Policy clarity | redistributable public deps | private or unclear deps |

This lets authors fix cheap problems before capture: pin images, commit
lockfiles, add hashes, replace `latest`, declare URL digests.

### 4. Run the online capture build

The first build runs with upstream access, under observation.

For Python, the capture step should:

1. Read the declared dependency files and lockfiles.
2. Resolve environment markers for the target Python, OS, CPU, and ABI.
3. Download selected wheels and sdists into the workbench CAS.
4. Record index metadata, filenames, hashes, `Requires-Python`, yanked status
   when visible, and package metadata.
5. Record SWHIDs or source archive candidates for each package where possible.
6. If a wheel is unavailable but an sdist or SWH source is available, attempt a
   source-to-wheel build and write a package-build receipt.

For every ecosystem: capture installable artifacts first, source fallback
second, replay instructions always.

### 5. Build the dependency closure

After the online build, write a closure manifest:

```text
dependency-archive/
+-- closure-manifest.json
+-- blobs/               # content-addressed package artifacts and source archives
+-- indexes/             # simple index, apt repo, conda channel, OCI layout, etc.
+-- receipts/            # source-to-package build receipts
+-- observed-network.json
+-- exclusions.json      # private, restricted, failed, or policy-skipped deps
```

The closure manifest binds every dependency to its role:

| Role | Meaning |
|---|---|
| `exact-artifact` | The installable artifact used by the successful build was captured. |
| `source-fallback` | Source was captured, but package artifact reconstruction is required. |
| `rebuilt-artifact` | repo2ree rebuilt an installable artifact and recorded the receipt. |
| `external-required` | The dependency cannot be archived and must be supplied later. |
| `unclassified-fetch` | The build fetched something repo2ree could not classify. |

### 6. Generate local replay services

repo2ree turns the closure into services that normal tooling can use:

| Ecosystem | Replay interface |
|---|---|
| Python | local simple index plus wheelhouse |
| apt | local repository with captured indexes and `.deb` files |
| OCI | local registry or OCI layout with digest-pinned images |
| npm | local registry/cache |
| conda | local channel |
| Direct URL | CAS rewrite or local file URL with digest check |

Package managers should see normal local indexes, not RO-Crate internals.

### 7. Run the offline rebuild

The acceptance test is a second build with upstream network disabled:

1. Create a clean workbench.
2. Restore source, overlay, and dependency archive.
3. Start local replay services.
4. Block arbitrary outbound network.
5. Run the same build entrypoint.
6. Compare the runtime image digest, SBOM, installed package list, and selected
   smoke-run outputs.
7. Record every deviation.

Pass means the closure was exercised. Failures become Label evidence.

### 8. Score the final Label

Score dependency preservation by evidence, not one opaque grade.

| Axis | High score | Medium score | Low score |
|---|---|---|---|
| Source identity | SWHID + clean commit | commit only | dirty tree or branch snapshot |
| Declaration strength | complete lockfiles with hashes | pinned manifests without full hashes | loose ranges or scripts only |
| Artifact capture | all installable artifacts captured | source fallback or rebuilt artifacts needed | missing artifacts |
| Resolver replay | local indexes reproduce selected versions | manual rewrite required | live index required |
| Network closure | no unclassified fetches | known exclusions | unknown or uncontrolled fetches |
| Offline rebuild | clean pass | pass with declared exclusions or equivalence drift | fail |
| Policy readiness | redistributable closure | some author approvals needed | private/restricted blockers |

The archive tier follows from the evidence:

| Result | Meaning | Suggested tier |
|---|---|---|
| Offline rebuild passes from captured closure | Runtime can be re-derived without live upstreams | Rebuild |
| Runtime image exists, closure incomplete | Runtime can be rerun but not re-derived | Replay |
| Receipts and metadata exist, no durable runtime | Claim is citable but depends on live upstreams | Cite |
| Missing source identity or hidden fetches dominate | Archive is possible, but reproducibility claim is weak | Draft / needs action |

Every score should point to evidence: lockfile, digest, blob, local index,
offline rebuild log, or exclusion. The UI should show captured, rebuilt,
SWH-backed, excluded, and failed dependencies.

## Deposit shape

The dependency archive may be small enough to live inside the main REE bundle, or
large enough to require a sibling deposit. Both shapes should be valid.

```text
bundle/
+-- ro-crate-metadata.json
+-- declaration/
+-- overlay/
+-- source/
+-- receipts/
+-- label/
+-- artifacts/
    +-- runtime-image.tar
    +-- dependency-archive/
        +-- closure-manifest.json
        +-- blobs/
        +-- indexes/
        +-- replay/
```

For large closures:

```text
REE DOI
  points to: declaration, overlay, receipts, label, runtime image
  references: dependency-archive DOI/PID

dependency-archive DOI/PID
  contains: closure manifest, blobs, indexes, replay instructions
```

Bind the dependency archive by digest, not just URL. DOI locates it; digest
identifies it.

For Rebuild, the Seal Manifest should include the dependency archive digest. If
the closure is a sibling deposit, the main REE deposit records both its DOI/PID
and its digest.

## Policy and legal surface

Dependency archiving has a policy surface that simple REE deposit does not.
repo2ree should classify every captured dependency as one of:

| Class | Meaning | Archive behavior |
|---|---|---|
| Redistributable | License or ecosystem norm permits redistribution | Include in closure |
| Public but uncertain | Publicly fetchable, redistribution unclear | Warn; require author decision |
| Private | Requires credentials or internal registry access | Record metadata; do not publish bytes by default |
| Restricted | Cannot legally be redistributed | Record access requirements and expected digest |
| Generated at build time | Produced by scripts, compilers, or model downloaders | Preserve output if allowed; record generation provenance |

Expose this in the Label. "Offline rebuild failed because private package X was
excluded" is a useful archival result.

## What repo2ree should not become

- Not a permanent archive. Zenodo, Dataverse, SWH, and institutional repositories
  own long-term storage and identifiers.
- Not a global package mirror. The closure is per REE, not a replacement for
  PyPI, npm, apt, conda, or Docker Hub.
- Not a universal license oracle. repo2ree can detect and disclose risk; authors
  and institutions decide what can be deposited.
- Not a guarantee that restricted data or proprietary dependencies become
  public. The archive can record absence and access requirements.
- Not a promise of bit-identical rebuilds for every substrate. Some stacks can
  be rebuilt only to a declared equivalence contract.
- Not a Nix-only gateway. Nix-native REEs should score well when their closure
  verifies, but non-Nix projects should remain archivable through native
  ecosystem adapters.

## Implementation path

### Phase 0 - Inventory

- Detect dependency ecosystems from source and overlays.
- Detect first-class Nix inputs (`flake.nix`, `flake.lock`, derivations) and
  treat them as their own substrate, not as generic shell scripts.
- Preserve the original declaration files in the bundle.
- Record SBOMs, build logs, and observed network fetches.
- Add Label axes for declaration strength, fetch observability, and closure
  capturability.

### Phase 1 - Substrate-native closures

- Start with the ecosystems already central to repo2ree's scoring.
- Capture blobs into the workbench CAS.
- Generate local replay indexes or caches.
- For Nix-native projects, archive the flake/derivation inputs and store
  closure, then verify by rebuilding or substituting from the captured closure
  with upstream substituters disabled.
- For Python, capture both wheels and sdists when possible, and record a
  source-to-wheel receipt when a wheel has to be rebuilt from sdist or SWH
  source.
- Add an offline rebuild job.
- Mark Rebuild eligible only after the offline rebuild passes or fails with
  explicit exclusions.

### Phase 2 - Archive deposits

- Extend the bundle metadata to bind dependency closures by digest.
- Include the Seal Manifest and `ree_digest` in archive metadata.
- Support inline closure deposit for small archives.
- Support sibling Zenodo/Dataverse deposits for large closures.
- Expose archive footprint, quota risk, and excluded dependencies before
  deposit.

### Phase 3 - Recording proxy

- Route build-time network through a recording proxy.
- Classify unknown fetches.
- Support replay through CAS rewrite rules.
- Use the proxy first as an observability tool, then as a capture tool where
  policy allows.

## Open design questions

- Should the dependency archive be named as a separate product primitive, or
  remain an implementation detail of Rebuild?
- Which ecosystem earns first-class support first: Python/uv, apt, OCI base
  layers, npm, conda, or whatever appears most often in target CS artifacts?
- Is "offline rebuild passed" required for the Rebuild tier, or can there be a
  weaker "closure captured but not independently rebuilt" state?
- When a package artifact vanishes, is an SWH-backed source rebuild an equivalent
  dependency, a derived dependency, or a lower-confidence fallback?
- How should package-version-to-source mappings be established when PyPI
  metadata points to a repository but not to an exact release commit?
- How should repo2ree represent dependencies that are technically capturable but
  legally ambiguous?
- Should base images be preserved as OCI layers, reconstructed from Dockerfiles,
  or both?
- When runtime images are large, should dependency closures be cheaper than
  Replay, more expensive, or offered as a separate institutional preservation
  decision?
- How should private dependencies be escrowed for reviewers without making them
  public?

## Working thesis

Archive the REE through existing repositories. Archive dependencies so the
computation can be rebuilt after upstream services change.
