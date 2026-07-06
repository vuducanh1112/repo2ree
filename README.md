# repo2ree

Public product docs live in [docs/public/README.md](docs/public/README.md).
Contributor setup, deployment, and test docs live under
[docs/engineering/](docs/engineering/).
Research and paper-facing notes live under
[docs/research/](docs/research/).

## Quick demo

To try the app locally with Docker, use the published Docker Hub images. The
compose stack is control plane only (frontend + API); workbenches are
provisioned by an agent that runs separately and dials the API:

```bash
docker compose up -d
docker run -d --name repo2ree-agent \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v repo2ree-agent-state:/var/lib/repo2ree-agent \
  --add-host host.docker.internal:host-gateway \
  -e WORKBENCH_API_WS_URL=ws://host.docker.internal:8000/agent/connect \
  docker.io/vuducanh1112/repo2ree-agent:edge
```

Then open `http://localhost:3000`.

### Run without cloning the repository

Fetch the compose file straight from the repository and start the stack from
stdin. The `-p repo2ree` project name gives stable container/volume names and a
clean teardown later:

```bash
curl -fsSL https://codeberg.org/vuducanh1112/repo2ree/raw/branch/main/docker-compose.yml \
  | docker compose -p repo2ree -f - up -d
```

Then open `http://localhost:3000`.

To stop it — no compose file needed, the project name is enough. The agent
container lives outside the stack, so stop it separately:

```bash
docker compose -p repo2ree down      # stop and remove containers + network
docker compose -p repo2ree down -v   # also delete the demo-data volume
docker rm -f repo2ree-agent          # the separately started agent
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

Then run compose with the local image tags, and start the agent from its
local tag (same `docker run` as above with `repo2ree-agent:local` as the
image):

```bash
REPO2REE_FRONTEND_IMAGE=repo2ree-frontend:local \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:local \
docker compose up
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

2. Start the workbench agent, which dials the API and owns the container
   runtime (workbenches only provision while it is connected):

```bash
uv run --package repo2ree-agent python -m repo2ree_agent
```

For faster local iteration, you can share the host Docker daemon with
workbenches:

```bash
WORKBENCH_DOCKER_MODE=host-socket uv run --package repo2ree-agent python -m repo2ree_agent
```

This reuses the host Docker image cache, but it weakens workbench isolation and
is intended for trusted local development only. The default `dind` mode keeps a
separate Docker daemon per workbench.

3. Install frontend dependencies:

```bash
npm --prefix frontend ci
```

4. Start the frontend dev server:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --host
```

## E2E test

For the full test map, see
[docs/engineering/testing.md](docs/engineering/testing.md).

```bash
make e2e-tests
```
