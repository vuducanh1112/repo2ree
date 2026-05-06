# repo2ree

## Quick demo

To try the app locally with Docker:

```bash
docker compose -f docker-compose.demo.yml up --build
```

Then open `http://localhost:3000`.

This starts the frontend on port `3000` and the API on port `8000`.
The backend container mounts `/var/run/docker.sock` because several repo2ree API flows shell out to Docker. In the demo compose setup, the backend stays rootless and stores its persistent data under `/app/.repo2ree`.

To override the frontend API URL, set `VITE_API_BASE_URL`; to override demo storage paths, use `DEMO_WORKSPACE_STORAGE_DIR` and `DEMO_REVIEWS_STORAGE_DIR` because those paths are evaluated inside the backend container.


## Local development

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

```bash
npm --prefix /repo2ree/frontend exec -- playwright test -c /repo2ree/playwright.config.ts /repo2ree/tests/e2e/ree-create-python-hello-world.spec.ts
```
