# repo2ree - Engineering Development Setup

> Status: current contributor setup (2026-06). This is for people developing
> or operating repo2ree itself. User-facing service guides should live outside
> `docs/engineering/`.

repo2ree is a Python workspace plus a React/Vite frontend. Workbench
containers are driven by the agent, so most realistic flows need a reachable
Docker daemon. Every tier — the browser e2e/demo runs and the docker-gated
integration tiers — provisions the production default bench: upstream
`docker:dind` with the executor and tools injected by the agent
(`make e2e-bundles` builds what the agent injects).

## Recommended Toolchain

Use the Nix dev shell when possible:

```bash
nix develop
```

The shell provides Python 3.13, `uv`, Node, Docker client tools, `kubectl`,
Graphviz, and Playwright browser binaries. The shell also sets the Playwright
browser environment used by the e2e tests.

If you use `direnv`, allow the repo once:

```bash
direnv allow .
```

`.envrc` enters the flake, creates `.venv` when needed, runs
`uv sync --all-packages`, and activates the virtualenv.

Without Nix, install equivalent tools yourself:

- Python `~=3.13`
- `uv`
- Node/npm compatible with the frontend lockfile
- Docker
- Playwright browser dependencies, if running e2e tests

## Initial Setup

From the repository root:

```bash
cp .env.example .env
uv sync --all-packages
npm --prefix frontend ci
```

Important local paths:

| Path | Purpose |
|---|---|
| `.repo2ree/` | Local API/runtime state. Gitignored. |
| `.venv/` | Python virtualenv created by `uv` or `.envrc`. Gitignored. |
| `frontend/node_modules/` | Frontend npm dependencies. Gitignored. |
| `test-artifacts/` | Logs, traces, coverage, Playwright output. Gitignored. |

## Run The App Locally

Start the API:

```bash
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in another shell:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --host
```

Then open the URL printed by Vite, usually `http://localhost:5173`.

The frontend reads `VITE_API_BASE_URL` at build/dev-server time. In local dev,
point it at the API. In the Docker demo image, the frontend uses same-origin
`/api` and Caddy proxies API traffic to the backend service.

## Workbench Benches

The implemented execution path provisions one persistent Docker-in-Docker
workbench per REE from the pinned upstream `docker:dind` bench, with the
executor/tools bundles injected by the agent. Build the bundles before running
Docker-gated integration or e2e flows:

```bash
make e2e-bundles
```

The current workbench is privileged Docker-in-Docker. It does not receive the
host Docker socket; it runs its own daemon and stores `/var/lib/docker` in a
per-REE Docker volume. The target hardening path is VM-backed workbenches, but
that is not the current local setup.

## Devcontainer

The devcontainer uses `docker-compose.dev.yml` and the `dev` service:

```bash
docker compose -f docker-compose.dev.yml up --build dev
```

It mounts the repo at `/repo2ree` and mounts `/var/run/docker.sock` so the
container can reach the host Docker daemon. The entrypoint adjusts the
container's `docker` group to match the socket group before switching to
`nixuser`.

VS Code users can open the folder in the devcontainer. The configured remote
user is `nixuser`.

## Configuration

The API reads `.env` through `pydantic-settings`. Useful local variables:

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_STAGING_DIR` | `.repo2ree/upload-staging` | Temporary HTTP upload landing zone before files enter a workbench. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Host-side map from REE id to workbench container/volume. |
| `OTLP_ENDPOINT` | unset | OTLP collector base URL for traces/metrics. |
| `TRACE_FILE` | unset | Local NDJSON trace sink when no collector is used. |
| `VITE_API_BASE_URL` | unset | Frontend API origin for local Vite builds/dev server. |

Containerized dev/demo runs may also need `DOCKER_GID`, the numeric group id of
the host Docker socket:

```bash
stat -c '%g' /var/run/docker.sock
```

## Package Layout

The Python workspace members are:

| Package | Role |
|---|---|
| `protocol` | Typed command/result/log/tracing contract shared across host and workbench. |
| `core` | Execution handlers and REE filesystem/domain logic. Runs inside the bench (injected by the agent). |
| `executor` | `repo2ree-exec`, the one-shot in-bench command surface over `core`. |
| `supervisor` | Host-side workbench lifecycle and command dispatch. |
| `agent` | The deployable that owns the container runtime and injects the executor/tools bundles. |
| `api` | FastAPI surface over the supervisor and service storage. |

The frontend lives under `frontend/` and is a Vite/React app.

## Common Commands

```bash
# Python workspace dependencies
uv sync --all-packages

# Frontend dependencies
npm --prefix frontend ci

# Frontend checks
make fe-checks

# Backend checks
make be-checks

# Executor/tools bundles for Docker-gated tiers
make e2e-bundles
```

For the full test map, see [testing.md](testing.md).
