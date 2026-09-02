# repo2ree — Component and Package Architecture Reference

> **Status: partially implemented + target rules (2026-08).** The
> code-organization companion to [architecture.md](architecture.md). It maps
> the runtime model onto source packages, deployment locations, and dependency
> rules. For concepts see [concepts.md](concepts.md); for product framing see
> [research/POSITIONING.md](../../research/POSITIONING.md).

## Mental model

repo2ree is a **control plane driving an isolated execution plane over a typed
command protocol**; see
[Control plane / execution plane split](architecture.md#control-plane--execution-plane-split).
Three invariants shape every package boundary below:

1. **An REE is built inside a workbench (a "bench").** The main path provisions
   a per-REE Docker-in-Docker bench and dispatches typed commands into it. The
   target is a stronger VM-backed bench.
2. **The control plane never touches a container runtime.** A separate
   deployable — the *provider* — owns the runtime on its host, dials the control
   plane outbound, and creates benches on the control plane's behalf. Swapping
   the substrate (local Docker today; Kubernetes or HPC later) is a swap of
   provider, not of protocol or commands.
3. **Capacity and execution never share a connection.** The provider offers
   capacity and can never run an REE command; the *workbench service* resident
   in each bench runs commands and can never create or destroy infrastructure.
   Both dial the control plane outbound, on separate sockets with separate
   credentials.
4. **The bench image carries no repo2ree content.** The provider injects the
   executor and its base tools (content-addressed nix closures) into whatever
   env image the bench boots from, so any image that keeps a process alive and
   has a writable `/ree` can be a bench — the default is upstream `docker:dind`.
   See [the env image](architecture.md#the-workbench-env-image).

These are separate deployable units joined by two protocols: the host-side
control plane, the runtime-owning provider, and — inside each bench — the
workbench service with its short-lived executors.

## The decomposition: libraries + surfaces + the two compute-side deployables

**Libraries do the work. Surfaces are thin adapters that expose a library at a
boundary.** Surfaces own *no* logic — they translate (argv / HTTP / stdin) into
a library call and shape the result back. The **provider** and the **workbench
service** are a third kind: deployables that sit on the execution-plane host,
one holding the runtime socket and one living inside the bench.

```
                              protocol      ← the contract (Command / ActionResult / LogFrame)
                 ┌───────────┬────┴────┬────────────┐
              core        provider  workbench    supervisor
                │        (capacity) (execution)  /        \
          ┌─────┴────┐                      ┌───┴────┐  ┌──┴───┐
          │ executor │                      │repo2ree│  │ api  │   ← surfaces
          │ (in bench)                      │(future │  │(http,│
          │          │                      │  cli)  │  │ opt.)│
          └──────────┘                      └────────┘  └──────┘

  LIBRARIES (logic)             SURFACES (entry points)      COMPUTE SIDE
  ─────────────────             ───────────────────────      ────────────
  protocol   the wire contract  executor  in-bench, one-shot  provider  holds the docker
  core       does the work      repo2ree  future host cli               socket, creates
  supervisor placement+dispatch api       host http, optional           benches, injects
                                                              workbench runs one executor
                                                                        per command
```

### Libraries

| package | responsibility | depends on | deployed |
|---|---|---|---|
| **protocol** | the typed `Command` / `ActionResult` / `LogFrame` envelope + (de)serialization (`command_adapter`), **and** the two wire schemas: execution (`WorkbenchWsRequest` / `WorkbenchWsMessage` / `WorkbenchRef`) and capacity (`ProviderWsRequest` / `ProviderWsMessage`). The things the sides must agree on. | — | host, provider **and** bench |
| **core** | does the actual work — the command handlers (`build-runtime`, `generate-sbom`, `evaluate`, `run-experiment`), the `doctor` bench probe, the tool resolver (`execution/tools.py`), and the workspace/REE/`/ree`-tree operations. Pure library; **no CLI framework deps**. | protocol | **bench only** |
| **supervisor** | the control plane: REE **lifecycle** (provision / teardown) expressed as capacity calls, the **registry** (`ree_id → workbench + opaque location`), single-use **enrollment**, and the **dispatch** that sends commands to a workbench and streams logs/results back. Two seams with different authority — `ProviderClient` and `WorkbenchClient`. Never executes a command, and never touches a container runtime, itself. | protocol | host only |

### The compute side (two deployables)

| package | responsibility | depends on | deployed |
|---|---|---|---|
| **provider** (`repo2ree-provider-docker`) | owns the container runtime on its host (`DockerIsolation` behind an `IsolationBackend` protocol). Dials the control plane on a **capacity-only** socket. Creates volumes and benches, injects the executor + tools closures, mints the opaque `WorkbenchRef`, runs the `doctor` probe, and starts `repo2ree-workbench` inside each bench with a single-use enrollment token. Never receives an REE command. | protocol, docker-support | its own host (holds the docker socket) |
| **workbench** (`repo2ree-workbench`) | the service resident *inside* each bench. Dials the control plane on its own **execution-only** socket, enrolls against one allocation, decodes typed commands, starts one short-lived executor per command (`LocalExecutor`), streams frames, and moves files. Deliberately substrate-free; cannot create or destroy anything. | protocol | inside each bench |
| **docker-support** | the shared Docker CLI wrapper and reference encoding. No process authority of its own. | protocol | with the provider |

### Surfaces

| surface | over | role | deployed |
|---|---|---|---|
| **executor** (`repo2ree-exec`) | core + protocol | one-shot: read a `Command` on stdin, run it via core, stream `LogFrame`s on stderr, emit `ActionResult` on stdout, exit. **No listening server.** Injected by the provider, so it ships with the provider — not baked into the bench image. | **bench only** |
| **`repo2ree`** (supervisor cli) | supervisor + protocol | **target host surface.** Drive the pipeline against a bench, stream logs, pull artifacts, tear down. | host — *not implemented yet* |
| **api** (http) | supervisor + protocol | **optional** hosted UX over the supervisor (what the GUI talks to; remote/multi-user access). | host |

## Dependency rules (the invariants that keep the seam clean)

These are the rules a dependency-cruiser / import-linter config should enforce
as the migration finishes:

1. **The host should not import effectful `core`.** `supervisor` and the future
   host CLI depend on `protocol` only. `api` still imports a few `core` domain
   and storage helpers today; keep shrinking that surface until execution logic
   lives exclusively in the bench.
2. **Surfaces import their library, never each other.** `api` and `repo2ree`
   are sibling surfaces over `supervisor`. No `cli -> api` or `api -> cli` edge.
3. **`protocol` depends on nothing.** It is the seam; it must stay importable by
   every side without dragging any side's logic along.
4. **`core` carries no CLI/HTTP framework deps.** It is a pure library so it can
   also be imported by the in-process *test* transport (below) without cost.
5. **Neither compute-side package imports `core`.** The provider places benches
   and *injects* the executor closure; the workbench service starts that
   executor. Neither runs command logic itself, which keeps execution logic on
   the far side of the bench boundary.
6. **The provider never executes and the workbench never provisions.** These are
   not conventions: `pyproject.toml`'s import-linter contracts fail the build on
   either edge, alongside "Capacity and execution vocabularies are independent".

Resulting DAG (acyclic, and the only cross-boundary edge is the protocol):

```
protocol ← core ← executor                       (execution plane, in the bench)
protocol ← workbench                             (in the bench; runs the executor)
protocol ← docker-support ← provider             (runtime host; creates benches)
protocol ← supervisor ← { repo2ree(cli), api }   (control plane)
```

## Call graph — what is and isn't a process boundary

A common misread is that the `api` shells out to the supervisor cli. It does
not. `api` and `repo2ree` are sibling surfaces that both import the
`supervisor` library in-process. The runtime lives one hop further out, behind
the bench: the supervisor speaks two wire protocols, and the process that starts
the executor lives inside the bench itself.

```
                             ┌─ws(capacity)─► provider ──docker──► creates the bench
gui ───────http──► api ──┐   │                (ProviderClient)
                         ├─► supervisor
host user ─► repo2ree ──┘    │                (WorkbenchClient)
              (sv-cli)       └─ws(execution)─► workbench ──spawn──► executor ─► core
                                              (in the bench)      (in the bench)
        ▲ both call supervisor as a Python library, in-process ▲
                       ▲ both sockets cross the network to the compute side ▲
```

Four hops, only the outer ones cross a boundary:

| hop | kind | why |
|---|---|---|
| `api` / `repo2ree` → `supervisor` | **in-process function call** | same machine, same process — `supervisor.provision(...)`, `supervisor.dispatch(cmd, ...)`. No subprocess. |
| `supervisor` → `provider` | **network / wire** (`ProviderClient` over one **provider-dialed** WebSocket; typed `ProviderWsRequest` / `ProviderWsMessage`) | crosses **to the runtime-owning host** to obtain and release capacity. Carries no REE command, ever. |
| `supervisor` → `workbench` | **network / wire** (`WorkbenchClient` over one **workbench-dialed** WebSocket; typed `WorkbenchWsRequest` / `WorkbenchWsMessage`) | crosses **into the bench**. Both sides dial outbound, so this works from inside clusters and NATed networks that only allow egress — no inbound port on either. |
| `workbench` → `executor` | **subprocess** (`Command` on stdin, one short-lived process per command) | stays inside the bench, but crosses the process boundary that keeps `core` out of the resident service. |

The two wire hops are the "cross a boundary" paths, and they are deliberately
separate: capacity credentials cannot run commands, and workbench credentials
cannot allocate infrastructure. Everything left of `supervisor` is a function
call. In hosted mode, `api` may pass through the
[service tier](#the-service-tier--multi-user-persistence-auth-hosted-only) first,
still in-process.

## The two CLIs — why, and how to name them

repo2ree has **two** command-line tools because it has two execution contexts,
and conflating them is the mistake to avoid:

| | runs | reads | job | user-facing? |
|---|---|---|---|---|
| **`repo2ree`** (supervisor cli) | on the host | argv | drive workbenches | **yes — this is what `pip install` gives you** |
| **`repo2ree-exec`** (executor) | inside the bench (provider-injected) | a `Command` on **stdin** | execute one command, exit | no — bench-internal |

The friendly name `repo2ree` belongs to the future host cli. The implemented
guest piece is the stdin-driven `repo2ree-exec`: started per command by the
workbench service, executes once, emits a result, exits. Avoid `server`/`daemon`
and bare `cli`; each is ambiguous here. Two more deployables carry the compute
side and are not CLIs at all: `repo2ree-provider-docker` and
`repo2ree-workbench`.

## Always isolated, location configurable

Isolation is fixed; *which provider owns the substrate* is the knob. The control
plane never holds a docker socket — capacity comes from the provider that
created a bench, so "local vs remote" is a matter of *where the provider runs*,
not a second transport to write:

- **The provider owns the runtime; the control plane owns intent.** A provider
  runs next to the docker host (or a future cloud/HPC substrate), dials the
  control plane outbound, and reports its identity. Provision pins the REE to
  the concrete provider it lands on (`ProviderClient.resolve_provider`) and to
  the workbench that provider creates; every later command routes to that same
  workbench.
- **Handle resolution goes through the provider, not `docker inspect`.** Because
  the control plane has no socket, it cannot inspect containers directly: it
  records `ree_id → (allocation_id, workbench_id, WorkbenchRef)` in a persisted
  registry (`WORKBENCH_REGISTRY_FILE`) and asks the provider for run-state
  (`is_running`). The bench's container name is still deterministic *on the
  provider's host* (`repo2ree-wb-{ree_id}`), but that name is the provider's
  private vocabulary, carried inside the opaque `WorkbenchRef` — the control
  plane never interprets it.
- **The iterate loop stays fast despite always-isolated.** The bench is
  persistent: provision once (the image's own default process keeps it alive —
  `dockerd` on dind — with a pause command only as the rescue for images whose
  default exits immediately; `restart unless-stopped` is applied *after* the
  bench proves viable), then one executor per command inside the standing bench,
  tear down at the end.
- **A connected provider is the hard requirement for creating an REE, and a
  connected workbench for running one.** An environment with neither cannot run
  the product.

The remote case is a **registered provider inside the user's boundary**, reached
outbound-only — not the control plane holding SSH keys or a kubeconfig. In
hosted mode repo2ree should not receive SSH passwords, private keys, cloud admin
credentials, or kubeconfigs; cloud and university resources are reached through
a registered provider inside the user's boundary. See
[Remote execution clients](architecture.md#remote-execution-clients-user-owned-runners).

## What runs continuously — deployment modes

The supervisor is a **library, not a daemon** — whether anything "runs
continuously" is a property of the *surface that hosts it*. But note where the
always-on process moved: because the control plane has no docker socket, the
long-running runtime host is now the **provider**, and the control plane keeps a
small **persisted registry** (it cannot reconstruct bench state from `docker
inspect` the way a socket-holding supervisor could):

| state | owned by |
|---|---|
| the bench fleet (containers + volumes) | **docker on the provider's host** — a long-running daemon (`restart unless-stopped`, applied once a bench is viable) |
| the runtime host that creates the fleet | **the provider** — a continuously-running process holding the socket and one outbound capacity WebSocket |
| the process that drives one bench | **the workbench service** — resident inside that bench, holding its own outbound execution WebSocket |
| the registry (`ree_id → allocation_id + workbench_id + WorkbenchRef`) | **persisted by the control plane** (`WORKBENCH_REGISTRY_FILE`) — the opaque reference is minted by the provider and cannot be re-derived host-side |
| long-running jobs (a build is minutes) | **the bench itself** — run inside the bench, write logs/result to `/ree`, stream frames back over the workbench connection. Each bench is a per-REE continuous process. |
| the versioned manifest (optimistic concurrency) | the **service tier's DB** (below); moot in single-client cli mode |

Two modes follow:

| mode | the continuous processes | supervisor |
|---|---|---|
| **cli / single host** | docker + benches + one provider | ephemeral library, in-process per command — *no control-plane service to run, but a provider must be up* |
| **hosted / multi-user** | **the `api`** (a long-lived server) **+ one or more providers** | same library, hosted in-process by the api → effectively continuous; fleet background work (idle-TTL GC, health, orphan cleanup) is a background task *inside the api process* |

A separate supervisor daemon would break the zero-service CLI flow and add an
unnecessary IPC hop. The provider is different: it runs on the execution host and
owns the substrate that the control plane must not hold.

Introduce a standalone control-plane worker only when fleet-wide work, such as
global quotas or cross-host draining, must outlive request handling. That worker
should import the supervisor library, not reimplement it.

## The service tier — multi-user, persistence, auth (hosted only)

The base is **3 libraries + 3 surfaces**. A multi-user *hosted* deployment adds
one library tier **on top of** the supervisor — strictly additive, and the cli
path never touches it. Identity/tenancy is **neither a `core` nor a `supervisor`
concern**: core executes commands, the supervisor places a workbench *for an
opaque `ree_id`* (tenant-agnostic, so the single-user cli can reuse it). The
service is the layer that knows about **people**.

```
protocol ─ core ─ executor                         execution plane (in the bench)
protocol ─ supervisor                              placement + dispatch (tenant-agnostic)
              └─ service   ← DB · identity · tenancy · policy · use-cases   [HOSTED ONLY]
                    └─ api (thin HTTP surface)  ──  gui

   repo2ree (cli) ──────────► supervisor           ← bypasses the service tier entirely
```

It maps "*user U acts on REE R*" → authenticate → authorize (ownership/ACL) →
call `supervisor.dispatch(resolved_ree_id, …)`. Consequences:

- **`api` stays thin.** It does HTTP transport + **auth *enforcement* at the
  edge** (verify the token). The *policy* (what this identity may do) lives in
  `service`. Routes are a shell over service use-cases.
- **The DB holds control-plane + ownership metadata, never execution state.** It
  *indexes and points at* the fleet (docker) and the `/ree` tree (volumes) —
  it does not hold REE artifacts.

| in the service DB | stays where it is |
|---|---|
| users, orgs/tenants, memberships | bench fleet → docker |
| REE ownership / ACL / sharing (`ree_id → tenant`) | `/ree` tree + artifacts → the volume |
| versioned manifest (optimistic concurrency) | CAS blobs → its own store, if/when |
| run history / audit log / job records; quotas / usage | |

Two judgment calls baked in:

1. **Auth is a pluggable boundary, not a bespoke system.** Build a seam
   (verify token → identity, OIDC/SSO-friendly) with a default impl — don't
   hand-roll a user/password store deployments can't swap.
2. **Tenancy stays out of the supervisor.** Enforce it in the service ACL layer;
   keep `ree_id`s globally-unique opaque ids (the provider derives its own flat
   container name, `repo2ree-wb-{ree_id}`, from that id inside the opaque
   `WorkbenchRef`). If the supervisor learns about tenants it stops being
   reusable by the cli.

DAG rule extends cleanly: `service → supervisor → protocol`, and **`service`
never imports `core`.** Packaging is non-dogmatic — a well-bounded `service`
*module* inside `api` (routes thin over it) is a fine start; promote to its own
package when a second surface needs the same use-cases. None of this is needed
for the cli/local flow or a first single-tenant deployment.

## Distribution

The executor no longer ships as a bench image. It is a nix closure carried by
the **provider** and injected at provision time, so the units to distribute are
the control plane, the provider, and an env image that carries *no* repo2ree
content.

| audience | installs / pulls |
|---|---|
| control-plane host | `api` (and the GUI it serves) + `supervisor` + `protocol` |
| runtime host | the **provider image** (`repo2ree-provider-docker`): the provider process plus the workbench, executor, and tools closures it injects (`protocol` + `core` + `executor` + `workbench`, bundled — never `supervisor` / `api`) |
| env image (the bench) | any image that keeps a process alive with a writable `/ree`; **zero repo2ree content** — the default is upstream `docker:dind`, pinned by digest in the catalog |

Because the workbench, executor, and tools **version with the provider, not the
env image**, there is no separately-installed executor to skew against: pull a
newer provider image and every bench it creates runs the matching pair.

Two things pin what produced an REE, and both are content addresses: the env
image (`Command.workbench_image: digest` — see
[the wire form](architecture.md#the-wire-form-a-typed-action-envelope)) *and* the
injected executor/tools closures (content-hashed nix store paths). Pinning both
pins the environment that produced the REE. See
[the env image](architecture.md#the-workbench-env-image).

## Test layout

Three seams can be isolated independently. The control plane depends on
`ProviderClient` (capacity) and `WorkbenchClient` (execution); the provider
depends on `IsolationBackend` (provider → substrate). Each has one production
impl and, where useful, a test fake:

| seam | production | test | docker? |
|---|---|---|---|
| `ProviderClient` (control plane → provider) | `WsProviderClient` (one outbound WebSocket) | in-memory fake client | no |
| `WorkbenchClient` (control plane → workbench) | `WsWorkbenchClient` (one outbound WebSocket) | in-memory fake client | no |
| `IsolationBackend` (provider → substrate) | `DockerIsolation` (local docker socket) | — | yes (real) |
| `in-process` (run `core` directly on a temp `/ree`) | — | test transport | no |

Unit suites use those seams for fast, daemon-free checks. Integration and GUI
e2e suites deliberately exercise the real provider and Docker bench path.

```
protocol/tests/      unit: envelope + frame (de)serialization round-trips
core/tests/          unit + integration: command handlers, /ree ops, doctor, tooling
provider/tests/      unit: DockerIsolation lifecycle, injection, and probe logic
workbench/tests/     unit: connection, dispatch, executor frames, transfers
supervisor/tests/    unit: registry; manager/dispatch w/ both clients faked
                     integration: real provider + DockerIsolation + injected executor
api/tests/           unit: routes/orchestration with fakes
                     integration: real FastAPI + provider + Docker benches
gui/tests/e2e/       real browser flow against the API + provider stack
```

`gui/tests/e2e/helpers/flow.ts` factors the common UI flow. The API integration
suite covers the corresponding HTTP lifecycle. A future host CLI should reuse
the same sequence (acquire → build → evaluate → experiment → seal).

## Relationship to today's code

The package split is now largely real:

- **Done:** `protocol/` holds the typed command/result/log/tracing contract
  **and** both wire schemas — execution (`workbench.py`) and capacity
  (`provider.py`) — kept independent by contract.
- **Done:** `supervisor/` holds `WorkbenchManager`, the persisted registry,
  single-use enrollment, and the separate `ProviderClient` / `WorkbenchClient`
  seams — it dispatches over the wire and touches no runtime.
- **Done:** `provider/` holds the runtime host: the `IsolationBackend` protocol,
  its sole `DockerIsolation` impl (bench lifecycle, executor injection, the
  `doctor` probe), and its capacity WebSocket loop.
- **Done:** `workbench/` holds the in-bench service: its execution WebSocket
  loop, the dispatcher, chunked transfers, and `LocalExecutor`. It contains no
  provisioning code, and the import contracts enforce that.
- **Done:** `executor/` provides `repo2ree-exec`, the in-bench command runner,
  now injected by the provider rather than baked into a bench image.
- **Done (interface):** each transport is an interface with one impl —
  `ProviderClient` → `WsProviderClient`, `WorkbenchClient` → `WsWorkbenchClient`,
  `IsolationBackend` → `DockerIsolation` — not a single hardcoded local-Docker
  path. Additional providers (Kubernetes, HPC) are the intended next impls.
- **Done:** the dependency rules above are machine-enforced. `[tool.importlinter]`
  in [pyproject.toml](../../../pyproject.toml) carries workspace-level layers, per-package
  layer contracts for `api` and `core` (both marked exhaustive, so a new top-level
  module must declare its tier), and independence contracts holding the author and
  review sides apart in both `core.operations.handlers` and `api`.
- **Still rough:** `api` imports `core` domain and evidence *types* directly
  (`Ree`, `ReviewRecord`, aggregate assessments, the step graph) rather
  than through `protocol`, and owns hosted UX concerns directly.
- **Missing:** the user-facing host `repo2ree` supervisor CLI does not exist yet.

## Future surfaces — what the seams enable (optional, driver-gated)

> Not roadmap. This records what the existing seams *already make possible*, so
> a future driver doesn't trigger a redesign. **Don't build any of this without a
> concrete driver** (YAGNI). A good architecture makes new surfaces cheap; the
> test is that each item below drops onto an interface that already exists and
> touches **neither `core`, `supervisor`, nor the protocol**.

"P2P" is not one surface — it conflates three independent axes, each landing on
a different existing seam, each separately optional:

| axis | meaning | seam it reuses | verdict |
|---|---|---|---|
| **distribution** | fetch finished REEs from any peer | the artifact / CAS store interface | commodity — hermetic + content-addressing already suffices |
| **execution** | run a build on a peer's bench | the `ProviderClient` / `WorkbenchClient` seams | the *differentiated* one — enabled by reproducibility |
| **discovery / identity** | DHT + keys instead of the central `service`/DB | an alternative to the service tier | heaviest; usually unnecessary |

The hosted-client version of this is the registered runner described in
[Remote execution clients](architecture.md#remote-execution-clients-user-owned-runners):
it leases typed Actions, runs them through a local provider, and returns
digest-bound `ActionResult`s. A peer execution surface would reuse that same
shape with a different discovery and trust layer.

### The distributed action cache (the core idea)

The envelope is [REAPI-shaped](architecture.md#the-wire-form-a-typed-action-envelope),
and REAPI is *already* a protocol for distributed execution **and caching**. The
P2P-native object is therefore not "the REE" — it's the **action cache entry**:

```
command_digest  →  (ActionResult, output artifacts)     content-addressed · signed · verifiable
```

where `command_digest` folds in the source digest, the args, **and the
`workbench_image` digest** (so the cache key already pins what produced the
result). This collapses "distribution" and "execution" into one mechanism:

- A peer that already ran the *exact* `Command` can serve the cached
  `ActionResult` + artifacts. You **verify by digest** — you don't trust the
  peer, you trust the hash.
- "P2P" concretely = **a distributed action cache** (a DHT/gossip front over the
  same content-addressed store), optionally backed by **rebuilders**.

The build pipeline therefore gains one lookup before it provisions a bench: *ask the
network whether `command_digest` is already satisfied.* Hit → fetch + verify,
skip the build. Miss → build locally, publish the new entry. Same `Command`, same
`ActionResult`; the network is just a cache tier in front of the supervisor.

### Hermeticity enables P2P execution

- **Distribution:** a content-addressed REE is fetch-and-verify from any backend
  (OCI registry, S3, IPFS, BitTorrent). Keep the artifact store pluggable; add a
  P2P backend only when needed.
- **Execution:** hermeticity is the precondition for trustless remote work. A
  peer's result is useful only because it can be re-run and compared by digest,
  in the Nix rebuilder / Bazel RBE shape.

The two properties already built are exactly the two security primitives P2P
needs: **content-addressing** makes distribution trustless (verify the artifact
by hash); **sandbox + reproducibility** makes execution safe (run the peer's
command in *your own* workbench) *and* verifiable (re-run, compare digests).

### Where each axis plugs in

- **distribution** → an impl of the artifact/CAS store interface (in the
  `service` tier / CAS layer). No change to core, supervisor, or protocol.
- **execution** → another `IsolationBackend` impl (a *peer* substrate alongside
  `DockerIsolation`), or a peer `ProviderClient`, **+** a verification step that
  re-runs via `core` and digest-compares. The capacity and execution seams are
  what make this free.
- **discovery / identity** → an alternative realization of the `service` tier
  (DHT + cryptographic identity) — only if the *goal itself* is a decentralized
  public network.

The one slice worth watching, because it's unique to a reproducibility product:
the **verifiable action cache / rebuilder**. That's where P2P stops being
commodity file-sharing and becomes something only this tool can credibly offer.

## Open decisions

- **Package names:** `protocol` vs `envelope` vs `wire`; `supervisor` vs
  `control`. (Doc uses `protocol` / `supervisor`.)
- **Executor home:** thin separate package vs an entrypoint on `core`. This doc
  recommends *separate*, to keep `core` framework-free.
- **Sequencing:** *(largely resolved)* `supervisor` is extracted, and capacity
  and execution are separate seams with the provider as the runtime host. What
  remains sequenced behind this is the user-facing `repo2ree` cli and additional
  `IsolationBackend` impls (Kubernetes, HPC).
- **Service tier home:** a bounded `service` module inside `api` vs its own
  package. Defer until a second surface needs the same use-cases.
- **Auth scheme:** the default identity provider behind the pluggable auth seam
  (OIDC? local dev token?). Out of scope until the first multi-user deployment.
- **P2P / distributed action cache:** explicitly *non-goal* until a concrete
  driver. Tracked only as "preserved option" — the action-cache key
  (`command_digest`) and the artifact/CAS + `ProviderClient`/`WorkbenchClient`
  interfaces are the seams that keep it free.
