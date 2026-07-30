# repo2ree — Component & Package Architecture

> **Status: partially implemented + target rules (2026-06).** The
> code-organization companion to [ARCHITECTURE.md](ARCHITECTURE.md). It maps
> the runtime model onto source packages, deployment locations, and dependency
> rules. For concepts see [CONCEPTS.md](CONCEPTS.md); for product framing see
> [research/POSITIONING.md](research/POSITIONING.md).

## Mental model

repo2ree is a **control plane driving an isolated execution plane over a typed
command protocol**; see
[Control plane / execution plane split](ARCHITECTURE.md#control-plane--execution-plane-split).
Three invariants shape every package boundary below:

1. **An REE is built through a workbench (a "bench").** The main path provisions
   a per-REE Docker-in-Docker bench and dispatches typed commands into it. The
   target is a stronger VM-backed bench.
2. **The control plane never touches a container runtime.** A separate
   deployable — the *agent* — owns the runtime on its host, dials the control
   plane outbound, and drives the bench on the control plane's behalf. Swapping
   the substrate (local Docker today; a cloud/Kubernetes/HPC runner later) is a
   swap of agent, not of protocol or commands.
3. **The bench image carries no repo2ree content.** The agent injects the
   executor and its base tools (content-addressed nix closures) into whatever
   env image the bench boots from, so any image that keeps a process alive and
   has a writable `/ree` can be a bench — the default is upstream `docker:dind`.
   See [the env image](ARCHITECTURE.md#the-workbench-env-image).

These are separate deployable units joined by one protocol: the host-side
control plane, the runtime-owning agent, and the in-bench executor.

## The decomposition: 3 libraries + surfaces + the agent

**Libraries do the work. Surfaces are thin adapters that expose a library at a
boundary.** Surfaces own *no* logic — they translate (argv / HTTP / stdin) into
a library call and shape the result back. The **agent** is a fourth kind: a
runtime-owning deployable that sits on the execution-plane host between the
control plane and the bench.

```
                       protocol            ← the contract (Command / ActionResult / LogFrame)
                    /      |       \
                core    agent      supervisor
                  │    (runtime      /       \
          ┌───────┴──┐   host)   ┌───┴───┐  ┌──┴───┐
          │ executor │           │repo2ree│  │ api  │   ← surfaces
          │  (guest) │           │(future │  │(http,│
          │          │           │  cli)  │  │ opt.)│
          └──────────┘           └────────┘  └──────┘

  LIBRARIES (logic)            SURFACES (entry points)         AGENT (runtime host)
  ─────────────────            ───────────────────────         ────────────────────
  protocol   the wire contract executor  guest, in-image        owns the container
  core       does the work     repo2ree  future host cli        runtime; dials the
  supervisor lifecycle+dispatch api       host http, optional    control plane; injects
                                                                 the executor into benches
```

### Libraries

| package | responsibility | depends on | deployed |
|---|---|---|---|
| **protocol** | the typed `Command` / `ActionResult` / `LogFrame` envelope + (de)serialization (`command_adapter`), **and** the agent wire schema (`AgentRequest` / `AgentFrame` / `WorkbenchLocation`). The things the sides must agree on. | — | host, agent **and** bench |
| **core** | does the actual work — the command handlers (`build-runtime`, `generate-sbom`, `evaluate`, `run-experiment`), the `doctor` bench probe, the tool resolver (`tooling.py`), and the workspace/REE/`/ree`-tree operations. Pure library; **no CLI framework deps**. | protocol | **bench only** |
| **supervisor** | the control plane: workbench + REE **lifecycle** (provision / reprovision / teardown), the **registry** (`ree_id → agent + location`), and the **dispatch** that sends commands to the agent and streams logs/results back. Never executes a command, and never touches a container runtime, itself. | protocol | host only |

### The agent (runtime host)

| package | responsibility | depends on | deployed |
|---|---|---|---|
| **agent** (`repo2ree-agent`) | owns the container runtime on its host (`DockerRuntime` behind a `WorkbenchRuntime` protocol). Dials the control plane outbound and serves per-bench verbs over one WebSocket. Injects the executor + tools closures into each bench, mints its opaque `WorkbenchLocation`, runs the `doctor` probe, and ferries frames. A *frame ferry*, not an executor — imports `protocol` only. | protocol | its own host (holds the docker socket) |

### Surfaces

| surface | over | role | deployed |
|---|---|---|---|
| **executor** (`repo2ree-exec`) | core + protocol | one-shot: read a `Command` on stdin, run it via core, stream `LogFrame`s on stderr, emit `ActionResult` on stdout, exit. **No listening server.** Injected by the agent, so it ships with the agent — not baked into the bench image. | **bench only** |
| **`repo2ree`** (supervisor cli) | supervisor + protocol | **target user/agent surface.** Drive the pipeline against a bench, stream logs, pull artifacts, tear down. | host — *not implemented yet* |
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
5. **The agent imports `protocol` only — never `core`.** It is a frame ferry: it
   places and drives benches and *injects* the executor closure, but never runs
   command logic itself. Keeping `core` out of the agent keeps the runtime host
   small and keeps the execution logic on the far side of the bench boundary.

Resulting DAG (acyclic, and the only cross-boundary edge is the protocol):

```
protocol ← core ← executor              (execution plane, in the bench)
protocol ← agent                        (runtime host; drives the bench, injects the executor)
protocol ← supervisor ← { repo2ree(cli), api }   (control plane)
```

## Call graph — what is and isn't a process boundary

A common misread is that the `api` shells out to the supervisor cli. It does
not. `api` and `repo2ree` are sibling surfaces that both import the
`supervisor` library in-process. The runtime lives one hop further out, behind
the agent: the supervisor speaks the agent wire protocol, and the *agent* is
what does the `docker exec`.

```
gui ───────http──► api ──┐
                         ├─► supervisor ══ws══► agent ──docker exec──► executor ─► core
agent/user ─► repo2ree ──┘   (library)  (AgentClient)  (DockerRuntime) (in the bench)
              (sv-cli)
        ▲ both call supervisor as a Python library, in-process ▲
                              ▲ crosses the network to the runtime host ▲
```

Three hops, only the two outer ones cross a boundary:

| hop | kind | why |
|---|---|---|
| `api` / `repo2ree` → `supervisor` | **in-process function call** | same machine, same process — `supervisor.provision(...)`, `supervisor.dispatch(cmd, ...)`. No subprocess. |
| `supervisor` → `agent` | **network / wire** (`AgentClient` over one **agent-dialed** WebSocket; typed `AgentRequest` / `AgentFrame`) | crosses **to the runtime-owning host**. The agent dials the control plane, so this works from inside clusters and NATed networks that only allow egress — no inbound agent port. |
| `agent` → `executor` | **subprocess** (`docker exec … <exec_path> execute`, `Command` on stdin) | crosses **into the isolated bench**. Can't be an in-process call; needs a wire — this is what the typed envelope is *for*. |

The two outer hops are the only "cross a boundary" paths: the supervisor→agent
hop crosses the network to the runtime host, and the agent→executor hop crosses
into the sandbox. Everything left of `supervisor` is a function call. In hosted
mode, `api` may pass through the
[service tier](#the-service-tier--multi-user-persistence-auth-hosted-only) first,
still in-process.

## The two CLIs — why, and how to name them

repo2ree has **two** command-line tools because it has two execution contexts,
and conflating them is the mistake to avoid:

| | runs | reads | job | user-facing? |
|---|---|---|---|---|
| **`repo2ree`** (supervisor cli) | on the host | argv | drive workbenches | **yes — this is what `pip install` gives you** |
| **`repo2ree-exec`** (executor) | inside the bench (agent-injected) | a `Command` on **stdin** | execute one command, exit | no — bench-internal |

The friendly name `repo2ree` belongs to the future host cli. The implemented
guest piece is the stdin-driven `repo2ree-exec`: invoked per command via
`docker exec`, executes once, emits a result, exits. Avoid `agent`,
`server`/`daemon`, and bare `cli`; each is ambiguous here.

## Always isolated, location configurable

Isolation is fixed; *which agent owns the substrate* is the knob. The control
plane never holds a docker socket — it addresses a bench through the agent that
provisioned it, so "local vs remote" is a matter of *where the agent runs*, not
a second transport to write:

- **The agent owns the runtime; the control plane owns intent.** An agent runs
  next to the docker host (or cloud/HPC substrate), dials the control plane
  outbound, and reports its identity. Provision pins the REE to the concrete
  agent it lands on (`AgentClient.resolve_agent`), and every later op routes to
  that same agent.
- **Handle resolution goes through the agent, not `docker inspect`.** Because
  the control plane has no socket, it cannot inspect containers directly: it
  records `ree_id → (agent_id, WorkbenchLocation)` in a persisted registry
  (`WORKBENCH_REGISTRY_FILE`) and asks the agent for run-state (`is_running`).
  The bench's container name is still deterministic *on the agent's host*
  (`repo2ree-wb-{ree_id}`), but that name is the agent's private vocabulary,
  carried inside the opaque `WorkbenchLocation` — the control plane never
  interprets it.
- **The iterate loop stays fast despite always-isolated.** The bench is
  persistent: provision once (the image's own default process keeps it alive —
  `dockerd` on dind — with a pause command only as the rescue for images whose
  default exits immediately; `restart unless-stopped` is applied *after* the
  bench proves viable), then `docker exec` per command via the agent, tear down
  at the end.
- **A reachable agent is the hard requirement.** An environment with no
  connected agent (and thus no runtime) cannot run the product.

The remote case is a **registered agent inside the user's boundary**, reached
outbound-only — not the control plane holding SSH keys or a kubeconfig. In
hosted mode repo2ree should not receive SSH passwords, private keys, cloud admin
credentials, or kubeconfigs; cloud and university resources are reached through
a registered runner/agent inside the user's boundary. See
[Remote execution clients](ARCHITECTURE.md#remote-execution-clients-user-owned-runners).

## What runs continuously — deployment modes

The supervisor is a **library, not a daemon** — whether anything "runs
continuously" is a property of the *surface that hosts it*. But note where the
always-on process moved: because the control plane has no docker socket, the
long-running runtime host is now the **agent**, and the control plane keeps a
small **persisted registry** (it cannot reconstruct bench state from `docker
inspect` the way a socket-holding supervisor could):

| state | owned by |
|---|---|
| the bench fleet (containers + volumes) | **docker on the agent's host** — a long-running daemon (`restart unless-stopped`, applied once a bench is viable) |
| the runtime host that drives the fleet | **the agent** — a continuously-running process holding the socket and one outbound WebSocket to the control plane |
| the registry (`ree_id → agent_id + WorkbenchLocation`) | **persisted by the control plane** (`WORKBENCH_REGISTRY_FILE`) — the opaque location is minted by the agent and cannot be re-derived host-side |
| long-running jobs (a build is minutes) | **the bench itself** — run inside the bench, write logs/result to `/ree`, stream frames back through the agent. Each bench is a per-REE continuous process. |
| the versioned manifest (optimistic concurrency) | the **service tier's DB** (below); moot in single-client cli mode |

Two modes follow:

| mode | the continuous processes | supervisor |
|---|---|---|
| **cli / single agent** | docker + benches + one agent | ephemeral library, in-process per command — *no control-plane service to run, but an agent must be up* |
| **hosted / multi-user** | **the `api`** (a long-lived server) **+ one or more agents** | same library, hosted in-process by the api → effectively continuous; fleet background work (idle-TTL GC, health, orphan cleanup) is a background task *inside the api process* |

A **separate** supervisor daemon is still the wrong default: it breaks the
zero-service cli flow and adds an IPC hop the api gains nothing from. The agent
is *not* that daemon — it lives on the execution-plane host and owns the
substrate, which is exactly the concern the control plane must not hold. Only
introduce a standalone control-plane worker if fleet-wide background work must
be decoupled from the request lifecycle (global quotas, cross-host draining) —
and even then it's an *optional worker that imports the supervisor library*,
never a reimplementation.

## The service tier — multi-user, persistence, auth (hosted only)

The base is **3 libraries + 3 surfaces**. A multi-user *hosted* deployment adds
one library tier **on top of** the supervisor — strictly additive, and the cli
path never touches it. Identity/tenancy is **neither a `core` nor a `supervisor`
concern**: core executes commands, the supervisor manages a workbench *for an
opaque `ree_id`* (tenant-agnostic, so the single-user cli can reuse it). The
service is the layer that knows about **people**.

```
protocol ─ core ─ executor                         execution plane (in workbench)
protocol ─ supervisor                              workbench control (tenant-agnostic)
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
| users, orgs/tenants, memberships | workbench fleet → docker |
| REE ownership / ACL / sharing (`ree_id → tenant`) | `/ree` tree + artifacts → the volume |
| versioned manifest (optimistic concurrency) | CAS blobs → its own store, if/when |
| run history / audit log / job records; quotas / usage | |

Two judgment calls baked in:

1. **Auth is a pluggable boundary, not a bespoke system.** Build a seam
   (verify token → identity, OIDC/SSO-friendly) with a default impl — don't
   hand-roll a user/password store deployments can't swap.
2. **Tenancy stays out of the supervisor.** Enforce it in the service ACL layer;
   keep `ree_id`s globally-unique opaque ids (the agent derives its own flat
   container name, `repo2ree-wb-{ree_id}`, from that id inside the opaque
   `WorkbenchLocation`). If the supervisor learns about tenants it stops being
   reusable by the cli.

DAG rule extends cleanly: `service → supervisor → protocol`, and **`service`
never imports `core`.** Packaging is non-dogmatic — a well-bounded `service`
*module* inside `api` (routes thin over it) is a fine start; promote to its own
package when a second surface needs the same use-cases. None of this is needed
for the cli/local flow or a first single-tenant deployment.

## Distribution

The executor no longer ships as a bench image. It is a nix closure carried by
the **agent** and injected at provision time, so the units to distribute are the
control plane, the agent, and an env image that carries *no* repo2ree content.

| audience | installs / pulls |
|---|---|
| control-plane host | `api` (and the GUI it serves) + `supervisor` + `protocol` |
| runtime host | the **agent image** (`repo2ree-agent`): the agent process + the executor and tools closures it injects (`protocol` + `core` + `executor`, bundled — never `supervisor` / `api`) |
| env image (the bench) | any image that keeps a process alive with a writable `/ree`; **zero repo2ree content** — the default is upstream `docker:dind`, pinned by digest in the catalog |

Because the executor and tools **version with the agent, not the env image**,
there is no separately-installed executor to skew against: pull a newer agent
image and every bench it provisions runs the matching executor.

Two things pin what produced an REE, and both are content addresses: the env
image (`Command.workbench_image: digest` — see
[the wire form](ARCHITECTURE.md#the-wire-form-a-typed-action-envelope)) *and* the
injected executor/tools closures (content-hashed nix store paths). Pinning both
pins the environment that produced the REE. See
[the env image](ARCHITECTURE.md#the-workbench-env-image).

## Target test layout

Two seams need faking, not one. The control plane depends on `AgentClient`
(supervisor → agent); the agent depends on `WorkbenchRuntime` (agent →
substrate). Each has one production impl and a test fake:

| seam | production | test | docker? |
|---|---|---|---|
| `AgentClient` (control plane → agent) | `WsAgentClient` (one outbound WebSocket) | in-memory fake client | no |
| `WorkbenchRuntime` (agent → substrate) | `DockerRuntime` (local docker socket) | — | yes (real) |
| `in-process` (run `core` directly on a temp `/ree`) | — | test transport | no |

That keeps "full e2e per surface" affordable: the **real docker path is
exercised end-to-end once** (through a real agent + `DockerRuntime`), while each
surface is tested against faked seams — fast, deterministic, daemon-free.

```
protocol/tests/      unit: envelope + agent-frame (de)serialization round-trips
core/tests/          unit: command handlers, /ree ops, doctor, tooling   (existing)
agent/tests/         unit: DockerRuntime injection/probe logic; control_link; transfers
supervisor/tests/    unit: registry; manager/dispatch w/ AgentClient faked
                     integration: against a fake agent / in-process transport
cli/tests/e2e/       future repo2ree cli: provision → acquire → build → run → seal → teardown
api/tests/e2e/       same flow over httpx against the FastAPI app
gui/tests/e2e/  existing UI e2e
```

The e2e suites should share **one flow definition** per surface (acquire → build
→ evaluate → experiment → seal), mirroring how `gui/tests/e2e/helpers/flow.ts`
already factors the UI flow. Today the API/GUI path carries that coverage;
when the host CLI exists, it should reuse the same flow.

## Relationship to today's code

The package split is now largely real:

- **Done:** `protocol/` holds the typed command/result/log/tracing contract
  **and** the agent wire schema (`AgentRequest` / `AgentFrame` /
  `WorkbenchLocation`).
- **Done:** `supervisor/` holds `WorkbenchManager`, the persisted registry, and
  the `AgentClient` seam — it dispatches over the wire and touches no runtime.
- **Done:** `agent/` holds the runtime host: the `WorkbenchRuntime` protocol,
  its sole `DockerRuntime` impl (provisioning, executor injection, the `doctor`
  probe), and the `control_link` WebSocket server.
- **Done:** `executor/` provides `repo2ree-exec`, the in-bench command runner,
  now injected by the agent rather than baked into a bench image.
- **Done (interface):** the transport is now an interface with one impl each —
  `AgentClient` → `WsAgentClient`, `WorkbenchRuntime` → `DockerRuntime` — not a
  single hardcoded local-Docker path. Additional runtimes (cloud/HPC) are the
  intended next impls.
- **Done:** the dependency rules above are machine-enforced. `[tool.importlinter]`
  in [pyproject.toml](../pyproject.toml) carries workspace-level layers, per-package
  layer contracts for `api` and `core` (both marked exhaustive, so a new top-level
  module must declare its tier), and independence contracts holding the author and
  review sides apart in both `core.operations.handlers` and `api`.
- **Still rough:** `api` imports `core` domain and evidence *types* directly
  (`ReeIntent`, `ReviewRecord`, `ReproducibilityScoreCard`, the step graph) rather
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
| **execution** | run a build on a peer's bench | the `AgentClient` / `WorkbenchRuntime` seams | the *differentiated* one — enabled by reproducibility |
| **discovery / identity** | DHT + keys instead of the central `service`/DB | an alternative to the service tier | heaviest; usually unnecessary |

The hosted-client version of this is the registered runner described in
[Remote execution clients](ARCHITECTURE.md#remote-execution-clients-user-owned-runners):
it leases typed Actions, runs them through a local provider, and returns
digest-bound `ActionResult`s. A peer execution surface would reuse that same
shape with a different discovery and trust layer.

### The distributed action cache (the core idea)

The envelope is [REAPI-shaped](ARCHITECTURE.md#the-wire-form-a-typed-action-envelope),
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
- **execution** → another `WorkbenchRuntime` impl (a *peer* substrate alongside
  `DockerRuntime`), or a peer `AgentClient`, **+** a verification step that
  re-runs via `core` and digest-compares. The runtime/agent seams are what make
  this free.
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
- **Sequencing:** *(largely resolved)* `supervisor` is extracted and the
  transport is now the `AgentClient` / `WorkbenchRuntime` seams with the agent as
  the runtime host. What remains sequenced behind this is the user-facing
  `repo2ree` cli and additional `WorkbenchRuntime` impls (cloud/HPC).
- **Service tier home:** a bounded `service` module inside `api` vs its own
  package. Defer until a second surface needs the same use-cases.
- **Auth scheme:** the default identity provider behind the pluggable auth seam
  (OIDC? local dev token?). Out of scope until the first multi-user deployment.
- **P2P / distributed action cache:** explicitly *non-goal* until a concrete
  driver. Tracked only as "preserved option" — the action-cache key
  (`command_digest`) and the artifact/CAS + `AgentClient`/`WorkbenchRuntime`
  interfaces are the seams that keep it free.
