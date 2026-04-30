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

## Architecture guardrails

New frontend code should follow the current layer boundaries:

- `src/domain`: pure business types and logic. No React, no browser APIs, no `infra`.
- `src/application`: use-case logic, state transitions, and repository/port contracts. No React UI imports.
- `src/infra`: HTTP clients, DTO mappers, and repository implementations that satisfy application ports.
- `src/runtime`: app wiring and environment-specific adapters.
- `src/ui`: React components, route composition, and feature-level hooks that talk to application/runtime boundaries.

When you are deciding where a new module belongs:

- Put it in `domain` if it should run in a test without React, fetch, or app context.
- Put it in `application` if it coordinates workflow or workspace behavior but should still be UI-framework agnostic.
- Put it in `infra` if it knows backend payload shapes, URLs, or repository implementation details.
- Put it in `ui` if it renders or manages interaction state for the browser.
- Prefer importing repositories or application mappers in `ui`; do not import from `src/infra/api` directly unless a new approved boundary is added to `.dependency-cruiser.js`.

`make fe-checks` runs TypeScript, Biome, Knip, and dependency-cruiser. Any dependency boundary violation should fail there before it reaches CI.

## E2E test

```bash
npm --prefix /repo2ree/frontend exec -- playwright test -c /repo2ree/playwright.config.ts /repo2ree/tests/e2e/ree-create-python-hello-world.spec.ts
```
