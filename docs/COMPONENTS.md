# repo2ree — Component & Package Architecture

> **Status: proposed / in-design (2026-06).** The **code-organization**
> companion to [ARCHITECTURE.md](ARCHITECTURE.md). That doc describes the
> *runtime* model — the control-plane / execution-plane split, the isolation
> boundary, the typed action envelope, CAS. This doc maps that model onto
> **source packages**: what each component is, what it may depend on, where it
> is deployed, and the dependency rules that keep the seam clean. For *what*
> each concept means see [CONCEPTS.md](CONCEPTS.md); for *why* the product is
> shaped this way see [POSITIONING.md](POSITIONING.md).

## Mental model

repo2ree is a **control plane driving an isolated execution plane over a typed
command protocol** (the "thin client, fat agent" pattern — cf. kubectl→kubelet;
see [Control plane / execution plane split](ARCHITECTURE.md#control-plane--execution-plane-split)).
Two invariants shape every package boundary below:

1. **An REE is always built in an isolated workbench.** There is no
   "run it directly on the host" mode in the shipped product — a non-isolated
   build produces an REE whose reproducibility/provenance claims can't be
   trusted. Isolation is not configurable.
2. **The only configurable axis is *where the workbench runs*** — the docker
   endpoint: a local daemon, or a remote host (ssh / docker context / later
   k8s). Same protocol, same commands; only the transport target changes.

From those two invariants the decomposition is forced: a piece that runs
**inside** the workbench and a piece that runs **on the host** must be separate
deployable units, joined only by the protocol they both speak.

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
            │  (guest)  │   │ (host  │  │(http,│
            │           │   │  cli)  │  │ opt.)│
            └───────────┘   └────────┘  └──────┘

  LIBRARIES (logic)            SURFACES (entry points)
  ─────────────────            ───────────────────────
  protocol   the wire contract executor  guest, in-image, stdin→core→stdout
  core       does the work     repo2ree  host cli — THE user/agent surface
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
| **`repo2ree`** (supervisor cli) | supervisor + protocol | **the primary user/agent surface.** Provision a workbench (local or remote), drive the pipeline, stream logs, pull artifacts, tear down. | host — *what users install* |
| **api** (http) | supervisor + protocol | **optional** hosted UX over the supervisor (what the frontend talks to; remote/multi-user access). | host |

## Dependency rules (the invariants that keep the seam clean)

These are the rules a dependency-cruiser / import-linter config should enforce:

1. **The host never imports `core`.** `supervisor`, `repo2ree` (cli), and `api`
   depend on `protocol` only. Execution logic lives exclusively in the image.
   This is what makes "nobody installs core" true at the dependency level, not
   just by convention.
2. **Surfaces import their library, never each other.** `api` and `repo2ree`
   are sibling surfaces over `supervisor`; neither imports the other. No
   `cli → api` or `api → cli` edge. (This is precisely the edge that "fold
   lifecycle into the existing cli" would have created — and why we didn't.)
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

A common misread is that the `api` shells out to the supervisor cli
(`frontend → api → repo2ree → supervisor → …`). It does not. `api` and
`repo2ree` are **sibling surfaces** that both import the **supervisor library
in-process**. Neither goes through the other (that would be the `api → cli` edge
rule 2 forbids).

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

The supervisor → executor hop is the **only** legitimate "invoke a cli" in the
system, precisely because it's the one that crosses the sandbox. Everything to
the left of the supervisor is plain function calls. (In a hosted deployment the
api routes through the [service tier](#the-service-tier--multi-user-persistence-auth-hosted-only)
before reaching the supervisor — still in-process.)

## The two CLIs — why, and how to name them

There are **two** command-line tools because there are two execution contexts,
and conflating them is the mistake to avoid:

| | runs | reads | job | user-facing? |
|---|---|---|---|---|
| **`repo2ree`** (supervisor cli) | on the host | argv | drive workbenches | **yes — this is what `pip install` gives you** |
| **`repo2ree-exec`** (executor) | inside the workbench image | a `Command` on **stdin** | execute one command, exit | no — image-internal |

The friendly name `repo2ree` belongs to the **host** cli — that's what a user or
an agent types. The guest piece is a one-shot, stdin-driven executor invoked per
command via `docker exec`; it is named **executor** (`repo2ree-exec`) to say
exactly that: it *executes* one command and exits (no daemon), it is stdin-fed,
and it fronts core. Avoid `agent` (collides with AI-agent), `server`/`daemon`
(implies a listener — there isn't one), and bare `cli` (now ambiguous).

## Always isolated, location configurable

Isolation is fixed; the docker endpoint is the knob. Because docker has native
remote support, "local vs remote" is mostly a connection setting, not a second
transport to write:

```
repo2ree create ./src -o ree.tar.gz                     # workbench on local daemon
repo2ree create ./src -o ree.tar.gz --host ssh://build  # workbench on a remote box
```

- The supervisor's transport targets a configurable docker endpoint
  (`DOCKER_HOST` / docker context / `-H ssh://…`). An agent on a laptop can
  offload heavy or untrusted builds to a remote, same cli, same commands.
- **Handle resolution needs no registry daemon.** The container name is
  deterministic (`repo2ree-wb-{ree_id}`), so existence/run-state is a
  `docker inspect` — *docker itself is the registry* for the cli flow. The
  stateful registry is only needed by the multi-user `api`.
- **The iterate loop stays fast despite always-isolated.** The workbench is
  persistent (`sleep infinity`, `restart unless-stopped`): provision once,
  `docker exec` per command, tear down at the end.
- **This assumes docker (local or reachable) is always available** — the price
  of the guarantee. An environment with no docker and no remote can't run the
  product; that's by design, not a gap to patch with an unsafe local mode.

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
| user / agent (cli) | `repo2ree` (supervisor cli) + `protocol`; **+ a workbench image** (carries `core` + `executor`) |
| hosted deployment | the above + `api` (and the frontend it serves) |
| workbench image | `protocol` + `core` + `executor` — *never* `supervisor` / `api` / cli |

The workbench **image is versioned and is part of the reproducibility anchor**
(`Command.workbench_image: digest` — see
[the wire form](ARCHITECTURE.md#the-wire-form-a-typed-action-envelope)). Pinning
the image pins what produced the REE.

## Test layout that follows

The transport is an interface (`WorkbenchClient`) with **three**
implementations — but only two are user-facing:

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
cli/tests/e2e/       repo2ree: provision → acquire → build → run → seal → teardown
api/tests/e2e/       same flow over httpx against the FastAPI app
frontend/tests/e2e/  existing UI e2e
```

The three e2e suites share **one flow definition** per surface (acquire → build
→ evaluate → experiment → seal), mirroring how `frontend/tests/e2e/helpers/flow.ts`
already factors the UI flow. Slow real-docker e2e runs once (cli, the agent's
primary door); the rest is fast.

## Relationship to today's code

This is the target shape; the current tree differs in three ways. See
[Migration notes](ARCHITECTURE.md#migration-notes) for sequencing.

- **The supervisor is trapped in `api/`.** `WorkbenchManager` + the registry live
  at [api/src/repo2ree_api/workbench/](api/src/repo2ree_api/workbench/) and do raw
  docker orchestration — host logic in a surface. → extract to a `supervisor`
  package; leave FastAPI glue (`deps.py`) in `api`.
- **The protocol is folded into `core`.** The envelope lives at
  `core/src/repo2ree_core/envelope/`. → hoist to its own `protocol` package so the
  host can speak the contract without importing `core`. (Lowest urgency — do it
  when "host imports core" actually starts to bite.)
- **One transport, hard-wired to docker.** `WorkbenchManager.dispatch_action` /
  `dispatch_query` weld lifecycle to docker-exec. → split out a `WorkbenchClient`
  interface; add the `in-process` (test) and `docker-remote` impls.

The current `cli/` package (`repo2ree_cli`, binary `repo2ree`) is today the
**guest executor**. Under the target naming the friendly `repo2ree` name moves to
the **host** supervisor cli, and the guest piece becomes `repo2ree-exec`.

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

### Why hermeticity is the *enabler*, not a substitute

The honest split on "isn't a hermetic artifact already enough?":

- **For distribution — yes, it's enough.** A content-addressed REE is
  fetch-and-verify from *any* backend (OCI registry, S3, IPFS, BitTorrent —
  interchangeable). Make the artifact store an interface; a P2P backend is one
  impl added the day someone needs it. Don't build bespoke P2P here.
- **For execution — hermeticity is not a substitute, it's the precondition.**
  Trustless remote execution is normally intractable (why trust a stranger's
  build?). Reproducibility solves it: an untrusted peer's result is **verifiable
  by re-running and comparing the output digest** — the Nix reproducible-builds
  *rebuilder* / Bazel-RBE model. For a *reproducibility tool specifically*, a
  verifiable rebuilder network is a genuinely differentiated capability that
  exists **because** REEs are hermetic.

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
