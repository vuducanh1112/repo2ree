# repo2ree

Public product docs live in [docs/public/README.md](docs/public/README.md).
Contributor setup, deployment, test docs, and backend design rationale live under
[docs/engineering/](docs/engineering/README.md).
Research and paper-facing notes live under
[docs/research/](docs/research/).

## Quick demo

To try the app locally with Docker, use the published Docker Hub images. The
compose stack is control plane only (frontend + API); workbenches are
provisioned by an agent that runs separately and dials the API:

```bash
docker compose up -d
docker compose -f docker-compose.agent.yml up -d
```

The agent stack is a separate compose file on purpose — the agent dials the
control plane over an outbound WebSocket and can run anywhere a container
runtime lives, so its lifecycle stays independent. Then open
`http://localhost:3000`.

### Run without cloning the repository

Fetch each compose file straight from the repository and start it from stdin —
no clone needed. The first line brings up the control plane under the
`-p repo2ree` project (stable container/volume names, clean teardown later);
the second brings up the agent, which carries its own `repo2ree-agent` project
name inside the file, so no `-p` is needed for it:

```bash
curl -fsSL https://codeberg.org/vuducanh1112/repo2ree/raw/branch/main/docker-compose.yml \
  | docker compose -p repo2ree -f - up -d
curl -fsSL https://codeberg.org/vuducanh1112/repo2ree/raw/branch/main/docker-compose.agent.yml \
  | docker compose -f - up -d
```

The agent dials `host.docker.internal:8000` by default, which resolves to the
control plane you just started on the same host. Then open
`http://localhost:3000`.

To stop it — no compose file needed, the project name is enough. The agent
container lives outside the stack, so stop it separately:

```bash
docker compose -p repo2ree-agent down   # stop the separate agent stack
docker compose -p repo2ree down         # stop control plane: containers + network
docker compose -p repo2ree down -v      # also delete the demo-data volume
```

To refresh to the latest published images, append `--pull always` to the `up`
command.

### Build the images locally

To build the images locally from this repository:

```bash
make frontend-image
make backend-image
make agent-image
```

Then run compose with the local image tags, and start the agent stack
pointed at its local tag:

```bash
REPO2REE_FRONTEND_IMAGE=repo2ree-frontend:local \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:local \
docker compose up -d

REPO2REE_AGENT_IMAGE=repo2ree-agent:local \
docker compose -f docker-compose.agent.yml up -d
```

The per-REE workbench env image isn't a compose variable: benches provision
from the backend's image catalog (a pinned upstream `docker:dind` by
default), with the executor injected by the agent at provision time.

Compose starts the frontend on port `3000` and the API on port `8000`; the
API container stores its persistent data under `/app/.repo2ree`. The agent
container runs outside the stack and mounts `/var/run/docker.sock` because it
owns workbench container lifecycle.

For more detail, see
[docs/engineering/deployment.md](docs/engineering/deployment.md).


## Local development

Full contributor setup lives in
[docs/engineering/development.md](docs/engineering/development.md).

1. Start the backend from the repository root:

```bash
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Build the executor and tools bundles the agent injects into workbenches.
   The published agent image ships them baked in, but an agent run from
   source needs them built and pointed at explicitly — without them,
   provisioning fails its executor probe (`"repo2ree-exec": executable file
   not found`). Rebuild after changing `core/` or `executor/`, or benches
   keep running the old executor:

```bash
make e2e-bundles   # builds test-artifacts/{exec-bundle,tools-bundle} via nix
```

3. Start the workbench agent, which dials the API and owns the container
   runtime (workbenches only provision while it is connected):

```bash
REPO2REE_EXEC_BUNDLE=$PWD/test-artifacts/exec-bundle \
REPO2REE_TOOLS_BUNDLE=$PWD/test-artifacts/tools-bundle \
uv run --package repo2ree-agent python -m repo2ree_agent
```

For faster local iteration, you can share the host Docker daemon with
workbenches:

```bash
REPO2REE_EXEC_BUNDLE=$PWD/test-artifacts/exec-bundle \
REPO2REE_TOOLS_BUNDLE=$PWD/test-artifacts/tools-bundle \
WORKBENCH_DOCKER_MODE=host-socket \
uv run --package repo2ree-agent python -m repo2ree_agent
```

This reuses the host Docker image cache, but it weakens workbench isolation and
is intended for trusted local development only. The default `dind` mode keeps a
separate Docker daemon per workbench.

4. Install frontend dependencies:

```bash
npm --prefix frontend ci
```

5. Start the frontend dev server:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --host
```

## E2E test

For the full test map, see
[docs/engineering/testing.md](docs/engineering/testing.md).

```bash
make e2e-tests
```
