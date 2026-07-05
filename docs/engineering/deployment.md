# repo2ree - Engineering Deployment Notes

> Status: current demo/dev deployment shape (2026-06). This is not yet a
> hardened production runbook. The current stack is useful for local demos and
> engineering validation.

repo2ree has three deployed surfaces today:

- `backend`: the FastAPI API — pure control plane. It never touches Docker;
  workbench operations go to whichever agents have dialed in.
- `agent`: the workbench agent. It holds the docker socket, dials the backend
  over an outbound WebSocket, provisions benches, and injects its embedded
  executor/tools bundles into them. Anyone can run one to contribute benches;
  the compose stack runs one next to the backend.
- `frontend`: a static Vite bundle served by Caddy. Caddy also reverse-proxies
  `/api/*` to the backend so the browser uses one origin.

Each REE gets a separate workbench container named `repo2ree-wb-{ree_id}` plus
Docker volumes for `/ree` state and the nested Docker daemon.

## Run With Published Images

The public demo path uses Docker Hub images and does not require Nix:

```bash
docker compose up
```

Then open `http://localhost:3000`.

`docker-compose.yml` defaults to the current Docker Hub demo images:

| Variable | Default | Purpose |
|---|---|---|
| `REPO2REE_FRONTEND_IMAGE` | `docker.io/vuducanh1112/repo2ree-frontend:edge` | Frontend image served by Caddy. |
| `REPO2REE_BACKEND_IMAGE` | `docker.io/vuducanh1112/repo2ree-backend:edge` | FastAPI backend image. |
| `REPO2REE_AGENT_IMAGE` | `docker.io/vuducanh1112/repo2ree-agent:edge` | Workbench agent: holds the docker socket, provisions benches, injects the executor/tools bundles. |

The per-REE workbench env image is not a deployment variable: it defaults to
the backend's image catalog (`api/src/repo2ree_api/settings.py` — a pinned
upstream `docker:dind` digest; the agent injects the executor and tools) and
is chosen per REE at provision time (the image picker in the UI, or a custom
ref). To ship a different set, override the `WORKBENCH_IMAGE_CATALOG` env var
on the backend.

## Build Images Locally

Build and load the frontend image:

```bash
make frontend-image
```

This builds `.#frontend-image` with Nix, serves the static bundle with Caddy,
and tags the result as `repo2ree-frontend:latest`.

Build the backend image:

```bash
make backend-image
```

This runs the Dockerfile build for `docker/demo/backend.Dockerfile` and tags the
result as `repo2ree-backend:latest`.

Build and load the agent image (agent process + embedded executor/tools
bundles):

```bash
make agent-image
```

## Run With Local Images

```bash
REPO2REE_FRONTEND_IMAGE=repo2ree-frontend:latest \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:latest \
docker compose up
```

Then open `http://localhost:3000`.

The compose stack publishes:

| Service | Port | Notes |
|---|---:|---|
| `frontend` | `3000` | Caddy serves the Vite bundle and proxies `/api/*`. |
| `backend` | `8000` | FastAPI API. Exposed directly for debugging. |

The agent service mounts `/var/run/docker.sock` and launches workbench
containers; the backend has no Docker access at all. The workbench containers
do not receive the host socket either; they run privileged Docker-in-Docker
with their own daemon.

## Compose Storage

`docker-compose.yml` creates two named volumes:

| Volume | Mounted at | Purpose |
|---|---|---|
| `repo2ree-demo-data` | `/app/.repo2ree` in the backend | Backend-local metadata such as upload staging and workbench registry. |
| `repo2ree-agent-state` | `/var/lib/repo2ree-agent` in the agent | The agent's stable identity across container replacements. |

REE execution state lives in per-REE Docker volumes created by the supervisor,
not inside `repo2ree-demo-data`.

## Runtime Configuration

Backend variables:

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_STAGING_DIR` | `.repo2ree/upload-staging` | Temporary upload landing zone before files enter a workbench. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Registry file mapping REE ids to workbench containers and volumes. |
| `OTLP_ENDPOINT` | unset | OTLP collector base URL. |
| `TRACE_FILE` | unset | Local NDJSON trace sink when no collector is configured. |

Frontend variables:

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_UPSTREAM` | `backend:8000` | Runtime Caddy upstream for `/api/*` in the Nix-built frontend image. |
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
- Run the frontend image with `BACKEND_UPSTREAM` set to the backend host and
  port reachable from the Caddy container.
- Persist backend `.repo2ree` state and do not treat workbench Docker volumes as
  disposable while REEs are active.

The API is the hosted long-running process today. The supervisor is a library,
not a separate daemon.
