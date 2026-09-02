# repo2ree

Public product docs live in [docs/public/README.md](docs/public/README.md).
Contributor setup, deployment, test docs, and backend design rationale live under
[docs/engineering/](docs/engineering/README.md). The complete documentation map
starts at [docs/README.md](docs/README.md).
Research and paper-facing notes live under
[docs/research/](docs/research/).

## Quick demo

To try the app locally with Docker, use the published Docker Hub images. The
compose stack is control plane only (GUI + API); workbenches are
provisioned by a Docker provider that runs separately and dials the API:

```bash
docker compose up -d
docker compose -f docker-compose.workbench.yml up -d
```

The provider stack is a separate compose file on purpose — the provider dials
the control plane over an outbound WebSocket and can run anywhere a container
runtime lives, so its lifecycle stays independent. Then open
`http://localhost:3000`.

### Run without cloning the repository

Fetch each compose file straight from the repository and start it from stdin —
no clone needed. The first line brings up the control plane under the
`-p repo2ree` project (stable container/volume names, clean teardown later);
the second brings up the provider, which carries its own `repo2ree-provider`
project name inside the file, so no `-p` is needed for it:

```bash
curl -fsSL https://codeberg.org/vuducanh1112/repo2ree/raw/branch/main/docker-compose.yml \
  | docker compose -p repo2ree -f - up -d
curl -fsSL https://codeberg.org/vuducanh1112/repo2ree/raw/branch/main/docker-compose.workbench.yml \
  | docker compose -f - up -d
```

The provider dials `host.docker.internal:8000` by default, which resolves to the
control plane you just started on the same host. Then open
`http://localhost:3000`.

To stop it — no compose file needed, the project name is enough. The provider
container lives outside the stack, so stop it separately:

```bash
docker compose -p repo2ree-provider down   # stop the separate provider stack
docker compose -p repo2ree down         # stop control plane: containers + network
docker compose -p repo2ree down -v      # also delete the demo-data volume
```

To refresh to the latest published images, append `--pull always` to the `up`
command.

### Build the images locally

To build the images locally from this repository:

```bash
just gui-image
just backend-image
just provider-image
```

Then run compose with the local image tags, and start the provider stack
pointed at its local tag:

```bash
REPO2REE_GUI_IMAGE=repo2ree-gui:local \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:local \
docker compose up -d

REPO2REE_PROVIDER_IMAGE=repo2ree-provider-docker:local \
docker compose -f docker-compose.workbench.yml up -d
```

The per-REE workbench env image isn't a compose variable: benches provision
from the backend's image catalog (a pinned upstream `docker:dind` by
default), with the executor injected by the provider at provision time.

Compose starts the GUI on port `3000` and the API on port `8000`; the
API container stores its persistent data under `/app/.repo2ree`. The provider
container runs outside the stack and mounts `/var/run/docker.sock` because it
owns workbench container lifecycle.

For more detail, see
[docs/engineering/how-to/deployment.md](docs/engineering/how-to/deployment.md).


## Local development

Full contributor setup lives in
[docs/engineering/how-to/development.md](docs/engineering/how-to/development.md).

1. Start the backend from the repository root:

```bash
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Build the executor and tools bundles the provider injects into each
   workbench. The published provider image ships them baked in, but a provider
   run from source needs them built and pointed at explicitly — without them,
   provisioning fails its executor probe (`"repo2ree-exec": executable file
   not found`). Rebuild after changing `core/` or `executor/`, or benches
   keep running the old executor:

```bash
just e2e-bundles   # builds dist/bundles/{exec,tools} via nix
```

3. Start the Docker provider, which dials the API and owns the container
   runtime (workbenches only provision while it is connected). It starts
   `repo2ree-workbench` inside each workbench it creates, so there is no second
   process to launch by hand:

```bash
REPO2REE_EXEC_BUNDLE=$PWD/dist/bundles/exec \
REPO2REE_TOOLS_BUNDLE=$PWD/dist/bundles/tools \
uv run --package repo2ree-provider-docker python -m repo2ree_provider_docker
```

The provider dials the control plane on `localhost`, but the workbench it
starts *inside* each bench needs a URL that resolves from within a container.
The provider rewrites a loopback bench URL to `host.docker.internal` (mapped to
the host gateway on every bench it creates) and logs that it did. Set
`PROVIDER_WORKBENCH_API_WS_URL` explicitly when the control plane lives
somewhere else.

For faster local iteration, you can share the host Docker daemon with
workbenches:

```bash
REPO2REE_EXEC_BUNDLE=$PWD/dist/bundles/exec \
REPO2REE_TOOLS_BUNDLE=$PWD/dist/bundles/tools \
PROVIDER_DOCKER_MODE=host-socket \
uv run --package repo2ree-provider-docker python -m repo2ree_provider_docker
```

This reuses the host Docker image cache, but it weakens workbench isolation and
is intended for trusted local development only. The default `dind` mode keeps a
separate Docker daemon per workbench.

The catalog's default bench image is a `dind` image, whose own default command
is `dockerd` — and that cannot start without the `--privileged` this mode
deliberately withholds. The provider notices the bench did not stay up and
restarts it under the injected pause binary, logging that it did so; the
substrate host-socket mode actually uses is the mounted host socket, not that
daemon. This is why the bundles above are not optional here.

#### Or skip the provider entirely

A workbench does not need a provider. It is a process that dials the control
plane and runs REE commands wherever it already is, so starting one by hand is
the lightest local setup there is: no container runtime, no bundles, no image
pulls. Use it when you are working on the authoring lifecycle rather than on
provisioning.

Directly installed workbenches authenticate with an operator credential, and
the control plane rejects them while it is unset. Start the backend from step 1
with one:

```bash
EXTERNAL_WORKBENCH_TOKEN=local-dev \
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

Then start the workbench itself. `--root` is the directory the REE lives in —
`ree.json`, the snapshot, `workspace/`, `artifacts/` — and it defaults to
`/ree`, a path that only makes sense inside a container, so point it somewhere
on your machine:

```bash
uv run --package repo2ree-workbench python -m repo2ree_workbench \
  --root "$PWD/.repo2ree/bench-1" \
  --connect ws://localhost:8000/workbench/connect \
  --token local-dev
```

Unlike the provider's bench-facing URL, `localhost` is right here: this
workbench runs on your machine, not inside a container. The equivalent
environment variables are `WORKBENCH_ROOT`, `WORKBENCH_API_WS_URL` and
`WORKBENCH_AUTH_TOKEN`.

It shows up in the GUI's lab picker as pre-provisioned capacity, offering no
image choice — the environment is whatever you started it in, which is the
point of this mode.

Workbenches are single-use. Releasing an REE drains its workbench and exits the
process, and a fresh start refuses a root that is not empty, so no REE inherits
a previous one's residue. For a second REE, start a second process — with its
own `--root`, and its own `--name`, since a workbench's identity otherwise
persists in `WORKBENCH_STATE_DIR` (`~/.repo2ree`) and two processes sharing one
identity displace each other on the control plane.

4. Install GUI dependencies:

```bash
npm --prefix gui ci
```

5. Start the GUI dev server:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix gui run dev -- --host
```

## E2E test

For the full test map, see
[docs/engineering/how-to/testing.md](docs/engineering/how-to/testing.md).

```bash
just e2e-gui
```
