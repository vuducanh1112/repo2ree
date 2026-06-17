.PHONY: \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks supervisor-checks api-checks executor-checks \
	be-tests be-unit-tests be-integration-tests \
	core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests \
	be-coverage be-coverage-unit be-coverage-context \
	test-checks \
	workbench-image frontend-image frontend-npm-hash \
	e2e-tests e2e-demo e2e-coverage

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
# Backend - tests with coverage
# ================================================
#
# Reports land under test-artifacts/coverage/<variant>/ (one per target, so they
# never clobber each other); the .coverage data lives under
# test-artifacts/coverage/data (set in [tool.coverage.run] in pyproject.toml).
# The `--cov` source list also lives there, so a bare `--cov` is all pytest needs.

# Container-free tiers in one process: fast and deterministic, runs anywhere.
# The Docker-gated transport (supervisor manager, hbom profilers) is not
# exercised, so it reads as uncovered — this number is a floor, not the truth.
be-coverage-unit:
	pytest core/tests/unit api/tests/unit executor/tests core/tests/integration \
		--cov --cov-report=term-missing --cov-report=html:test-artifacts/coverage/unit

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
		--cov --cov-append --cov-report=term-missing --cov-report=html:test-artifacts/coverage/full

# Per-test coverage: same two-process split as be-coverage, but each line is
# tagged with the test that executed it (--cov-context=test). The HTML report
# is built with `coverage html --show-contexts` so each source line lists which
# tests hit it (use the filter box in the report's index.html to narrow to one
# test). --show-contexts is kept on this target only, so the plain be-coverage
# report stays uncluttered.
be-coverage-context:
	pytest core/tests api/tests/unit supervisor/tests executor/tests \
		--cov --cov-context=test --cov-report=
	pytest api/tests/integration \
		--cov --cov-append --cov-context=test --cov-report=
	coverage html --show-contexts -d test-artifacts/coverage/context
	coverage report

# ================================================
# End-to-end tests
# ================================================

# Backend API server log for plain e2e runs (without coverage). Overwritten
# on each run; use test-artifacts/coverage/e2e/backend.log for coverage runs.
E2E_API_LOG = $(CURDIR)/test-artifacts/api-server.log

define e2e_run  # $(1) = playwright --project name
	@mkdir -p test-artifacts
	@rm -f $(E2E_API_LOG)
	@set -e; \
	echo ">> starting backend on :8000 (log: $(E2E_API_LOG))"; \
	uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
		> $(E2E_API_LOG) 2>&1 & \
	api_pid=$$!; \
	trap 'kill -TERM $$api_pid 2>/dev/null || true; wait $$api_pid 2>/dev/null || true' EXIT; \
	for i in $$(seq 1 30); do \
		curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1 && break; \
		echo "  waiting for backend... ($$i/30)"; sleep 1; \
	done; \
	echo ">> backend ready — running playwright project=$(1)"; \
	( cd frontend && npm exec -- playwright test \
		-c playwright.config.ts --project=$(1) ); \
	status=$$?; \
	trap - EXIT; \
	echo ">> stopping backend"; \
	kill -TERM $$api_pid 2>/dev/null || true; \
	wait $$api_pid 2>/dev/null || true; \
	exit $$status
endef

e2e-tests:
	$(call e2e_run,e2e)

e2e-demo:
	$(call e2e_run,demo)

# Full-stack e2e coverage: browser (frontend) + server (backend) in one run.
#
# The backend is started *under* coverage (you can't measure an already-running
# server), the e2e suite runs with E2E_COVERAGE=1 so the jsCoverage fixture
# captures browser V8 coverage, then the backend gets a graceful SIGTERM so
# coverage flushes its data on shutdown. Two reports come out: backend
# (test-artifacts/coverage/e2e/) and frontend (frontend/test-artifacts/coverage/).
# Needs docker + the workbench image + browsers, like the e2e suite itself.
#
# Backend data uses its own COVERAGE_FILE so it never clobbers be-coverage's,
# but lives in the same test-artifacts/coverage/data dir.
E2E_COVERAGE_FILE = $(CURDIR)/test-artifacts/coverage/data/.coverage.e2e

e2e-coverage:
	@echo ">> starting backend under coverage on :8000"
	@rm -f $(E2E_COVERAGE_FILE) $(E2E_COVERAGE_FILE).*
	@rm -rf frontend/test-artifacts/coverage-raw
	@mkdir -p test-artifacts/coverage/e2e
	@set -e; \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage run --parallel-mode \
		-m uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
		> test-artifacts/coverage/e2e/backend.log 2>&1 & \
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
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage html -d test-artifacts/coverage/e2e; \
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

# Regenerate the pinned npm-deps hash from frontend/package-lock.json. Run
# this after any lockfile change; it uses prefetch-npm-deps (the same tool
# buildNpmPackage uses internally), so the file can't disagree with the build.
frontend-npm-hash:
	@echo "Computing npm deps hash from frontend/package-lock.json..."
	nix run nixpkgs#prefetch-npm-deps -- frontend/package-lock.json > nix/frontend-npm-deps.hash
	@echo "Wrote nix/frontend-npm-deps.hash: $$(cat nix/frontend-npm-deps.hash)"

frontend-image: frontend-npm-hash
	@echo "Staging nix sources so the flake can see them..."
	git add -N nix/frontend-image.nix nix/frontend-npm-deps.hash 2>/dev/null || true
	@echo "Building frontend image..."
	nix build .#frontend-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-frontend:latest"
