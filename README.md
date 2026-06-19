# repo2ree

Public product docs live in [docs/public/README.md](docs/public/README.md).
Contributor setup, deployment, and test docs live under
[docs/engineering/](docs/engineering/).
Research and paper-facing notes live under
[docs/research/](docs/research/).

## Quick demo

To try the app locally with Docker, use the published Docker Hub images:

```bash
docker compose up
```

Then open `http://localhost:3000`.

To build the images locally from this repository:

```bash
make frontend-image
make backend-image
make workbench-image
```

Then run compose with the local image tags:

```bash
REPO2REE_FRONTEND_IMAGE=repo2ree-frontend:latest \
REPO2REE_BACKEND_IMAGE=repo2ree-backend:latest \
REPO2REE_WORKBENCH_IMAGE=repo2ree-workbench:latest \
docker compose up
```

This starts the frontend on port `3000` and the API on port `8000`.
The backend container mounts `/var/run/docker.sock` because several repo2ree API flows shell out to Docker. In the demo compose setup, the backend stays rootless and stores its persistent data under `/app/.repo2ree`.

For more detail, see
[docs/engineering/deployment.md](docs/engineering/deployment.md).


## Local development

Full contributor setup lives in
[docs/engineering/development.md](docs/engineering/development.md).

1. Start the backend from the repository root:

```bash
uv run --package repo2ree-api uvicorn repo2ree_api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Install frontend dependencies:

```bash
npm --prefix frontend ci
```

3. Start the frontend dev server:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --host
```

## E2E test

For the full test map, see
[docs/engineering/testing.md](docs/engineering/testing.md).

```bash
make e2e-tests
```
