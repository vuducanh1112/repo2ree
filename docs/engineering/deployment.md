# repo2ree - Engineering Deployment Notes

> Status: current demo/dev deployment shape (2026-06). This is not yet a
> hardened production runbook. The current stack is useful for local demos and
> engineering validation.

repo2ree has three deployed surfaces today:

- `backend`: the FastAPI API — pure control plane. It never touches Docker;
  workbench operations go to whichever agents have dialed in.
- `agent`: the workbench agent. It holds the docker socket, dials the backend
  over an outbound WebSocket, provisions benches, and injects its embedded
  executor/tools bundles into them. Anyone can run one to contribute benches.
  It is deliberately not part of the control-plane compose stack — that stack
  is control plane only (GUI + backend). The agent ships its own compose
  file (`docker-compose.agent.yml`) so it can be started separately wherever
  benches should live, with an independent lifecycle.
- `gui`: a static Vite bundle served by Caddy. Caddy also reverse-proxies
  `/api/*` to the backend so the browser uses one origin.

Each REE gets a separate workbench container named `repo2ree-wb-{ree_id}` plus
Docker volumes for `/ree` state and the nested Docker daemon.

## Run With Published Images

The public demo path uses Docker Hub images and does not require Nix. Compose
brings up the control plane; a second compose file brings up the agent, which
dials the host-published backend port:

```bash
docker compose up -d
docker compose -f docker-compose.agent.yml up -d
```

Then open `http://localhost:3000`.

The agent compose file defaults `WORKBENCH_API_WS_URL` to
`ws://host.docker.internal:8000/agent/connect` (the control plane on the same
host). Override it to dial a backend elsewhere:

```bash
WORKBENCH_API_WS_URL=ws://backend.example:8000/agent/connect \
  docker compose -f docker-compose.agent.yml up -d
```

`docker-compose.yml` defaults to the current Docker Hub demo images:

| Variable | Default | Purpose |
|---|---|---|
| `REPO2REE_GUI_IMAGE` | `docker.io/vuducanh1112/repo2ree-gui:edge` | GUI image served by Caddy. |
| `REPO2REE_BACKEND_IMAGE` | `docker.io/vuducanh1112/repo2ree-backend:edge` | FastAPI backend image. |

The agent image is set on its own compose file via `REPO2REE_AGENT_IMAGE`
(default `docker.io/vuducanh1112/repo2ree-agent:edge`) — it holds the docker
socket, provisions benches, and injects the executor/tools bundles, and is
always started from `docker-compose.agent.yml` as above.

The per-REE workbench env image is not a deployment variable: it defaults to
the backend's image catalog (`api/src/repo2ree_api/settings.py` — a pinned
upstream `docker:dind` digest; the agent injects the executor and tools) and
is chosen per REE at provision time (the image picker in the UI, or a custom
ref). To ship a different set, override the `WORKBENCH_IMAGE_CATALOG` env var
on the backend.

## Build Images Locally

Build and load the GUI image:

```bash
make gui-image
```

This builds `.#gui-image` with Nix, serves the static bundle with Caddy,
and tags the result as `repo2ree-gui:local`.

Build the backend image:

```bash
make backend-image
```

This runs the Dockerfile build for `docker/demo/backend.Dockerfile` and tags the
result as `repo2ree-backend:local`.

Build and load the agent image (agent process + embedded executor/tools
bundles):

```bash
make agent-image
```

## Publishing Images

Publishing is push → validate → promote, so `edge` only ever points at a
validated commit:

```bash
make push-gate      # clean tree + full check/test/e2e sequence (see testing.md)
make push-rev       # push all images under the immutable :<git-rev> tag
make validate-rev   # full e2e suite against the pushed set
make promote-edge   # retag <rev> -> edge on the registries (no rebuild)
```

`push-rev` refuses a dirty tree and never moves `edge`, so it is safe at any
time.

When builds and registry credentials live on different machines (e.g. nix
only in the dev container, docker login only on the host), replace
`push-rev` with the archive pair: `make image-archives` in the dev container
(same dirty-tree guard; writes loadable tarballs plus a `REV` stamp to
`dist/images/`), copy `dist/images/` to the host, then `make push-archives`
there. `push-archives` loads the tarballs and pushes them under the stamped
rev — it never takes an `IMAGE_TAG`, so like `push-rev` it cannot move
`edge`. Continue with `validate-rev`/`promote-edge` as above, passing
`REV=$(cat dist/images/REV)` if the host checkout is not on that commit. `promote-edge` moves the registry tag (`docker buildx imagetools
create`), so the promoted digests are exactly the validated ones.
`validate-rev` and `promote-edge` default `REV` to the current HEAD, so the
whole flow runs tag-free from the commit being published. All images always move together — the
agent↔control-plane protocol requires matching versions. Registries default
to GHCR + Docker Hub under `vuducanh1112`; override `REGISTRIES`,
`GHCR_NAMESPACE`, or `DOCKERHUB_NAMESPACE`.

## Run With Local Images

```bash
REPO2REE_GUI_IMAGE=repo2ree-gui:local \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:local \
docker compose up
```

Start the agent stack pointed at the local image, then open
`http://localhost:3000`:

```bash
REPO2REE_AGENT_IMAGE=repo2ree-agent:local \
  docker compose -f docker-compose.agent.yml up -d
```

The compose stack publishes:

| Service | Port | Notes |
|---|---:|---|
| `gui` | `3000` | Caddy serves the Vite bundle and proxies `/api/*`. |
| `backend` | `8000` | FastAPI API. Exposed directly for debugging; also the endpoint agents dial. |

The agent container mounts `/var/run/docker.sock` and launches workbench
containers; the backend has no Docker access at all. The workbench containers
do not receive the host socket either; they run privileged Docker-in-Docker
with their own daemon.

## Compose Storage

Each compose file creates one named volume:

| Volume | Mounted at | Purpose |
|---|---|---|
| `repo2ree-demo-data` | `/app/.repo2ree` in the backend | Backend-local metadata such as upload staging and workbench registry. |
| `repo2ree-agent-state` | `/var/lib/repo2ree-agent` in the agent | The agent's stable identity across container replacements (created by `docker-compose.agent.yml`, with a pinned volume name so it survives recreation). |

REE execution state lives in per-REE Docker volumes created by the supervisor,
not inside `repo2ree-demo-data`.

`docker compose down` keeps both volumes, which is what a stack you intend to
restart wants. To stop a stack and reclaim everything it stored — the compose
volumes plus any workbench containers and per-REE volumes left behind — use
`scripts/image-stack.sh down --volumes` (`make stack-clean`), or
`scripts/workbench-cleanup.sh` for the workbench leftovers alone — the latter
also sweeps unreferenced anonymous volumes, which the bench image declares for
itself and which nothing can address once their container is gone.

## Runtime Configuration

Backend variables:

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_STAGING_DIR` | `.repo2ree/upload-staging` | Temporary upload landing zone before files enter a workbench. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Registry file mapping REE ids to workbench containers and volumes. |
| `OTLP_ENDPOINT` | unset | OTLP collector base URL for API and agent traces/metrics/logs (see `observability/`). |
| `OTEL_EXPORTER_OTLP_HEADERS` | unset | Headers for authenticated OTLP ingest (e.g. ClickStack's `authorization=<key>`). |
| `TRACE_FILE` | unset | Local NDJSON trace sink for API/agent spans when no collector is configured. |
| `LOG_LEVEL` | `INFO` | Python log level for API, agent, and executor processes. |

GUI variables:

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_UPSTREAM` | `backend:8000` | Runtime Caddy upstream for `/api/*` in the Nix-built GUI image. |
| `VITE_API_BASE_URL` | empty in the Nix image | Build-time API base. Empty means same-origin `/api`. |

Container socket access:

| Variable | Purpose |
|---|---|
| `DOCKER_GID` | Optional numeric group id for `/var/run/docker.sock` when building/running non-root containers. Discover with `stat -c '%g' /var/run/docker.sock`. |

## Security And Isolation Notes

Current state:

- The agent (not the backend) can reach the host Docker daemon.
- The main workbench path does not pass the host Docker socket into REE
  execution.
- Each workbench is a privileged Docker-in-Docker container with its own nested
  Docker daemon.
- Workbench containers are restarted unless stopped and can be torn down by the
  supervisor/API.

Target hardening, described in the architecture docs, is VM-backed workbenches
and stronger content-addressed/cache semantics. Do not describe the current
compose deployment as production isolation.

## Operational Checks

Useful checks after starting the stack:

```bash
curl -f http://localhost:8000/
docker ps --filter 'name=repo2ree'
docker image ls 'docker' --filter 'reference=docker*dind*'
docker volume ls --filter 'name=repo2ree'
```

If workbench provisioning fails, check:

- The agent container is running, can access `/var/run/docker.sock`, and shows
  as connected under `GET /api/v1/agents` (the backend itself never touches
  docker).
- The configured workbench env image can be pulled by the Docker daemon the
  agent uses.
- The host supports privileged containers.
- The provisioning run's log: the agent streams the pull, the bundle-volume
  populate, and the `repo2ree-exec doctor` capability probe into it — a bench
  that violates the contract fails there with a specific message.
- Workbench logs with `docker logs repo2ree-wb-{ree_id}`.
- Nested Docker logs inside the workbench at `/var/log/dockerd.log`.

## Non-Compose Deployments

For a non-compose deployment, keep the same boundaries:

- Run the backend anywhere; it needs no Docker access.
- Run an agent wherever benches should live, with `WORKBENCH_API_WS_URL`
  pointing at the backend (outbound only — no inbound port on the agent), the
  docker socket mounted, and its state dir persisted.
- Run the GUI image with `BACKEND_UPSTREAM` set to the backend host and
  port reachable from the Caddy container.
- Persist backend `.repo2ree` state and do not treat workbench Docker volumes as
  disposable while REEs are active.

The API is the hosted long-running process today. The supervisor is a library,
not a separate daemon.
