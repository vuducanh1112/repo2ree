# repo2ree — Component & Package Architecture

> **Status: partially implemented + target rules (2026-06).** The
> code-organization companion to [ARCHITECTURE.md](ARCHITECTURE.md). It maps
> the runtime model onto source packages, deployment locations, and dependency
> rules. For concepts see [CONCEPTS.md](CONCEPTS.md); for product framing see
> [POSITIONING.md](POSITIONING.md).

## Mental model

repo2ree is a **control plane driving an isolated execution plane over a typed
command protocol**; see
[Control plane / execution plane split](ARCHITECTURE.md#control-plane--execution-plane-split).
Two target invariants shape every package boundary below:

1. **An REE is built through a workbench.** The main path provisions a per-REE
   Docker-in-Docker workbench and dispatches typed commands into it. The target
   is a stronger VM-backed workbench; legacy review routes are still being
   migrated.
2. **Only the workbench provider/location is configurable**: local Docker,
   user-local Docker over ssh/context, or a registered runner/controller for
   cloud, Kubernetes, and institutional environments. Protocol and commands stay
   the same.

So the host-side control plane and the in-workbench executor are separate
deployable units joined by one protocol.

## The decomposition: 3 libraries + 3 surfaces

**Libraries do the work. Surfaces are thin adapters that expose a library at a
boundary.** Surfaces own *no* logic — they translate (argv / HTTP / stdin) into
a library call and shape the result back.

```
                       protocol            ← the contract (Command / ActionResult / LogEvent)
                      /        \
                  core          supervisor
                    │           /        \
            ┌───────┴───┐   ┌───┴───┐  ┌───┴──┐
            │ executor  │   │repo2ree│  │ api  │   ← surfaces
            │  (guest)  │   │(future │  │(http,│
            │           │   │  cli)  │  │ opt.)│
            └───────────┘   └────────┘  └──────┘

  LIBRARIES (logic)            SURFACES (entry points)
  ─────────────────            ───────────────────────
  protocol   the wire contract executor  guest, in-image, stdin→core→stdout
  core       does the work     repo2ree  future host cli — user/agent surface
  supervisor lifecycle+relay    api       host http — optional hosted UX
```

### Libraries

| package | responsibility | depends on | deployed |
|---|---|---|---|
| **protocol** | the typed `Command` / `ActionResult` / `LogEvent` envelope + (de)serialization (`command_adapter`). The single thing host and guest must agree on. | — | host **and** image |
| **core** | does the actual work — the command handlers (`build-runtime`, `generate-sbom`, `evaluate`, `run-experiment`, the workspace/REE/`/ree`-tree operations). Pure library; **no CLI framework deps**. | protocol | **image only** |
| **supervisor** | the control plane: workbench + REE **lifecycle** (provision / reprovision / teardown), the **registry** (`ree_id → workbench`), and the **relay/transport** that dispatches commands into a workbench and streams logs/results back. Never executes a command itself. | protocol | host only |

### Surfaces

| surface | over | role | deployed |
|---|---|---|---|
| **executor** (`repo2ree-exec`) | core + protocol | one-shot: read a `Command` on stdin, run it via core, stream `LogEvent`s on stderr, emit `ActionResult` on stdout, exit. **No listening server.** | **image only** |
| **`repo2ree`** (supervisor cli) | supervisor + protocol | **target user/agent surface.** Provision a workbench (local or remote), drive the pipeline, stream logs, pull artifacts, tear down. | host — *not implemented yet* |
| **api** (http) | supervisor + protocol | **optional** hosted UX over the supervisor (what the frontend talks to; remote/multi-user access). | host |

## Dependency rules (the invariants that keep the seam clean)

These are the rules a dependency-cruiser / import-linter config should enforce
as the migration finishes:

1. **The host should not import effectful `core`.** `supervisor` and the future
   host CLI depend on `protocol` only. `api` still imports a few `core` domain
   and storage helpers today; keep shrinking that surface until execution logic
   lives exclusively in the image.
2. **Surfaces import their library, never each other.** `api` and `repo2ree`
   are sibling surfaces over `supervisor`. No `cli -> api` or `api -> cli` edge.
3. **`protocol` depends on nothing.** It is the seam; it must stay importable by
   both sides without dragging either side's logic along.
4. **`core` carries no CLI/HTTP framework deps.** It is a pure library so it can
   also be imported by the in-process *test* transport (below) without cost.

Resulting DAG (acyclic, and the only cross-boundary edge is the protocol):

```
protocol ← core ← executor
protocol ← supervisor ← { repo2ree(cli), api }
```

## Call graph — what is and isn't a process boundary

A common misread is that the `api` shells out to the supervisor cli. It does
not. `api` and `repo2ree` are sibling surfaces that both import the
`supervisor` library in-process.

```
frontend ──http──► api ──┐
                         ├─► supervisor ──docker exec──► executor ─► core
agent/user ─► repo2ree ──┘   (library)     (transport)   (in workbench)
              (sv-cli)
        ▲ both call supervisor as a Python library, in-process ▲
```

There are two hops that *look* alike but are fundamentally different — only one
crosses a process/isolation boundary:

| hop | kind | why |
|---|---|---|
| `api` / `repo2ree` → `supervisor` | **in-process function call** | same machine, same process — `supervisor.provision(...)`, `supervisor.dispatch(cmd, ...)`. No subprocess. |
| `supervisor` → `executor` | **subprocess / transport** (`docker exec … repo2ree-exec`, `Command` on stdin) | crosses **into the isolated workbench** (and maybe to another machine via ssh). Can't be an in-process call; needs a wire — this is what the typed envelope is *for*. |

The supervisor -> executor hop is the only legitimate "invoke a cli" path
because it crosses the sandbox. Everything left of `supervisor` is a function
call. In hosted mode, `api` may pass through the
[service tier](#the-service-tier--multi-user-persistence-auth-hosted-only) first,
still in-process.

## The two CLIs — why, and how to name them

There are **two** command-line tools because there are two execution contexts,
and conflating them is the mistake to avoid:

| | runs | reads | job | user-facing? |
|---|---|---|---|---|
| **`repo2ree`** (supervisor cli) | on the host | argv | drive workbenches | **yes — this is what `pip install` gives you** |
| **`repo2ree-exec`** (executor) | inside the workbench image | a `Command` on **stdin** | execute one command, exit | no — image-internal |

The friendly name `repo2ree` belongs to the future host cli. The implemented
guest piece is the stdin-driven `repo2ree-exec`: invoked per command via
`docker exec`, executes once, emits a result, exits. Avoid `agent`,
`server`/`daemon`, and bare `cli`; each is ambiguous here.

## Always isolated, location configurable

Isolation is fixed; the docker endpoint is the knob. Because docker has native
remote support, the single-user CLI can treat "local vs remote" mostly as a
connection setting, not a second transport to write:

```
repo2ree create ./src -o ree.tar.gz                     # workbench on local daemon
repo2ree create ./src -o ree.tar.gz --host ssh://build  # workbench on a remote box
```

- The supervisor targets a configurable Docker endpoint (`DOCKER_HOST`, docker
  context, `-H ssh://...`). Same cli, same commands.
- **Handle resolution needs no registry daemon.** The container name is
  deterministic (`repo2ree-wb-{ree_id}`), so existence/run-state is a
  `docker inspect` — *docker itself is the registry* for the cli flow. The
  stateful registry is only needed by the multi-user `api`.
- **The iterate loop stays fast despite always-isolated.** The workbench is
  persistent (`sleep infinity`, `restart unless-stopped`): provision once,
  `docker exec` per command, tear down at the end.
- **Docker must be local or reachable.** An environment with no Docker and no
  remote cannot run the product.

This SSH/context form is the **user-controlled CLI case**: the user's local
machine may use its own SSH agent or Docker context to reach a remote Docker
host. In hosted mode, repo2ree should not receive SSH passwords, private keys,
cloud admin credentials, or kubeconfigs. Cloud and university resources should
be reached through a registered runner/controller inside the user's boundary;
see [Remote execution clients](ARCHITECTURE.md#remote-execution-clients-user-owned-runners).

## What runs continuously — deployment modes

The supervisor is a **library, not a daemon.** Whether anything "runs
continuously" is a property of the *surface that hosts it*, not of the
supervisor itself — because the supervisor owns no state that must outlive a
call. It is **stateless** and derives everything from docker each time:

| state | owned by |
|---|---|
| the workbench fleet (containers + volumes) | **docker** — already a long-running daemon (`restart unless-stopped`) |
| the registry (`ree_id → workbench`) | **derived** — container name is deterministic, so `docker inspect` reconstructs it |
| long-running jobs (a build is minutes) | **the workbench itself** — run detached, write logs/result to `/ree`, clients attach to tail. Each workbench is already a per-REE continuous process. |
| the versioned manifest (optimistic concurrency) | the **service tier's DB** (below); moot in single-client cli mode |

So the continuously-running things you'd reach for **already exist** (docker +
the workbench containers). Two modes follow:

| mode | the continuous process | supervisor |
|---|---|---|
| **cli / single agent** | docker + workbench containers | ephemeral library, in-process per command, stateless — *no service to run* |
| **hosted / multi-user** | **the `api`** (a long-lived server) | same library, hosted in-process by the api → effectively continuous; fleet background work (idle-TTL GC, health, orphan cleanup) is a background task *inside the api process* |

A **separate** supervisor daemon is the wrong default: it breaks the
zero-service cli flow, is redundant with docker, and adds an IPC hop the api
gains nothing from. Only introduce a standalone long-lived process if
fleet-wide background work must be decoupled from the request lifecycle (global
quotas, cross-host draining) — and even then it's an *optional worker that
imports the supervisor library*, never a reimplementation.

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
                    └─ api (thin HTTP surface)  ──  frontend

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
   keep `ree_id`s globally-unique opaque ids and container naming flat
   (`repo2ree-wb-{ree_id}`). If the supervisor learns about tenants it stops
   being reusable by the cli.

DAG rule extends cleanly: `service → supervisor → protocol`, and **`service`
never imports `core`.** Packaging is non-dogmatic — a well-bounded `service`
*module* inside `api` (routes thin over it) is a fine start; promote to its own
package when a second surface needs the same use-cases. None of this is needed
for the cli/local flow or a first single-tenant deployment.

## Distribution

| audience | installs / pulls |
|---|---|
| user / agent (future cli) | `repo2ree` (supervisor cli) + `protocol`; **+ a workbench image** (carries `core` + `executor`) |
| hosted deployment | the above + `api` (and the frontend it serves) |
| workbench image | `protocol` + `core` + `executor` — *never* `supervisor` / `api` / cli |

The workbench **image is versioned and is part of the reproducibility anchor**
(`Command.workbench_image: digest` — see
[the wire form](ARCHITECTURE.md#the-wire-form-a-typed-action-envelope)). Pinning
the image pins what produced the REE.

## Target test layout

The transport is an interface (`WorkbenchClient`) with **three**
implementations in the target design — but only two are user-facing:

| transport | use | docker? |
|---|---|---|
| `docker-local` | shipped | yes |
| `docker-remote` (ssh / context) | shipped | yes (remote) |
| `in-process` (run `core` directly on a temp `/ree`) | **test only** | no |

That keeps "full e2e per surface" affordable: the **real docker path is
exercised end-to-end once**, while each surface is tested against the
in-process transport — fast, deterministic, daemon-free.

```
protocol/tests/      unit: envelope (de)serialization round-trips
core/tests/          unit: command handlers, /ree ops          (existing)
supervisor/tests/    unit: registry; lifecycle/relay w/ docker mocked
                     integration: against in-process transport
cli/tests/e2e/       future repo2ree cli: provision → acquire → build → run → seal → teardown
api/tests/e2e/       same flow over httpx against the FastAPI app
frontend/tests/e2e/  existing UI e2e
```

The e2e suites should share **one flow definition** per surface (acquire → build
→ evaluate → experiment → seal), mirroring how `frontend/tests/e2e/helpers/flow.ts`
already factors the UI flow. Today the API/frontend path carries that coverage;
when the host CLI exists, it should reuse the same flow.

## Relationship to today's code

The package split is now partly real:

- **Done:** `protocol/` holds the typed command/result/log/tracing contract.
- **Done:** `supervisor/` holds `WorkbenchManager` and the workbench registry.
- **Done:** `executor/` provides `repo2ree-exec`, the image-internal command
  runner.
- **Still rough:** `api` still imports some `core` domain/storage helpers and
  owns hosted UX concerns directly.
- **Still rough:** `WorkbenchManager` has one local-Docker transport, not a
  `WorkbenchClient` interface with local/remote/in-process implementations.
- **Missing:** the user-facing host `repo2ree` supervisor CLI does not exist yet.
- **Legacy:** review routes still carry older inline Docker flows and should move
  behind the same supervisor/protocol path.

## Future surfaces — what the seams enable (optional, driver-gated)

> Not roadmap. This records what the existing seams *keep possible for free*, so
> a future driver doesn't trigger a redesign. **Don't build any of this without a
> concrete driver** (YAGNI). A good architecture makes new surfaces cheap; the
> test is that each item below drops onto an interface that already exists and
> touches **neither `core`, `supervisor`, nor the protocol**.

"P2P" is not one surface — it conflates three independent axes, each landing on
a different existing seam, each separately optional:

| axis | meaning | seam it reuses | verdict |
|---|---|---|---|
| **distribution** | fetch finished REEs from any peer | the artifact / CAS store interface | commodity — hermetic + content-addressing already suffices |
| **execution** | run a build on a peer's workbench | the `WorkbenchClient` transport | the *differentiated* one — enabled by reproducibility |
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

So the build pipeline gains one lookup before it provisions a workbench: *ask the
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
- **execution** → another `WorkbenchClient` transport (a *peer* endpoint
  alongside `docker-local` / `docker-remote`) **+** a verification step that
  re-runs via `core` and digest-compares. The transport interface is the seam.
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
- **Sequencing:** extract `supervisor` + introduce `WorkbenchClient` first (this
  unblocks the cli e2e and fixes the layering smell); `protocol` split and the
  remote/agent surfaces can follow for free once the shape is in place.
- **Service tier home:** a bounded `service` module inside `api` vs its own
  package. Defer until a second surface needs the same use-cases.
- **Auth scheme:** the default identity provider behind the pluggable auth seam
  (OIDC? local dev token?). Out of scope until the first multi-user deployment.
- **P2P / distributed action cache:** explicitly *non-goal* until a concrete
  driver. Tracked only as "preserved option" — the action-cache key
  (`command_digest`) and the artifact/CAS + `WorkbenchClient` interfaces are the
  seams that keep it free.
