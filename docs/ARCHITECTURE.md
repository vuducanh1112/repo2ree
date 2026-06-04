# repo2ree — Execution & Isolation Architecture

> **Status: proposed / in-design (2026-05).** The **how** of repo2ree —
> the target execution model, isolation boundary, action envelope, CAS,
> and bundle composition that implement the integration layer. For
> *why* the integration is shaped this way see
> [POSITIONING.md](POSITIONING.md); for *what* each named concept means
> normatively see [CONCEPTS.md](CONCEPTS.md); for *how the code is organized*
> into packages (the libraries/surfaces split, dependency rules) see
> [COMPONENTS.md](COMPONENTS.md). Today's code orchestrates
> plain Docker containers from the backend and mounts the host Docker
> socket (see [Current state](#current-state)); this document is the
> plan to replace that.

This doc covers *how REEs are built and run* — the isolation boundary, the
directory layout an REE lives in, the nesting of execution contexts, the
split between orchestration and execution, and the composition of the
archival bundle. For *what the product should become*
(outputs model, reuse, trust), see [REE_SERVICE_ROADMAP.md](REE_SERVICE_ROADMAP.md).

## Current state

Docker is used in two places, and both expose the host daemon — which is
**root-on-the-host equivalent**:

1. **Backend → host socket.** The backend runs in a container and mounts
   `/var/run/docker.sock` to spawn sibling run-containers
   ([docker-compose.yml:13](docker-compose.yml#L13),
   [docker-compose.dev.yml:11](docker-compose.dev.yml#L11)).
2. **Each run-container → host socket.** Every per-run container *also* gets the
   socket mounted, because the workspace's own build scripts run `docker`
   ([docker_env.py:239](core/src/repo2ree_core/working_environment/docker_env.py#L239),
   [review_ree.py:484](api/src/repo2ree_api/review_ree.py#L484) &
   [587](api/src/repo2ree_api/review_ree.py#L587)).

Layer 2 is the dangerous one: **untrusted repo code holds the host socket** and
can trivially escape to the host (`docker run --privileged -v /:/host …`). The
architecture below removes the socket from that path entirely.

## Isolation model: VM-backed working environments

Each REE is built and exercised inside its own **working environment** — a
lightweight VM-backed container via [Kata Containers](https://katacontainers.io/),
keeping the OCI/`docker create` workflow the code already uses while giving each
REE its own kernel behind a hardware-virtualization boundary.

- **Why Kata, not gVisor.** REE build scripts run `docker build` themselves.
  gVisor's userspace kernel doesn't reliably support running `dockerd` inside;
  Kata's real per-sandbox kernel does. Kata is the standard answer for safe
  nested Docker.
- **Hypervisor.** Prefer Cloud Hypervisor or Firecracker over QEMU — microVMs
  boot in ~100–200ms with single-digit-MB overhead, which matters for the
  spawn-per-REE model.
- **Runtime is configurable, not hardcoded.** Kata needs `/dev/kvm` (and nested
  virtualization if the host is itself a VM). Dev boxes (Docker Desktop /
  linuxkit) typically can't run it, so the runtime is a config knob:
  `runc` for dev, `kata` for prod.
- **Fallback if KVM is unavailable:** [Sysbox](https://github.com/nestybox/sysbox),
  a runc-based runtime built to run `dockerd` unprivileged. Weaker boundary
  (hardened shared kernel, not a VM) but no KVM requirement.

The host socket is **deleted** from the working environment. Docker activity
runs against a `dockerd` *inside* the Kata VM — confined to the VM, with no path
to the host.

## The three-tier nesting

A working environment is provisioned on the **first execution-needing operation**
(not at REE creation — see
[State ownership](#state-ownership-declarative-manifest-vs-durable-tree)) and is
thereafter the standing workshop where every assembly function runs. It carries a
fixed directory layout
(the REE's durable structure, see [below](#working-environment-directory-layout))
and the tools to act on it:

```
┌─ HOST / backend (control plane) ──────────────────────────────────────┐
│  repo2ree-api + core orchestration                                    │
│  owns: durable REE state (host storage), VM lifecycle, cp in/out,     │
│  command assembly. Touches host docker/containerd ONLY to launch VMs. │
│                                                                       │
│   on first action:  docker create --runtime=kata  repo2ree-workbench  │
│        │                                                              │
│        ▼                                                              │
│  ┌─ WORKING ENV  (Kata microVM, one per REE) ───────────────────────┐ │
│  │  base tools: dockerd (in-VM), repo2ree CLI, git, build toolchains │ │
│  │                                                                   │ │
│  │  /ree                          ── the REE's durable structure ──  │ │
│  │  ├── workspace/   mutable source checkout                         │ │
│  │  ├── overlays/    REE definition: runtime spec, experiment        │ │
│  │  │                specs, generated Dockerfiles/scripts            │ │
│  │  │                        ▲ declared via the frontend             │ │
│  │  └── artifacts/   produced outputs:                               │ │
│  │      ├── runtime-image.tar   ◄── the REE                          │ │
│  │      ├── sbom/                                                    │ │
│  │      ├── dependency-score/                                        │ │
│  │      └── runs/<id>/   experiment results & traces                 │ │
│  │                                                                   │ │
│  │  assembly functions (repo2ree CLI) read workspace+overlays,       │ │
│  │  write artifacts:                                                 │ │
│  │    build-runtime             ─ docker build ─► runtime-image      │ │
│  │    generate-sbom             ────────────────► sbom               │ │
│  │    evaluate-dependency-score ────────────────► dependency-score   │ │
│  │    run-experiment   ─ docker run runtime-image ─► runs/<id>       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
        ✗ no host docker.sock ever crosses into the working env
```

It is containers-inside-a-VM, **not** VM-in-VM — only one virtualization layer
(Kata). The runtime build and each experiment run are ordinary containers
against the in-VM `dockerd`; *"runs happen in separated environments"* means each
experiment gets its own container, not its own VM.

### Working-environment directory layout

The VM holds the REE as a directory tree that maps directly onto the
workspace↔REE seam:

| Dir | Role | Seam position |
|-----|------|---------------|
| `/ree/workspace/` | Mutable source checkout + user edits. Corresponds to today's `CONTAINER_WORKSPACE` (`/workspace`, [run_script.py:17](core/src/repo2ree_core/container/run_script.py#L17)). | the **inputs** |
| `/ree/overlays/` | The REE *definition* layered beside the pristine source: runtime spec, experiment specs, generated Dockerfiles/scripts. Authored declaratively via the frontend. | the **environment** |
| `/ree/artifacts/` | Produced *outputs/evidence*: the runtime image, SBOM, dependency score, per-run results & traces. | the **outputs** |

Overlays keep the source checkout pristine while REE-defining material lives
beside it — realizable as plain directories, or as an `overlayfs` mount over the
workspace if copy-on-write semantics over the source are wanted.

This **tree** — not the running VM — is the durable REE state. The microVM is a
rehydratable workbench: tear it down and recreate it by re-mounting the persisted
tree. That keeps standing-VM cost bounded when REEs are numerous or long-lived
(the tree persists to host storage; cf. `WORKSPACE_STORAGE_DIR`).

### Glossary (keep these distinct)

The workspace↔REE seam must not collapse — this names the tiers carefully:

| Term | What it is | Lifetime |
|------|-----------|----------|
| **Workspace** | The mutable source checkout (`/ree/workspace`). | Durable (in the tree) |
| **Working env** | The per-REE **sandbox** (Kata microVM) provisioned on the first execution-needing operation; hosts the `/ree` tree and all assembly functions; never shipped. | VM rehydratable; the `/ree` tree is the durable state |
| **Runtime image (the REE)** | The reproducible artifact built inside the working env (`artifacts/runtime-image`). The thing whose reproducibility is guaranteed. | The product |
| **Experiment run** | An *instance* of the runtime image, executed in its own container to produce results. | Per-run |

The seam: workspace (mutable source) → overlays (REE definition) → artifacts
(REE products, incl. the runtime image) → experiment (a run of the REE).

### The workbench image

The working env boots from a repo2ree-controlled base image (not `docker:latest`)
bundling `dockerd`, the `repo2ree` CLI, git, and build toolchains. Pin and
version it — the workbench is itself part of reproducibility.

## Control plane / execution plane split

Orchestration and execution are separate planes — the "thin client, fat agent"
pattern (cf. kubectl→kubelet, CI orchestrator→runner):

```
CONTROL PLANE                          EXECUTION PLANE
(frontend + api)                       (repo2ree core, in the working-env VM)
─────────────────                      ───────────────────────────────────────
• REE management pane:                 • repo2ree CLI actually runs here
    declare runtimes & experiments     • build-runtime  → docker build
• edit overlays from declarations      • generate-sbom
• manage REE lifecycle (VM up/down)    • evaluate-dependency-score
• assemble commands from intent        • run-experiment → docker run
• ferry tree in / results out          • (all read workspace+overlays,
• stream logs, persist metadata          write artifacts)

   declaration ─► [assemble] ─► repo2ree <cmd> ──exec in VM──► artifacts ─►
```

The **frontend is a declarative REE management pane**: the user declares
runtimes and experiments; those declarations populate `/ree/overlays`; the
*functions* that actually build the environment (docker image, SBOM, score,
runs) execute inside the working-env VM. The frontend never executes anything
itself.

### State ownership: declarative manifest vs. durable tree

The two planes own *different kinds of state*, and conflating them is the easy
mistake:

- **The declarative manifest is control-plane state.** The runtime/experiment
  declarations that populate `/ree/overlays` are small, edited continuously (the
  frontend autosaves on a 300ms debounce —
  [useReeDraftSync.ts](frontend/src/shell/ui/ree-editor/workspace-sync/useReeDraftSync.ts),
  persisted via the draft-patch route [manage_ree.py:86](api/src/repo2ree_api/manage_ree.py#L86)),
  and guarded by optimistic concurrency (`expectedVersion`). That concurrency
  check must stay **single-machine** — keep the manifest in host storage / the
  control-plane DB. Editing a field must never round-trip into a VM.
- **The durable tree and artifacts are execution-plane state.** The workspace
  checkout, materialized overlays, and `artifacts/` live with the working env
  (persisted as the `/ree` tree).
- **Projection, not shared mutable state.** The manifest is *projected* into
  `/ree/overlays` at job dispatch — the lab receives a consistent snapshot when
  an operation runs, rather than the browser and the VM mutating the same bytes
  live.

**Consequence — provision the lab lazily.** Because declaring and editing need no
executor, the working env is created on the first execution-needing operation
(acquire / build / run), *not* when the REE record is created. A freshly-created
REE the user is still naming and declaring has no VM and costs nothing — which is
also why the autosave path above must not depend on one.

### The repo2ree CLI is the contract

Because the api/frontend defer execution, the `repo2ree` CLI is the seam between
the two planes and must be designed as a contract:

- **Structured I/O:** commands emit JSON (or write to known `artifacts/` paths),
  use stable flags, and return meaningful exit codes. Build the result payload
  on top of the existing `StepOutcome` (exit code / stdout / stderr) shape in
  [working_environment/base.py](core/src/repo2ree_core/working_environment/base.py).
- **The CLI is the product; api/frontend are a hosted UX over it.** The same
  `repo2ree build-runtime …` a user could run locally is what the backend drives
  remotely — dogfooding for free, and an independently testable surface.
- **Provenance:** every REE operation becomes a recorded, replayable command
  against the `/ree` tree. For a reproducibility tool this is the seam made
  concrete — the command log *is* the record of what produced the REE.
- **The wire form is a typed action envelope, not a shell string.** The
  control→execution boundary carries structured data — never an interpolated
  `repo2ree …` string. Schema and caching consequences in
  [The wire form](#the-wire-form-a-typed-action-envelope) and
  [Content-addressed state](#content-addressed-state-cas-and-the-action-cache)
  below. This is what makes [rule 1](#two-rules-this-imposes) enforceable
  rather than aspirational.

### The wire form: a typed action envelope

The envelope mirrors the [Bazel Remote Execution API](https://github.com/bazelbuild/remote-apis)
(REAPI) shape — three layered messages, defined in `core` and shared by api,
CLI, and the in-VM agent, whose digests compose into one identifier for the
build:

```
Command {
  operation:       build_runtime | generate_sbom |
                   evaluate_dependency_score | run_experiment
  args:            typed-per-operation
  workbench_image: digest                # workbench is itself part of repro
  output_paths:    [paths in artifacts/ to capture]
}

InputRoot = Merkle directory digest over the *projected* inputs:
  workspace/ + the per-operation slice of overlays/

Platform { runtime: kata|runc|sysbox, cpu, mem, … }

Action {
  command_digest
  input_root_digest
  platform_digest
  timeout
}
  action_digest = sha256(Action proto)
```

Two consequences:

- **`input_root_digest` subsumes "manifest version" on the wire.** A content
  hash is strictly stronger than a monotonic version — it also catches "same
  version, different bytes" and is portable across machines. The control-plane
  manifest still carries `expectedVersion` for single-machine optimistic
  concurrency on the autosave path
  ([State ownership](#state-ownership-declarative-manifest-vs-durable-tree));
  that's a different concern and stays.
- **Per-operation input slices.** `build_runtime` doesn't take experiment specs
  as inputs; `run_experiment` doesn't take dependency-score config. Each
  operation's input root is a *subset* of `/ree`, which is what makes the cache
  (next section) invalidate at the right granularity automatically — no
  hand-written dirtiness logic.

The CLI's argv/JSON is its *local* surface; the wire transports the Action
proto, not its rendering.

### Content-addressed state: CAS and the action cache

Once the envelope has stable digests, two host-side stores fall out — and they
reframe what "durable state" means:

```
CAS                 (content-addressable blob store)
  blobs/<sha256>    raw files, log bundles, runtime-image layers, sbom.json, …
  trees/<sha256>    Directory protos → recursive Merkle root identifies a tree

ActionCache         (small KV)
  action_digest →   ActionResult { output_digests, exit_code,
                                   stdout_digest, stderr_digest, executed_at }
```

This sharpens the
[durable-tree claim above](#working-environment-directory-layout): the *blobs*
are the durable state; the `/ree` tree-on-disk inside the VM and the VM itself
are both rehydratable views of CAS content. The diagram's `cp in / cp out`
([above](#the-three-tier-nesting)) becomes *materialize inputs from CAS /
ingest outputs into CAS* — same shape, stronger properties.

The execution loop with caching:

```
1. api projects manifest → overlays; snapshots inputs into CAS
2. core assembles Command + Action → computes action_digest
3. lookup action_digest in ActionCache
     hit  → return recorded ActionResult; fetch output blobs on demand. Done.
     miss → dispatch Action to the in-VM agent
4. agent materializes input_root from CAS, runs the op against in-VM dockerd,
   uploads each output_path to CAS, records the ActionResult
```

What this earns, specifically for a reproducibility product:

- **The action digest *is* the reproducibility receipt.** "REE produced by
  action `sha256:abc…` over inputs `sha256:def…` on platform `kata-…`" names
  the build exactly — the provenance bullet above becomes a primary key, not
  prose.
- **Correct invalidation for free.** Editing an experiment overlay doesn't
  rebuild the runtime image because `build_runtime`'s `action_digest` doesn't
  change.
- **A real reproducibility test.** Replaces the `--strict` re-load open
  question ([below](#open-decisions)): re-execute the action and assert output
  digests match bit-for-bit — that tests reproducibility, not packaging.
- **Shared REE = CAS substitution.** Multiple machines opening the same REE
  pull artifacts by digest. The Nix binary-cache model, and exactly the
  product story.
- **In-flight dedup and cleaner cancellation.** Concurrent triggers of the
  same Action coalesce on `action_digest`; cancel = stop waiting on the
  future, signal the agent only when no waiter remains — closes the
  cross-boundary cancellation gap noted in
  [Migration notes](#migration-notes).

**Prior art to borrow from, not reinvent.** REAPI
(`Action`/`Command`/`ActionResult`, CAS, ActionCache) and the
[Nix daemon + binary cache](https://nixos.org/manual/nix/stable/) model.
Reading both before fixing the envelope schema is cheaper than discovering
their constraints later.

**Things to be careful about:**

- **Non-determinism inside actions.** `docker build` isn't bit-reproducible
  without effort (timestamps, layer order, network deps). REAPI keys on
  *input* identity, not output equality — the right first step. Promoting to
  bit-equal verification needs BuildKit reproducible-build flags
  (`SOURCE_DATE_EPOCH`, sorted tarballs).
- **Workspace mutability.** Snapshot to CAS at action dispatch, not on every
  keystroke — already implied by "projection at job dispatch"
  ([above](#state-ownership-declarative-manifest-vs-durable-tree)).
- **Large blobs.** `runtime-image.tar` is multi-GB. Pragmatic split: **OCI
  registry for runtime images** (already content-addressed, dockerd speaks it
  natively), own CAS for everything else (sbom, score, run bundles, logs).
- **Trust.** ActionResults are only safe from sources you trust to have
  executed honestly. Same-tenant for now; signed-narinfo style if/when a
  shared substituter ships.
- **`output_paths` discipline.** Anything written outside `output_paths` is
  lost — a feature (forces operations to be honest about outputs), but it
  means the inline-docker migration ([below](#migration-notes)) needs a
  per-operation declaration of which paths matter.
- **GC.** CAS grows unboundedly; mark-from-roots GC over "REEs users still
  care about" + recent ActionResults. Standard but real.

**Minimum viable subset.** Don't clone REAPI. (1) Define the typed envelope and
compute `action_digest` deterministically in `core`, shared by api, CLI, and
agent. (2) Trivial host-side CAS (`blobs/<sha256>`, SQLite ActionCache).
(3) OCI registry for runtime images. Distributed cache, signing, chunking, and
GC are deferrable — they're bolt-on once the envelope is right.

### Two rules this imposes

1. **Assemble commands server-side, never in the frontend.** The frontend sends
   structured *declarations/intent* (it's FCIS — intent is just data); a **pure
   core function** translates intent → concrete command; the working env runs it.
   Letting the browser hand raw command strings to a VM is an injection straight
   into the execution plane.
2. **Core has two consumption modes.** This sharpens the existing thin-api
   layering rather than breaking it:
   - **Library, host-side** — only the *pure* bits: intent→command assembly,
     spec/overlay validation. (api stays thin, still only calls core.)
   - **CLI, in-VM** — all *effectful* bits: build, run, score, sbom.

   Discipline: *touches docker/fs/network → CLI in VM; pure translation/
   validation → library host-side.*

## Archival composition

A deposited REE is a **composition manifest**, not a self-contained
tarball. The same source/overlay split that defines `/ree/` at runtime
carries through to the archived form, with each component placed in the
institution best suited to hold it.

### Layering and ownership

| Layer                            | What                                                          | Archive home                          | Reason                                                            |
|----------------------------------|---------------------------------------------------------------|---------------------------------------|-------------------------------------------------------------------|
| Source                           | The pristine repo at a commit                                 | **SWH** by SWHID pointer              | SWH already owns source code at internet scale                    |
| Overlay                          | repo2ree's contribution (declaration, generated recipes, scripts) | Inline in the bundle              | New; specific to this REE; nobody else owns it                    |
| Receipts                         | Run outputs and provenance                                    | Inline in the bundle                  | Compact; structural; benefits from co-location with the overlay   |
| Artifacts (selectively)          | Built runtime image, inputs closure                           | Inline by fidelity tier               | Optional; size-versus-fidelity tradeoff                           |
| Identifiers (DOI / SWHID / PID)  | The handles that resolve to the above                         | Their issuing services                | Each handle is a service's responsibility, not a content artifact |

repo2ree owns the **hot tier** (live CAS + ActionCache), the **bundle
format** (RO-Crate-shaped, defined here), and the **deposit and
resolution workflow**. Long-term archival itself is delegated.

### Bundle layout

```
bundle/
├── ro-crate-metadata.json    # FAIR metadata, JSON-LD
├── declaration/              # the intent (small, durable)
├── overlays/                 # repo2ree's contribution to the source
├── source/                   # usually empty: a SWHID pointer in metadata.
│                             # Inline bytes only in Draft state (no SWHID).
├── receipts/                 # Run Receipts with predecessor links
├── label/                    # the Repro Label snapshot at deposit time
└── artifacts/                # populated by fidelity tier (see below)
    ├── runtime-image.tar     # Replay+
    └── inputs-closure/       # Rebuild only
```

### Fidelity tiers

Three tiers, each a strict superset of the previous. The chosen tier is
recorded in the RO-Crate metadata and surfaced through the Label.

| Tier        | Contents                                                  | Re-runnable?           | Re-derivable?              | Storage |
|-------------|-----------------------------------------------------------|------------------------|----------------------------|---------|
| **Cite**    | declaration + overlay + source-pointer + Receipts + Label | iff upstreams alive    | iff upstreams alive        | KB–MB   |
| **Replay**  | Cite + runtime image                                      | always (OCI + amd64)   | no                         | MB–GB   |
| **Rebuild** | Replay + inputs closure                                   | always                 | yes, against dead internet | GB      |

**Recommended default: Replay.** Most paper-supplementary use cases want
"I can run this in 2034 even if PyPI is gone." Replay covers that without
requiring closure-capture infrastructure that doesn't exist yet.

### Closure capture (Rebuild tier)

Capturing the dependency closure for the Rebuild tier is the open
engineering work. Two paths:

1. **Substrate-specific.** Each ecosystem has native lockfile + download
   mechanisms — `pip download`, `apt-get install --download-only`,
   `docker save` for base layers, etc. 80% of the value for 20% of the
   work; aligns with the substrate-grading machinery already driving the
   Label (the same code that scores `uv.lock` knows how to mirror its
   wheels).
2. **Recording HTTP proxy.** All outbound build traffic routed through a
   CAS-backed proxy that captures (URL → content-hash). Substrate-agnostic
   and exhaustive. Requires TLS MITM in the build sandbox and a custom CA;
   longer-arc work.

The v1 path is (1), scoped to whatever substrates the Label already
grades. Rebuild is not on the critical path; Cite and Replay are.

### REE lifecycle states

Archival readiness is a property of the REE, exposed in the UI and
recorded by the Label:

| State              | What's true                                          | Eligible for canonical deposit?                                                 |
|--------------------|------------------------------------------------------|---------------------------------------------------------------------------------|
| **Draft**          | Local-only or no stable identifier; pre-deposit iteration | No — bundles may carry source bytes inline as a temporary snapshot         |
| **Archive-ready**  | Source resolves to an SWHID; declaration and overlay are stable | Yes — bundle becomes source-by-pointer                                |
| **Deposited**      | Bundle deposited on Zenodo; DOI assigned; SWHIDs registered | Already archived; future deposits create new versions                     |

Promotion Draft → Archive-ready happens when the source acquires a stable
identifier (push to a SWH-crawled forge; deposit via Zenodo's
`save_code_now`; or via SWH's direct deposit API).

### What repo2ree does not do

- **Run a permanent archive.** Bundles live on Zenodo; source lives on
  SWH; PIDs come from DataCite or PID4NFDI. The Zenodo–SWH integration
  means a single deposit on Zenodo automatically archives source-code
  components to SWH and binds them to SWHIDs.
- **Issue identifiers.** repo2ree consumes identifiers from the archival
  services; it does not mint its own.
- **Replicate package ecosystems.** No mirror of PyPI; no apt rehost. The
  closure-capture work produces *per-REE* archived copies of required
  artifacts, not a general-purpose mirror.

## Migration notes

- **Introduce CAS + ActionCache early — even before remoting.** Route the
  existing local job model through the envelope/CAS path on the host first
  (host-side CAS, SQLite ActionCache, OCI registry for runtime images). The
  cost is small and it makes the control→execution split data-shaped from day
  one; the later switch to an in-VM agent becomes a transport change, not a
  protocol change. See
  [Content-addressed state](#content-addressed-state-cas-and-the-action-cache).
- **Establish the `/ree` layout on first provisioning** (not REE creation — see
  [State ownership](#state-ownership-declarative-manifest-vs-durable-tree)).
  `__enter__` no longer just cp's the workspace to `/workspace` — it lays down
  `workspace/`, `overlays/`, `artifacts/` and seeds overlays by projecting the
  declared (control-plane) manifest.
- **Remote the existing job model; don't reinvent it.** `_start_background_run` /
  `_run_summary` / `_is_cancel_requested`
  ([run_management.py:172](api/src/repo2ree_api/run_management.py#L172)) already
  give submit→stream→cancel as an async job — exactly the shape the control plane
  needs. Remoting an operation is mostly swapping the local `Thread` for *dispatch
  to the in-VM agent* and streaming its logs back. The one piece that does not
  survive the boundary is cancellation: the flag-file check
  ([:138](api/src/repo2ree_api/run_management.py#L138)) becomes a remote signal to
  the agent.
- **Relocate `dockerfile_utils` into the VM.** It currently builds images on the
  **host** via `docker.from_env()` against the host socket
  ([build_image.py:24](core/src/repo2ree_core/dockerfile_utils/build_image.py#L24)).
  In the new model this same code runs *inside* the working env against the
  in-VM `dockerd` — which is why `repo2ree` itself must be a base tool in the
  workbench image. The backend's job shrinks to launch / cp-in / invoke /
  cp-out.
- **`WorkingEnvironmentSpec` gains fields:** `runtime` (`kata`/`runc`), the
  workbench `image`, and `resources` (CPU/mem) — the latter fed by the existing
  experiment resource-estimate fields, which now double as **VM sizing**.
- **`DockerWorkingEnvironment._create()`** drops the `-v docker.sock` mount, adds
  `--runtime`, and starts the in-VM `dockerd` before the first script `exec`
  (base shifts toward `docker:dind`; no `--privileged` needed under Kata).
- **The inline-docker blocks in [review_ree.py](api/src/repo2ree_api/review_ree.py)**
  are the primary migration target: each should be sorted into "pure → stays as
  a host-side core call" vs "effectful → becomes a `repo2ree <cmd>` run in the
  VM." That inventory effectively *defines* the CLI surface.

## Open decisions

- **Runtime-image source for experiment runs.** With one working-env VM per REE,
  build and runs share the same in-VM `dockerd`, so `run-experiment` can use the
  just-built image directly (fast). Optionally re-`docker load` it from
  `artifacts/runtime-image.tar` first (the existing
  [`save_image_to_tar`](core/src/repo2ree_core/dockerfile_utils/build_image.py#L77)
  helper) to prove the image is self-contained. Once the action cache is in
  place ([above](#content-addressed-state-cas-and-the-action-cache)) the
  stronger check is re-executing the build Action and asserting output digests
  match — that tests reproducibility, not just packaging. Recommend fast by
  default; strict = action re-execution.
- **VM persistence model.** The durable REE state is the `/ree` tree, not the VM.
  Standing-VM-per-REE is simplest but costly at scale; rehydrate-on-demand
  (persist the tree, recreate the VM when an REE is opened) bounds cost.
  Recommend rehydratable, with the tree as source of truth. *First* provisioning
  is likewise lazy — deferred to the first execution-needing operation — so an REE
  that is only being declared/edited costs no VM (see
  [State ownership](#state-ownership-declarative-manifest-vs-durable-tree)).
- **KVM availability in the deployment target** decides Kata vs. the Sysbox
  fallback.
