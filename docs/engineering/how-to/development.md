# How to set up repo2ree for development

> Status: current contributor setup (2026-08). This is for people developing
> or operating repo2ree itself. User-facing service guides should live outside
> `docs/engineering/`.

repo2ree is a Python workspace with a React/Vite GUI. Most integration and
browser flows need Docker because the agent provisions the default
`docker:dind` workbench. Run `just e2e-bundles` first to build the executor and
tools that the agent injects.

## Recommended toolchain

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
- Node/npm compatible with the GUI lockfile
- Docker
- Playwright browser dependencies, if running e2e tests

## Initial setup

From the repository root:

```bash
cp .env.example .env
uv sync --all-packages
npm --prefix gui ci
```

Important local paths:

| Path | Purpose |
|---|---|
| `.repo2ree/` | Local API/runtime state. Gitignored. |
| `.venv/` | Python virtualenv created by `uv` or `.envrc`. Gitignored. |
| `gui/node_modules/` | GUI npm dependencies. Gitignored. |
| `test-artifacts/` | The one artifact root: coverage (by runtime, then tier), traces, Playwright output, logs. Gitignored. |

## Run the app locally

Start the API:

```bash
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

Build the executor and tools closures that a source-run agent injects into each
workbench:

```bash
just e2e-bundles
```

Start the agent in another shell. It dials the API and owns the Docker runtime;
without a connected agent, REE provisioning cannot complete:

```bash
REPO2REE_EXEC_BUNDLE=$PWD/dist/bundles/exec \
REPO2REE_TOOLS_BUNDLE=$PWD/dist/bundles/tools \
uv run --package repo2ree-agent python -m repo2ree_agent
```

For trusted local iteration, add `WORKBENCH_DOCKER_MODE=host-socket` to share
the host daemon's image cache. The default `dind` mode gives each workbench its
own nested daemon and stronger separation.

Start the GUI in another shell:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix gui run dev -- --host
```

Then open the URL printed by Vite, usually `http://localhost:5173`.

The GUI reads `VITE_API_BASE_URL` at build/dev-server time. In local dev,
point it at the API. In the Docker demo image, the GUI uses same-origin
`/api` and Caddy proxies API traffic to the backend service.

## Workbenches

The implemented execution path provisions one persistent Docker-in-Docker
workbench per REE from the pinned upstream `docker:dind` bench, with the
executor/tools bundles injected by the agent. Build the bundles before running
Docker-gated integration or e2e flows:

```bash
just e2e-bundles
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
| `UPLOAD_MAX_BYTES` | 2 GiB | Maximum size of one staged upload. |
| `UPLOAD_STAGING_MAX_BYTES` | 8 GiB | Aggregate budget for concurrent staged uploads. |
| `UPLOAD_TTL_SECONDS` | `3600` | Lifetime of an abandoned staged upload and its token. |
| `WORKBENCH_REGISTRY_FILE` | `.repo2ree/workbench-registry.json` | Control-plane map from REE id to agent, opaque workbench reference, and workbench specification. |
| `REE_INDEX_FILE` | `.repo2ree/ree-index.json` | Durable index of sealed REEs and archive attestations. |
| `RUN_REGISTRY_DIR` | `.repo2ree/runs` | Durable background-run records. |
| `RUN_MAX_WORKERS` | `4` | Maximum concurrent workbench commands and API worker threads. |
| `OTLP_ENDPOINT` | unset | OTLP collector base URL for API and agent traces/metrics/logs (see `observability/`). |
| `OTEL_EXPORTER_OTLP_HEADERS` | unset | Headers for authenticated OTLP ingest (e.g. ClickStack's `authorization=<key>`). |
| `TRACE_FILE` | unset | Local NDJSON trace sink for API/agent spans when no collector is used. |
| `LOG_LEVEL` | `INFO` | Python log level for API, agent, and executor processes. |
| `VITE_API_BASE_URL` | unset | GUI API origin for local Vite builds/dev server. |

Agent variables:

| Variable | Default | Purpose |
|---|---|---|
| `WORKBENCH_API_WS_URL` | `ws://localhost:8000/agent/connect` | Control-plane WebSocket dialed by the agent. |
| `WORKBENCH_AGENT_ID` | generated | Explicit stable agent identity override. |
| `WORKBENCH_AGENT_STATE_DIR` | `~/.repo2ree` | Storage used to persist a generated agent identity. |
| `WORKBENCH_DOCKER_MODE` | `dind` | `dind` for a nested daemon or `host-socket` for trusted local iteration. |

Containerized dev/demo runs may also need `DOCKER_GID`, the numeric group id of
the host Docker socket:

```bash
stat -c '%g' /var/run/docker.sock
```

## Package layout

The Python workspace members are:

| Package | Role |
|---|---|
| `protocol` | Typed command/result/log/tracing contract shared across host and workbench. |
| `core` | Execution handlers and REE filesystem/domain logic. Runs inside the bench (injected by the agent). |
| `executor` | `repo2ree-exec`, the one-shot in-bench command surface over `core`. |
| `supervisor` | Host-side workbench lifecycle and command dispatch. |
| `agent` | The deployable that owns the container runtime and injects the executor/tools bundles. |
| `api` | FastAPI surface over the supervisor and service storage. |

The GUI lives under `gui/` and is a Vite/React app.

## Common commands

```bash
# Python workspace dependencies
uv sync --all-packages

# GUI dependencies
npm --prefix gui ci

# GUI checks
just gui-checks

# Backend checks
just be-checks

# Executor/tools bundles for Docker-gated tiers
just e2e-bundles
```

For the full test map, see [testing.md](testing.md).
