.PHONY: \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks supervisor-checks api-checks executor-checks \
	be-tests be-unit-tests be-integration-tests \
	core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests \
	be-coverage be-coverage-unit be-coverage-context \
	test-checks \
	workbench-image \
	run-api e2e-tests e2e-demo e2e-coverage

# ================================================
# Frontend — checks and tests
# ================================================

fe-checks:
	@echo "Running frontend checks..."
	cd frontend && \
		echo "Running TypeScript compiler (app)..." && \
		npx tsc -p tsconfig.app.json && \
		echo "Running TypeScript compiler (e2e)..." && \
		npx tsc -p tsconfig.e2e.json && \
		echo "Running Biome..." && \
		npx biome check --write src tests playwright.config.ts && \
		echo "Running knip..." && \
		npx knip && \
		echo "Running dependency-cruiser..." && \
		npx depcruise src tests

fe-tests:
	@echo "Running frontend unit tests..."
	cd frontend && npx vitest run

# ================================================
# Backend - checks
# ================================================

protocol-checks:
	@echo "Running protocol checks..."
	ruff check protocol/src
	ruff format protocol/src
	mypy protocol/src

core-checks:
	@echo "Running core checks..."
	ruff check core/src core/tests
	ruff format core/src core/tests
	mypy core/src core/tests

supervisor-checks:
	@echo "Running supervisor checks..."
	ruff check supervisor/src supervisor/tests
	ruff format supervisor/src supervisor/tests
	mypy supervisor/src supervisor/tests

api-checks:
	@echo "Running api checks..."
	ruff check api/src api/tests
	ruff format api/src api/tests
	mypy api/src api/tests

executor-checks:
	@echo "Running executor checks..."
	ruff check executor/src executor/tests
	ruff format executor/src executor/tests
	mypy executor/src executor/tests

be-checks: protocol-checks core-checks supervisor-checks api-checks executor-checks

# ================================================
# Backend - tests
# ================================================

# Unit tests — single-component, no external infra.
core-unit-tests:
	pytest core/tests/unit

api-unit-tests:
	pytest api/tests/unit

executor-tests:
	pytest executor/tests

be-unit-tests: core-unit-tests api-unit-tests executor-tests

# Integration tests — flows spanning multiple components.
core-integration-tests:
	pytest core/tests/integration

# Real-component API tier: the actual FastAPI app over HTTP against real
# workbench containers. Skips when docker or the image is absent. Spans land
# in test-results/api-integration/traces.ndjson for post-run inspection.
api-integration-tests:
	pytest api/tests/integration

# Real workbench e2e: provisions a container from the workbench image and
# drives it over the live docker exec transport. Skips when docker or the
# image is absent (build it with `make workbench-image`).
supervisor-integration-tests:
	pytest supervisor/tests/integration

be-integration-tests: core-integration-tests api-integration-tests supervisor-integration-tests

# Per-package and full suites.
core-tests: core-unit-tests core-integration-tests

api-tests: api-unit-tests api-integration-tests

supervisor-tests: supervisor-integration-tests

be-tests: be-unit-tests be-integration-tests

# ================================================
# Coverage
# ================================================
#
# Both targets write an HTML report to htmlcov/ alongside the terminal
# summary. The `--cov` source list lives in [tool.coverage.run] in
# pyproject.toml, so a bare `--cov` is all pytest needs here.

# Container-free tiers in one process: fast and deterministic, runs anywhere.
# The Docker-gated transport (supervisor manager, hbom profilers) is not
# exercised, so it reads as uncovered — this number is a floor, not the truth.
be-coverage-unit:
	pytest core/tests/unit api/tests/unit executor/tests core/tests/integration \
		--cov --cov-report=term-missing --cov-report=html

# Full suite: the honest number, but the integration tiers skip silently
# without docker + the workbench image (build it with `make workbench-image`).
#
# Two invocations, not one: the api unit and integration tiers must run in
# separate processes (they collide on OpenTelemetry's set-once tracer provider
# — the tier conftests enforce this). The first run measures everything bar the
# api integration tier and writes .coverage fresh; the second appends the api
# integration tier and reports the combined total.
be-coverage:
	pytest core/tests api/tests/unit supervisor/tests executor/tests \
		--cov --cov-report=
	pytest api/tests/integration \
		--cov --cov-append --cov-report=term-missing --cov-report=html

# Per-test coverage: same two-process split as be-coverage, but each line is
# tagged with the test that executed it (--cov-context=test). The HTML report
# is built with `coverage html --show-contexts` so each source line lists which
# tests hit it (use the filter box in htmlcov/index.html to narrow to one test).
# --show-contexts is kept on this target only, so the plain be-coverage report
# stays uncluttered.
be-coverage-context:
	pytest core/tests api/tests/unit supervisor/tests executor/tests \
		--cov --cov-context=test --cov-report=
	pytest api/tests/integration \
		--cov --cov-append --cov-context=test --cov-report=
	coverage html --show-contexts
	coverage report

# ================================================
# End-to-end tests
# ================================================

e2e-tests:
	cd frontend && npm exec -- playwright test -c playwright.config.ts --project=e2e

e2e-demo:
	cd frontend && npm exec -- playwright test -c playwright.config.ts --project=demo

# Backend launcher. No --reload: reload spawns a child process the coverage
# harness can't see, and e2e-coverage needs to own (and measure) this exact
# process. Serves the same app the frontend's VITE_API_BASE_URL points at.
# Needs docker + the workbench image, since requests provision real workbenches.
run-api:
	uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 > fastapi.log 2>&1

# Full-stack e2e coverage: browser (frontend) + server (backend) in one run.
#
# The backend is started *under* coverage (you can't measure an already-running
# server), the e2e suite runs with E2E_COVERAGE=1 so the jsCoverage fixture
# captures browser V8 coverage, then the backend gets a graceful SIGTERM so
# coverage flushes its data on shutdown. Two reports come out: backend
# (htmlcov-e2e/) and frontend (frontend/coverage/frontend/). Needs docker + the
# workbench image + browsers, like the e2e suite itself.
#
# Backend data uses its own COVERAGE_FILE so it never clobbers be-coverage's.
E2E_COVERAGE_FILE = $(CURDIR)/.coverage.e2e

e2e-coverage:
	@echo ">> starting backend under coverage on :8000"
	@rm -f $(E2E_COVERAGE_FILE) $(E2E_COVERAGE_FILE).*
	@rm -rf frontend/test-results/e2e-coverage/raw
	@set -e; \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage run --parallel-mode \
		-m uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 > fastapi.log 2>&1 & \
	api_pid=$$!; \
	trap 'kill -TERM $$api_pid 2>/dev/null || true' EXIT; \
	for i in $$(seq 1 30); do \
		curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1 && break; sleep 1; \
	done; \
	status=0; \
	( cd frontend && E2E_COVERAGE=1 npm exec -- playwright test \
		-c playwright.config.ts --project=e2e ) || status=$$?; \
	echo ">> stopping backend (SIGTERM) so coverage flushes"; \
	kill -TERM $$api_pid 2>/dev/null || true; \
	wait $$api_pid 2>/dev/null || true; \
	trap - EXIT; \
	echo ">> backend coverage"; \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage combine; \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage html -d htmlcov-e2e; \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage report; \
	echo ">> frontend coverage"; \
	( cd frontend && node scripts/gen-frontend-coverage.mjs ); \
	exit $$status

# ================================================
# Build
# ================================================

workbench-image:
	@echo "Staging untracked executor sources for nix..."
	git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor 2>/dev/null || true
	@echo "Building workbench image..."
	nix build .#workbench-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-workbench:latest"
