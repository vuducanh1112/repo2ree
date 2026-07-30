# repo2ree — Execution & Isolation Architecture

> **Status: implementation + target design (2026-06).** The **how** of repo2ree —
> the implemented workbench/typed-envelope path and the target isolation/CAS
> model that should harden it. For
> *why* the integration is shaped this way see
> [research/POSITIONING.md](research/POSITIONING.md); for *what* each named concept means
> normatively see [CONCEPTS.md](CONCEPTS.md); for *how the code is organized*
> into packages (the libraries/surfaces split, dependency rules) see
> [COMPONENTS.md](COMPONENTS.md).

This doc covers how REEs are built and run: isolation, directory layout,
orchestration/execution split, action envelopes, CAS, and bundle composition.
For product evolution, see
[REE_SERVICE_ROADMAP.md](research/REE_SERVICE_ROADMAP.md).

## Current state

The main REE path now has the intended package seam:

- `api` calls `repo2ree_supervisor.WorkbenchManager`.
- `supervisor` provisions one persistent workbench container per REE.
- Commands cross the host/workbench boundary as typed `repo2ree_protocol`
  commands.
- The workbench invokes `repo2ree-exec`, which calls `core` handlers inside the
  container.

Current isolation is **Docker-in-Docker inside a privileged workbench**. The
backend never touches a container runtime: workbenches are launched by the
*agent* (its own deployable, holding the docker socket —
[docker-compose.yml](../docker-compose.yml)) over the outbound WebSocket. The
workbench does not receive the host socket. It runs its own daemon and stores
`/var/lib/docker` in a per-REE volume
([docker_runtime.py](../agent/src/repo2ree_agent/docker_runtime.py)).

The risk has moved: untrusted repo code no longer holds the host Docker socket
on the main path, but the workbench is still privileged and not VM-backed.

## Target isolation model: VM-backed working environments

Each REE should run inside its own **working environment**: a lightweight
VM-backed container via [Kata Containers](https://katacontainers.io/). This keeps
the OCI workflow while giving each REE its own kernel boundary.

- **Why Kata, not gVisor.** REE build scripts run `docker build` themselves.
  gVisor does not reliably support nested `dockerd`; Kata does.
- **Hypervisor.** Prefer Cloud Hypervisor or Firecracker over QEMU. MicroVM boot
  cost matters for spawn-per-REE.
- **Runtime is configurable, not hardcoded.** Kata needs `/dev/kvm` (and nested
  virtualization if the host is itself a VM). Dev boxes (Docker Desktop /
  linuxkit) typically can't run it, so the runtime is a config knob:
  `runc` for dev, `kata` for prod.
- **Fallback if KVM is unavailable:** [Sysbox](https://github.com/nestybox/sysbox),
  a runc-based runtime built to run `dockerd` unprivileged. Weaker boundary
  (hardened shared kernel, not a VM) but no KVM requirement.

The target hardening step is to replace today's privileged Docker-in-Docker
workbench with a VM-backed one. Docker activity still runs against a daemon
inside the workbench, but the workbench gets its own kernel boundary.

## The three-tier nesting

A working environment is provisioned on the **first execution-needing operation**
(not at REE creation; see
[State ownership](#state-ownership-declarative-manifest-vs-durable-tree)). It
then hosts the fixed `/ree` layout and the tools that act on it:

```
┌─ HOST / backend (control plane) ──────────────────────────────────────┐
│  repo2ree-api + supervisor                                            │
│  owns: durable REE state (host storage), workbench lifecycle,         │
│  command dispatch. Touches host docker/containerd to launch workbenches.│
│                                                                       │
│   on first action:  docker run <env image>                          │
│        │                                                              │
│        ▼                                                              │
│  ┌─ WORKING ENV  (today: privileged dind; target: Kata microVM) ────┐ │
│  │  base tools: dockerd, repo2ree-exec, git, build toolchains        │ │
│  │                                                                   │ │
│  │  /ree                          ── the REE's durable structure ──  │ │
│  │  ├── upstream/    extracted source snapshot                        │ │
│  │  ├── overlay/     REE definition: ree-scripts/ (build, activation, │ │
│  │  │                experiments), generated recipes                  │ │
│  │  │                        ▲ declared via the GUI             │ │
│  │  ├── workspace/   materialized upstream + overlay view             │ │
│  │  ├── artifacts/   produced evidence:                              │ │
│  │  │   ├── <runtime>.tar             ◄── the REE                    │ │
│  │  │   ├── sbom.json                                                │ │
│  │  │   └── reproducibility-report.json                              │ │
│  │  ├── results/<name>/   captured experiment outputs (baseline)     │ │
│  │  ├── runs/<id>/        NDJSON logs & run results                  │ │
│  │  ├── receipts/author/  latest successful receipt per step         │ │
│  │  └── reviews/<id>/     one reviewer attempt (its own tree)        │ │
│  │                                                                   │ │
│  │  assembly functions (repo2ree-exec/core) read workspace+overlay,  │ │
│  │  write artifacts:                                                 │ │
│  │    build-runtime             ─ docker build ─► <runtime>.tar      │ │
│  │    generate-sbom             ────────────────► sbom.json          │ │
│  │    evaluate-dependency-score ─────► reproducibility-report.json   │ │
│  │    run-experiment   ─ docker run runtime-image ─► runs/<id>       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
        ✗ main path: no host docker.sock crosses into the workbench
```

In the target form it is containers-inside-a-VM, **not** VM-in-VM — only one
virtualization layer (Kata). The runtime build and each experiment run are
ordinary containers against the workbench `dockerd`; *"runs happen in separated
environments"* means each experiment gets its own container, not its own VM.

### Working-environment directory layout

The workbench holds the REE as a directory tree that maps directly onto the
workspace↔REE seam:

| Dir | Role | Seam position |
|-----|------|---------------|
| `/ree/upstream/` | Extracted source snapshot, treated as read-only. | the **source** |
| `/ree/overlay/` | repo2ree-authored files layered beside the source: runtime scripts, generated recipes, experiment specs. | the **environment** |
| `/ree/workspace/` | Materialized view used at build/run time. It is derived from `upstream/ + overlay/` and may be rebuilt. | the **inputs** |
| `/ree/artifacts/` | Produced evidence: runtime image, SBOM (`sbom.json`), reproducibility report. | the **outputs** |
| `/ree/results/<name>/` | Per-experiment produced-results store: the author baseline a reviewer diffs against. | the **outputs** |
| `/ree/runs/` | NDJSON logs and run results for command executions. | the **lineage** |
| `/ree/receipts/author/` | Selected author evidence: the latest successful receipt per step. | the **lineage** |
| `/ree/reviews/<review_id>/` | One reviewer attempt, a parallel tree with its own `upstream/`, `overlay/`, `workspace/`. Never writes to author evidence. | the **review** |

`upstream/` and `overlay/` are the sources of truth; `workspace/` is the working
view. The source stays pristine while REE-defining material lives beside it.
Receipts and review attempts are covered in
[engineering/step-lifecycle.md](engineering/step-lifecycle.md) and
[engineering/review-evidence.md](engineering/review-evidence.md).

This **tree** — not the running container/VM — is the durable REE state. The
workbench is rehydratable: tear it down and recreate it by re-mounting the
persisted tree. That keeps standing-workbench cost bounded when REEs are numerous or long-lived
(the tree lives on the per-REE workbench volume, not host storage).

### Glossary (keep these distinct)

The workspace↔REE seam must not collapse — this names the tiers carefully:

| Term | What it is | Lifetime |
|------|-----------|----------|
| **Workspace** | The materialized build/run view (`/ree/workspace`). | Durable but derived |
| **Working env** | The per-REE **sandbox** provisioned on the first execution-needing operation; today a privileged Docker-in-Docker workbench, target a Kata/Sysbox-backed one. Hosts the `/ree` tree and all assembly functions; never shipped. | Rehydratable; the `/ree` tree is the durable state |
| **Runtime image (the REE)** | The reproducible artifact built inside the working env (`artifacts/runtime-image`). The thing whose reproducibility is guaranteed. | The product |
| **Experiment run** | An *instance* of the runtime image, executed in its own container to produce results. | Per-run |

The seam: upstream source + overlay definition → materialized workspace →
artifacts (REE products, incl. the runtime image) → experiment run.

### The workbench env image

The working env boots from an *env image* that provides only the substrate —
the default is upstream `docker:dind`, **pinned by manifest-list digest** in
the backend's image catalog (`api/src/repo2ree_api/settings.py`); the bench is
part of reproducibility, so the catalog pins refs and bumps them deliberately.
The image carries no repo2ree content: at provision time the agent injects its
**executor bundle** (the `repo2ree-exec` nix closure, mounted read-only at
`/nix/store` from a content-addressed volume) and its **tools bundle**
(`syft`, `git`, `curl`, `tar`, … + TLS roots), then verifies the bench
contract with
`repo2ree-exec doctor`. Executor and tools therefore version with the agent,
never with the env image — any image that keeps a process alive and has a
writable `/ree` can be a bench.

Images that ship their own `/nix` (nix-built env images) can't take the
`/nix/store` mount; the agent detects them, skips injection, and expects
`repo2ree-exec` on their PATH — the escape hatch for benches that bake their
own executor.

## Control plane / execution plane split

Orchestration and execution are separate planes — the "thin client, fat agent"
pattern (cf. kubectl→kubelet, CI orchestrator→runner):

```
CONTROL PLANE                          EXECUTION PLANE
(gui + api)                            (repo2ree core, in the working-env VM)
─────────────────                      ───────────────────────────────────────
• REE management pane:                 • repo2ree-exec/core run here
    declare runtimes & experiments     • build-runtime  → docker build
• edit overlay from declarations       • generate-sbom
• manage REE lifecycle (VM up/down)    • evaluate-dependency-score
• assemble commands from intent        • run-experiment → docker run
• ferry tree in / results out          • (all read workspace+overlay,
• stream logs, persist metadata          write artifacts)

   declaration ─► [assemble] ─► Command JSON ──repo2ree-exec──► artifacts ─►
```

The **GUI is a declarative REE management pane**: the user declares
runtimes and experiments; those declarations populate `/ree/overlay`; the
*functions* that actually build the environment (docker image, SBOM, score,
runs) execute inside the working-env VM. The GUI never executes anything
itself.

### State ownership: declarative manifest vs. durable tree

The two planes own *different kinds of state*, and conflating them is the easy
mistake:

- **The declarative manifest is control-plane state.** The runtime/experiment
  declarations that populate `/ree/overlay` are small, edited continuously and
  persisted through the REE/workspace API
  ([useReeIntentSync.ts](../gui/src/shell/state/ree-editor/workspace-sync/useReeIntentSync.ts),
  [authoring/intent.py](../api/src/repo2ree_api/authoring/intent.py)),
  and guarded by optimistic concurrency (`expectedVersion`). That concurrency
  check must stay **single-machine** — keep the manifest in host storage / the
  control-plane DB. Editing a field must never round-trip into a VM.
- **The durable tree and artifacts are execution-plane state.** The workspace
  snapshot, overlay files, materialized workspace, and `artifacts/` live with the working env
  (persisted as the `/ree` tree).
- **Projection, not shared mutable state.** The manifest is *projected* into
  `/ree/overlay` at job dispatch — the lab receives a consistent snapshot when
  an operation runs, rather than the browser and the VM mutating the same bytes
  live.

**Consequence — provision the lab lazily.** Because declaring and editing need no
executor, the working env is created on the first execution-needing operation
(acquire / build / run), *not* when the REE record is created. A freshly-created
REE the user is still naming and declaring has no workbench and costs nothing — which is
also why the autosave path above must not depend on one.

### The command envelope is the contract

Because the api/GUI defer execution, the typed `Command` envelope and
`repo2ree-exec` are the seam between the two planes:

- **Structured I/O:** `repo2ree-exec` reads typed JSON, streams structured
  `LogFrame`s, writes an `ActionResult`, and exits with a meaningful status.
- **The future host CLI is a surface over the same contract.** A user-facing
  `repo2ree` command should drive supervisor/protocol exactly as the API does,
  not invent a parallel execution path.
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

### Remote execution clients: user-owned runners

Hosted repo2ree should support cloud, university, and user-owned machines
without becoming the holder of their critical credentials. The service should
not SSH into a user's server, store private keys, hold passphrases, or keep a
university kubeconfig. Remote execution is a **runner** problem: a small
repo2ree client runs inside the user's boundary and calls the service outbound.

```
repo2ree service / control plane
  owns: users, REE intent, job records, action dispatch, logs, receipts
        |
        | outbound runner channel (mTLS or signed token), typed Actions
        v
repo2ree runner / execution client
  owns: local credentials, local provider API, workbench lifecycle
        |
        | WorkbenchProvider
        v
Docker host | cloud VM | Kubernetes namespace | HPC scheduler
        |
        v
isolated workbench -> repo2ree-exec -> core
```

The runner is the trust and policy boundary for a non-local execution plane. It
is needed for five reasons:

- **Credentials stay local.** Cloud credentials, SSH agents, kubeconfigs,
  private package tokens, and institutional storage credentials stay where the
  user or institution already manages them.
- **Networks stay closed.** Many clusters and university machines cannot accept
  inbound connections from a SaaS service. An outbound runner channel works
  through ordinary egress policy and avoids exposing SSH or the Kubernetes API.
- **Substrates differ.** Docker hosts, cloud VMs, Kubernetes namespaces, and HPC
  schedulers all have different APIs and policy knobs. The service should speak
  repo2ree Actions; the runner translates those Actions into local operations.
- **Local policy is enforceable.** Quotas, allowed images, GPU partitions,
  network policy, storage classes, and cleanup rules are enforced by the runner
  using local authority rather than by a remote service guessing what is safe.
- **Data can stay where it lives.** Sensitive datasets, licensed dependencies,
  and private registries can be mounted or fetched inside the user's boundary
  without copying access material into repo2ree's hosted control plane.

The runner is a deployment wrapper around the same supervisor/protocol seam. It
does not change the command envelope and it does not execute repository code
itself; it turns a typed Action into a local workbench on whatever substrate the
institution permits. The actual REE operation still crosses into the workbench
and runs through `repo2ree-exec`.

The bootstrap flow is:

1. The service creates a short-lived, single-use runner join token.
2. The user, cloud-init, a golden image, or a Helm chart installs the runner in
   the target environment.
3. The runner opens an outbound connection to the service and exchanges the
   join token for a revocable runner identity, such as an mTLS certificate or
   signed runner credential.
4. The join token is discarded. Long-lived SSH keys, cloud credentials, and
   kubeconfigs stay in the user's environment.
5. The service dispatches typed Actions to that runner. The runner provisions
   workbenches, streams structured logs, and uploads declared outputs or CAS
   blobs back to the service.

The runner's responsibilities are intentionally narrow:

| Responsibility | What the runner does |
|---|---|
| Registration | Exchanges a one-time join token for a runner identity; rotates and revokes that credential on command. |
| Capability reporting | Reports available providers, CPU/memory/GPU classes, storage classes, isolation runtimes, max job size, and policy limits. |
| Job leasing | Pulls or receives typed Actions, accepts a lease, renews heartbeats, and lets the service requeue work when a lease expires. |
| Input materialization | Fetches or receives the declared input root, verifies content digests, and materializes `/ree` for the workbench. |
| Workbench lifecycle | Creates, reuses, suspends, or tears down the per-REE workbench via a provider adapter. |
| Command execution | Invokes `repo2ree-exec` inside the workbench with the typed Action; never runs arbitrary service-provided shell outside the workbench. |
| Logs and cancellation | Streams structured logs/spans, forwards cancellation and timeout signals, and records final status. |
| Output collection | Hashes declared `output_paths`, uploads blobs or OCI layers, and returns an `ActionResult` bound to the action digest. |
| Local policy | Enforces quotas, allowed images, network rules, secret mounts, retention, and garbage collection. |
| Audit | Records runner version, provider, workbench image digest, platform, policy decisions, and cleanup outcomes for receipts. |

Things the runner must not become:

- a general remote shell;
- a second implementation of `core`;
- a place where the hosted service can ask for arbitrary host filesystem access;
- a long-lived holder of broad cloud or cluster admin credentials;
- a channel that uploads local secrets, private package credentials, or kubeconfig
  material back to the service.

The provider interface underneath the runner should be explicit:

```
WorkbenchProvider:
  prepare(action, input_root, resources) -> WorkbenchHandle
  execute(handle, action, log_sink, cancel_signal) -> ActionResult
  collect(handle, output_paths) -> OutputInventory
  suspend(handle) | teardown(handle)
  describe_capabilities() -> RunnerCapabilities
```

Likely provider implementations:

| Provider | Target | Notes |
|---|---|---|
| `docker-local` | A Docker daemon on the runner machine | Matches today's workbench manager. |
| `docker-context` | A Docker context or SSH-backed daemon chosen by the user | Single-user CLI/offload path; the hosted service still never sees SSH material. |
| `kubernetes` | A namespace with scoped RBAC | Creates Pods/Jobs/PVCs and uses cluster policy for isolation and quota. |
| `cloud-vm` | A VM or node pool created by limited cloud IAM | Useful when repo2ree is allowed to provision compute but not hold login secrets. |
| `hpc-scheduler` | Slurm/PBS/LSF-style systems | Submits batch jobs that run the workbench image or a site-approved wrapper. |

This gives three supported delivery modes:

| Environment | Delivery | Credential boundary |
|---|---|---|
| Existing user server | `repo2ree runner install user@host` from a local CLI, using the user's own SSH agent | The local CLI sees SSH; the hosted service does not. |
| Cloud VM | Golden image with the runner preinstalled, or cloud-init that downloads a pinned/signed runner and starts systemd | User-data carries only a short-lived join token, never a private key. |
| University Kubernetes | Helm install of a runner/controller into an approved namespace | The cluster service account and kubeconfig stay inside the institution. |

For Kubernetes, the runner maps repo2ree concepts onto cluster primitives:

| repo2ree concept | Kubernetes shape |
|---|---|
| Runner | Deployment or controller in a single namespace |
| Runner authority | Namespace-scoped ServiceAccount and RBAC |
| REE workbench | Pod or StatefulSet plus PVC |
| `/ree` durable tree | PVC, CSI volume, or CAS-backed materialization |
| Experiment run | Job, or a pod launched by the workbench |
| Hardware requirements | requests/limits, node selectors, tolerations, GPU resources |
| Isolation | RuntimeClass such as Kata, gVisor, or KubeVirt where available |

Many clusters ban privileged Docker-in-Docker. A Kubernetes provider should
prefer rootless BuildKit, buildah, kaniko, or a VM-backed RuntimeClass, and use
privileged DinD only as an explicitly allowed fallback in a locked-down
namespace.

The service may store runner identity, capabilities, quotas, health, job
records, logs, and artifact digests. It must not store SSH passwords, SSH
private keys, passphrases, user cloud admin credentials, or kubeconfigs. Runner
credentials must be scoped, revocable, and tied to the owning tenant or
installation. This is what lets repo2ree run where the data lives while keeping
critical access material outside the hosted service.

#### P2P outlook: runners as verifiable rebuilders

The same runner shape can later support peer-assisted execution without turning
repo2ree into an unstructured file-sharing system. The unit of exchange is the
Action, not "some machine ran something":

```
action_digest
  -> ActionResult
  -> output digests / receipts / optional signature
  -> blobs or OCI layers in a content-addressed store
```

A future peer network would be a distributed action cache plus optional
rebuilders:

1. Before provisioning a local workbench, ask known peers or a discovery layer
   whether `action_digest` already has a result.
2. If there is a hit, fetch the `ActionResult` and output blobs by digest.
3. Verify the digests locally. For higher assurance, re-run the same Action on a
   trusted runner and compare outputs.
4. If there is a miss, run locally and publish the resulting cache entry,
   possibly signed by the runner or institution.

This splits P2P into layers:

| Layer | Meaning | Trust model |
|---|---|---|
| Artifact distribution | Fetch blobs, OCI layers, or bundles from peers | Trust hashes, not peers. |
| Action cache | Reuse an `ActionResult` for an exact action digest | Trust only after digest verification; stronger with signatures. |
| Rebuilder network | Independent runners re-execute important Actions | Trust improves when independent outputs match. |
| Discovery/identity | Find peers and bind them to keys/institutions | Optional and heavy; not needed for the first runner design. |

The runner design preserves this option because the runner already leases typed
Actions, reports platform capabilities, returns digest-bound results, and can
sign or attest what it ran. P2P should remain an outlook until repo2ree has CAS,
stable action digests, and enough receipts for "peer result" to mean something
verifiable.

### The wire form: a typed action envelope

The envelope mirrors the [Bazel Remote Execution API](https://github.com/bazelbuild/remote-apis)
(REAPI) shape — three layered messages shared by `protocol`, `api`, `supervisor`,
and `repo2ree-exec`, whose digests compose into one identifier for the build:

```
Command {
  operation:       build_runtime | generate_sbom |
                   evaluate_dependency_score | run_experiment
  args:            typed-per-operation
  workbench_image: digest                # workbench is itself part of repro
  output_paths:    [paths in artifacts/ to capture]
}

InputRoot = Merkle directory digest over the *projected* inputs:
  workspace/ + the per-operation slice of overlay/

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
1. api projects manifest → overlay; snapshots inputs into CAS
2. core assembles Command + Action → computes action_digest
3. lookup action_digest in ActionCache
     hit  → return recorded ActionResult; fetch output blobs on demand. Done.
     miss → dispatch Action to repo2ree-exec
4. executor materializes input_root from CAS, runs the op against workbench dockerd,
   uploads each output_path to CAS, records the ActionResult
```

Why this matters for reproducibility:

- **Action digest as receipt.** "Action `sha256:abc...` over inputs
  `sha256:def...` on platform `kata-...`" names the build exactly.
- **Correct invalidation.** Editing an experiment overlay does not rebuild the
  runtime unless the `build_runtime` action changes.
- **Real reproducibility test.** Re-execute the action and compare output
  digests; this tests reproducibility, not packaging.
- **Shared REE by substitution.** Multiple machines pull artifacts by digest,
  in the Nix binary-cache shape.
- **Dedup and cancellation.** Concurrent identical Actions coalesce on
  `action_digest`; cancellation only signals the executor when no waiter
  remains.

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
compute `action_digest` deterministically across `protocol`, `core`, `api`, and
`executor`. (2) Trivial host-side CAS (`blobs/<sha256>`, SQLite ActionCache).
(3) OCI registry for runtime images. Distributed cache, signing, chunking, and
GC are deferrable — they're bolt-on once the envelope is right.

### Two rules this imposes

1. **Assemble commands server-side, never in the GUI.** The GUI sends
   structured *declarations/intent* (it's FCIS — intent is just data); a **pure
   core function** translates intent → concrete command; the working env runs it.
   Letting the browser hand raw command strings to a VM is an injection straight
   into the execution plane.
2. **Core has two consumption modes.** This sharpens the existing thin-api
   layering rather than breaking it:
   - **Library, host-side** — only the *pure* bits: intent→command assembly,
     spec/overlay validation. Keep this surface small; route execution through
     supervisor + protocol.
   - **Executor, in-workbench** — all *effectful* bits: build, run, score, sbom.

   Discipline: *touches docker/fs/network → executor in workbench; pure
   translation/validation → library host-side.*

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
| Seal Manifest                    | Canonical digest inventory for the REE                         | Inline in the bundle                  | Names the exact sealed object                                     |
| Signatures                       | Typed claims over the seal digest                              | Inline or sibling attestations        | Append-only; may arrive after deposit                             |
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
├── overlay/                  # repo2ree's contribution to the source
├── source/                   # usually empty: a SWHID pointer in metadata.
│                             # Inline bytes only in Draft state (no SWHID).
├── receipts/                 # Run Receipts with predecessor links
├── label/                    # the Repro Label snapshot at deposit time
├── seal/
│   ├── seal-manifest.json    # canonical inventory; hashed to ree_digest
│   └── signatures/           # detached attestations over ree_digest
└── artifacts/                # populated by fidelity tier (see below)
    ├── runtime-image.tar     # Replay+
    └── inputs-closure/       # Rebuild only
```

### Seal manifest and signatures

`seal-manifest.json` is the content identity of the REE. It records the digest
of each sealed component: source identity, overlay tree, Label, Receipts,
runtime artifact for Replay+, and dependency closure for Rebuild. The
`ree_digest` is the digest of the canonical manifest.

Signatures are excluded from the manifest digest. Each signature is a typed
statement over `ree_digest` with signer role, policy, timestamp evidence, and
verification material. This prevents a recursive hash and lets author,
executor, reviewer, institution, and archive signatures arrive at different
times.

Long-term archival requires timestamp evidence and algorithm identifiers. If a
hash algorithm ages out, add a digest-migration attestation that binds the old
digest to a new digest over the same manifest instead of rewriting history.

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
| **Sealed**         | Seal Manifest and `ree_digest` exist; edits create a new seal | Yes — content identity is stable                                      |
| **Deposited**      | Bundle deposited/exported; DOI/PID and SWHIDs recorded when available | Already archived; future deposits create new versions                     |

Promotion Draft → Archive-ready happens when the source acquires a stable
identifier, usually through a forge already crawled by Software Heritage or an
explicit SWH save/deposit request.

### What repo2ree does not do

- **Run a permanent archive.** Bundles live on Zenodo, Dataverse, or
  institutional repositories; source lives in Software Heritage when available;
  PIDs come from DataCite or PID4NFDI.
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
  one; the later switch to a hardened workbench becomes a transport change, not a
  protocol change. See
  [Content-addressed state](#content-addressed-state-cas-and-the-action-cache).
- **Establish the `/ree` layout on first provisioning** (not REE creation — see
  [State ownership](#state-ownership-declarative-manifest-vs-durable-tree)).
  The persistent workbench path already lays down `upstream/`, `overlay/`,
  `workspace/`, `artifacts/`, and `runs/`. Keep review/legacy paths converging on
  the same layout.
- **Remote the existing job model; don't reinvent it.** *(Done.)* The
  submit→stream→cancel async-job shape lives in
  [`RunRegistry`](../api/src/repo2ree_api/control/run_registry.py), fronted by
  `start_background_run` / `run_summary` / `is_cancel_requested`, plus the
  `start_provisioning_run` / `start_single_command_run` shapes
  ([control/run_orchestration.py](../api/src/repo2ree_api/control/run_orchestration.py)).
  Operations dispatch to `repo2ree-exec` through
  `WorkbenchManager.dispatch_action` with logs streamed back, and cancellation
  crosses the boundary as a remote signal to the agent
  ([manager.py:287](../supervisor/src/repo2ree_supervisor/manager.py#L287))
  rather than a local flag check.
- **Keep Docker image construction inside the workbench.** The main build path
  now reaches `core` through `repo2ree-exec` inside the workbench. Any remaining
  direct host-side Docker build paths should be treated as legacy/review code and
  migrated behind the same command envelope.
- **`WorkingEnvironmentSpec` gains fields:** `runtime` (`kata`/`runc`), the
  workbench `image`, and `resources` (CPU/mem) — the latter fed by the existing
  experiment resource-estimate fields, which now double as **workbench sizing**.
- **Harden `WorkbenchManager.provision()`.** Today it launches a privileged
  Docker-in-Docker workbench. The target is the same `/ree` volume and command
  envelope under a Kata/Sysbox-backed runtime, without relying on a privileged
  shared-kernel container.

## Open decisions

- **Runtime-image source for experiment runs.** With one workbench per REE,
  build and runs share the same workbench `dockerd`, so `run-experiment` can use the
  just-built image directly (fast). Optionally re-`docker load` it from the
  saved runtime tar first — the pattern the author-owned run scripts already
  use — to prove the image is self-contained. Once the action cache is in
  place ([above](#content-addressed-state-cas-and-the-action-cache)) the
  stronger check is re-executing the build Action and asserting output digests
  match — that tests reproducibility, not just packaging. Recommend fast by
  default; strict = action re-execution.
- **Workbench persistence model.** The durable REE state is the `/ree` tree, not
  the running container/VM. Standing-workbench-per-REE is simplest but costly at
  scale; rehydrate-on-demand
  (persist the tree, recreate the workbench when an REE is opened) bounds cost.
  Recommend rehydratable, with the tree as source of truth. *First* provisioning
  is likewise lazy — deferred to the first execution-needing operation — so an REE
  that is only being declared/edited costs no workbench (see
  [State ownership](#state-ownership-declarative-manifest-vs-durable-tree)).
- **KVM availability in the deployment target** decides Kata vs. the Sysbox
  fallback.
