# How to deploy repo2ree

> Status: current demo/dev deployment shape (2026-08). This is not yet a
> hardened production runbook. The current stack is useful for local demos and
> engineering validation.

repo2ree has three deployed surfaces today:

- `backend`: the FastAPI API — pure control plane. It never touches Docker;
  workbench operations go to whichever agents have dialed in.
- `agent`: the workbench agent. It holds the docker socket, dials the backend
  over an outbound WebSocket, provisions benches, and injects its embedded
  executor and tools. It has its own compose file
  (`docker-compose.agent.yml`) and lifecycle, so it can run wherever benches
  should live. The control-plane stack contains only the GUI and backend.
- `gui`: a static Vite bundle served by Caddy. Caddy also reverse-proxies
  `/api/*` to the backend so the browser uses one origin.

Each REE gets a separate workbench container named `repo2ree-wb-{ree_id}` plus
Docker volumes for `/ree` state and the nested Docker daemon.

## Run with published images

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

Set the agent image with `REPO2REE_AGENT_IMAGE` in its compose file. It defaults
to `docker.io/vuducanh1112/repo2ree-agent:edge`.

The backend image catalog defines the available per-REE workbench images
(`api/src/repo2ree_api/settings.py`). Its default is a pinned upstream
`docker:dind` digest; the agent injects the executor and tools. Override
`WORKBENCH_IMAGE_CATALOG` to publish a different catalog.

## Build images locally

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

## Publishing images

Publishing treats the GUI, backend, and agent as one image candidate. The
candidate is pushed under a Git revision, validated by manifest digest, then
promoted as one set:

```bash
make push-gate                       # source + local-image validation
make push-image-candidate            # push the three images as :<git-rev>
make validate-image-candidate        # test their exact registry digests
make promote-image-candidate-to-edge # move edge to the validated digests
```

`push-image-candidate` refuses a dirty tree and requires
`IMAGE_CANDIDATE_REV` to name that tree. It never moves `edge`.

`validate-image-candidate` resolves every component in both registries and
requires the corresponding manifests to have identical digests. Both GUI e2e
projects then run against explicit `@sha256` references rather than mutable
revision tags. A successful run writes one ignored, tab-separated receipt at
`.validation-certificates/image-candidates/<rev>.validated`. It records the
candidate revision and one digest row for each registry/image pair. The file is
moved into place only after both validation suites pass.

`promote-image-candidate-to-edge` requires that receipt, re-resolves every
candidate tag, and promotes from the recorded `@sha256` references. It verifies
each resulting `edge` tag and stops on failure. A candidate does not expire by
age; it becomes stale when a recorded revision tag no longer resolves to its
validated digest.

The candidate defaults to the current Git revision. Name another explicitly:

```bash
make validate-image-candidate IMAGE_CANDIDATE_REV=<rev>
make verify-image-candidate IMAGE_CANDIDATE_REV=<rev>
make promote-image-candidate-to-edge IMAGE_CANDIDATE_REV=<rev>
```

When builds and registry credentials live on different machines (e.g. nix
only in the dev container, docker login only on the host), replace
`push-image-candidate` with the archive pair: run `make image-archives` in the
dev container, copy `dist/images/` to the host, then run
`make push-image-archives`. The archive directory carries an
`IMAGE_CANDIDATE_REV` stamp, so the host cannot accidentally push the tarballs
under a different tag. Continue with validation and promotion using
`IMAGE_CANDIDATE_REV=$(cat dist/images/IMAGE_CANDIDATE_REV)`.

All images always move together because the agent↔control-plane protocol
requires matching versions. Registries default to GHCR and Docker Hub under
`vuducanh1112`; override `REGISTRIES`, `GHCR_NAMESPACE`, or
`DOCKERHUB_NAMESPACE` for another deployment set.

## Run with local images

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

## Compose storage

Each compose file creates one named volume:

| Volume | Mounted at | Purpose |
|---|---|---|
| `repo2ree-demo-data` | `/app/.repo2ree` in the backend | Backend-local metadata such as upload staging and workbench registry. |
| `repo2ree-agent-state` | `/var/lib/repo2ree-agent` in the agent | The agent's stable identity across container replacements (created by `docker-compose.agent.yml`, with a pinned volume name so it survives recreation). |

REE execution state lives in per-REE Docker volumes created by the selected
agent's runtime at the supervisor's request, not inside `repo2ree-demo-data`.

`docker compose down` keeps both volumes, which is what a stack you intend to
restart wants. To stop a stack and reclaim everything it stored — the compose
volumes plus any workbench containers and per-REE volumes left behind — use
`scripts/test-stack/image-stack.sh down --volumes` (`make stack-clean`), or
`scripts/test-stack/workbench-cleanup.sh` for the workbench leftovers alone —
the latter also sweeps unreferenced anonymous volumes, which the bench image
declares for itself and which nothing can address once their container is gone.

## Runtime configuration

Backend variables:

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_STAGING_DIR` | `.repo2ree/upload-staging` | Temporary upload landing zone before files enter a workbench. |
| `UPLOAD_MAX_BYTES` | 2 GiB | Per-upload staging limit. |
| `UPLOAD_STAGING_MAX_BYTES` | 8 GiB | Aggregate staging budget. |
| `UPLOAD_TTL_SECONDS` | `3600` | Abandoned-upload and token lifetime. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Registry mapping REE ids to agents, opaque workbench references, and workbench specifications. |
| `REE_INDEX_FILE` | `.repo2ree/ree-index.json` | Durable index of sealed REEs and archive attestations. |
| `RUN_REGISTRY_DIR` | `.repo2ree/runs` | Durable background-run state. |
| `RUN_MAX_WORKERS` | `4` | Concurrent workbench-command and worker-thread limit. |
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

## Security and isolation notes

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

## Operational checks

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

## Non-Compose deployments

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
