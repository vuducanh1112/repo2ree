# repo2ree - Engineering Test Guide

> Status: current test layout (2026-06). The suite intentionally separates
> container-free checks from Docker-gated integration and e2e flows.

## Quick Map

| Target | What it runs |
|---|---|
| `make fe-checks` | Frontend TypeScript, Biome, knip, dependency-cruiser. |
| `make fe-tests` | Frontend Vitest tests. |
| `make be-checks` | Ruff, Ruff format, and mypy across Python workspace packages. |
| `make be-unit-tests` | Container-free backend unit tests. |
| `make be-integration-tests` | Integration tiers, including Docker-gated workbench tests when Docker and the image exist. |
| `make be-tests` | Backend unit plus integration tests. |
| `make e2e-tests` | Playwright e2e project against a live API and frontend dev server. |
| `make e2e-demo` | Playwright demo walkthrough project with video. |
| `make e2e-coverage` | Backend coverage plus browser-side frontend coverage for e2e. |

## Before Docker-Gated Tests

Build the executor/tools bundles the agent injects into benches:

```bash
make e2e-bundles
```

The Docker-gated tiers skip when Docker or the bundles are absent. They do
not fake the workbench path; the first run pulls the pinned `docker:dind`
bench image.

## Backend Checks

Run all Python static checks:

```bash
make be-checks
```

Per-package targets are available:

```bash
make protocol-checks
make core-checks
make supervisor-checks
make api-checks
make executor-checks
```

These targets run `ruff check`, `ruff format`, and `mypy` for their package.
They may modify formatting.

## Backend Tests

Fast, container-free tests:

```bash
make be-unit-tests
```

Full backend test suite:

```bash
make be-tests
```

Per-package test targets:

```bash
make core-tests
make api-tests
make supervisor-tests
make executor-tests
```

Important split:

- `core/tests/unit` and `api/tests/unit` are regular unit tests.
- `core/tests/integration` exercises the real command handlers against a temp
  REE tree, without Docker.
- `api/tests/integration` runs the real FastAPI app over HTTP against real
  workbench containers.
- `supervisor/tests/integration` provisions a real workbench and drives the
  real `docker exec -> repo2ree-exec -> core` path.

Do not run `pytest api/tests` as one process. The API unit and integration
tiers intentionally run separately because OpenTelemetry's tracer provider is
process-global. Use:

```bash
make api-unit-tests
make api-integration-tests
```

or:

```bash
pytest api/tests/unit
pytest api/tests/integration
```

## Coverage

Container-free coverage floor:

```bash
make be-coverage-unit
```

Full backend coverage:

```bash
make be-coverage
```

Per-test backend coverage context:

```bash
make be-coverage-context
```

Reports land under `test-artifacts/coverage/`. Coverage data lives under
`test-artifacts/coverage/data/`, configured in `pyproject.toml`.

## Frontend Checks And Tests

Install dependencies:

```bash
npm --prefix frontend ci
```

Run frontend checks:

```bash
make fe-checks
```

Run frontend unit tests:

```bash
make fe-tests
```

`make fe-checks` runs TypeScript for the app and e2e configs, Biome, knip, and
dependency-cruiser.

## End-To-End Tests

The Playwright config is `frontend/playwright.config.ts`. It starts the Vite dev
server on `127.0.0.1:4173` and points the frontend at
`http://localhost:8000`.

Run e2e tests through Make:

```bash
make e2e-tests
```

That target starts the backend on `127.0.0.1:8000`, waits for it to respond,
then runs the Playwright `e2e` project from `frontend/`.

Run the narrated demo flow:

```bash
make e2e-demo
```

Run e2e coverage:

```bash
make e2e-coverage
```

E2E tests provision real workbench containers. The shared e2e fixture attempts
to seal and release the workbench after each test, including failures.

## Artifacts And Logs

All generated test artifacts should stay under `test-artifacts/`.

Useful locations:

| Path | Contents |
|---|---|
| `test-artifacts/api-server.log` | Backend log for plain e2e runs. |
| `test-artifacts/coverage/e2e/backend.log` | Backend log for e2e coverage runs. |
| `test-artifacts/coverage/` | Backend and e2e coverage reports. |
| `frontend/test-artifacts/playwright/` | Playwright traces, screenshots, and videos. |
| `test-artifacts/traces/api-integration/` | API integration trace files and workbench log snapshots. |

When a Docker-gated test fails, inspect both the workbench entrypoint log and
the nested daemon log:

```bash
docker logs repo2ree-wb-{ree_id}
docker exec repo2ree-wb-{ree_id} cat /var/log/dockerd.log
```

## Direct Commands

Direct commands are useful while debugging one tier:

```bash
pytest core/tests/unit
pytest core/tests/integration
pytest api/tests/unit
pytest api/tests/integration
pytest supervisor/tests/integration
pytest executor/tests
```

For one Playwright spec:

```bash
cd frontend
npm exec -- playwright test -c playwright.config.ts --project=e2e tests/e2e/workbench.spec.ts
```
