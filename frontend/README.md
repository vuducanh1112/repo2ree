# repo2ree Web UI

Simple Vite + React frontend for the repo2ree API.

## Demo run

From the repository root:

```bash
docker compose -f docker-compose.demo.yml up --build
```

Then open `http://localhost:3000`.

The frontend talks to the backend at `http://localhost:8000`.

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
