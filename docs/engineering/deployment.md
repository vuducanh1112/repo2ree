# repo2ree - Engineering Deployment Notes

> Status: current demo/dev deployment shape (2026-06). This is not yet a
> hardened production runbook. The current stack is useful for local demos and
> engineering validation.

repo2ree has two deployed surfaces today:

- `backend`: the FastAPI API. It imports the supervisor library and provisions
  workbench containers through Docker.
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
| `REPO2REE_WORKBENCH_IMAGE` | `docker.io/vuducanh1112/repo2ree-workbench:edge` | Image the backend launches for per-REE workbenches. |

The backend receives `WORKBENCH_IMAGE` from `REPO2REE_WORKBENCH_IMAGE` because
it launches workbench containers through the mounted Docker socket after
startup.

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

Build and load the workbench image:

```bash
make workbench-image
```

The API expects `repo2ree-workbench:latest` unless `WORKBENCH_IMAGE` is
overridden.

## Run With Local Images

```bash
REPO2REE_FRONTEND_IMAGE=repo2ree-frontend:latest \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:latest \
REPO2REE_WORKBENCH_IMAGE=repo2ree-workbench:latest \
docker compose up
```

Then open `http://localhost:3000`.

The compose stack publishes:

| Service | Port | Notes |
|---|---:|---|
| `frontend` | `3000` | Caddy serves the Vite bundle and proxies `/api/*`. |
| `backend` | `8000` | FastAPI API. Exposed directly for debugging. |

The backend mounts `/var/run/docker.sock` so the supervisor can launch
workbench containers. The workbench containers themselves do not receive the
host Docker socket; they run privileged Docker-in-Docker with their own daemon.

## Compose Storage

`docker-compose.yml` creates one named volume:

| Volume | Mounted at | Purpose |
|---|---|---|
| `repo2ree-demo-data` | `/app/.repo2ree` in the backend | Backend-local metadata such as upload staging and workbench registry. |

REE execution state lives in per-REE Docker volumes created by the supervisor,
not inside `repo2ree-demo-data`.

## Runtime Configuration

Backend variables:

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_STAGING_DIR` | `.repo2ree/upload-staging` | Temporary upload landing zone before files enter a workbench. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Registry file mapping REE ids to workbench containers and volumes. |
| `WORKBENCH_IMAGE` | Set by compose from `REPO2REE_WORKBENCH_IMAGE` | Image used for per-REE workbenches. |
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

- The backend can reach the host Docker daemon.
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
docker image inspect "${REPO2REE_WORKBENCH_IMAGE:-docker.io/vuducanh1112/repo2ree-workbench:edge}"
docker volume ls --filter 'name=repo2ree'
```

If workbench provisioning fails, check:

- The backend container can access `/var/run/docker.sock`.
- The configured workbench image can be pulled by the same Docker daemon the
  backend uses.
- The host supports privileged containers.
- Workbench logs with `docker logs repo2ree-wb-{ree_id}`.
- Nested Docker logs inside the workbench at `/var/log/dockerd.log`.

## Non-Compose Deployments

For a non-compose deployment, keep the same boundaries:

- Run the backend where it can reach the intended Docker daemon.
- Provide the configured workbench image to that daemon.
- Run the frontend image with `BACKEND_UPSTREAM` set to the backend host and
  port reachable from the Caddy container.
- Persist backend `.repo2ree` state and do not treat workbench Docker volumes as
  disposable while REEs are active.

The API is the hosted long-running process today. The supervisor is a library,
not a separate daemon.
