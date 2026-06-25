.PHONY: \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks supervisor-checks api-checks executor-checks \
	be-tests be-unit-tests be-integration-tests \
	core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests \
	be-coverage be-coverage-unit be-coverage-context \
	test-checks \
	image-archive-dir stage-nix-sources \
	workbench-image workbench-image-archive \
	frontend-image frontend-image-archive frontend-npm-hash \
	backend-image backend-image-archive \
	image-archives images load-image-archives \
	push-dockerhub-archives push-ghcr-archives \
	push-ghcr push-ghcr-local push-dockerhub push-dockerhub-local push-registries \
	e2e-tests e2e-demo e2e-demo-code-ocean e2e-coverage

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

e2e-demo-code-ocean:
	$(call e2e_run,code-ocean)

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

# Example:
#   make push-registries GHCR_NAMESPACE=github-org DOCKERHUB_NAMESPACE=dockerhub-org IMAGE_TAG=demo
#
# Image archive targets write loadable tarballs under IMAGE_ARCHIVE_DIR. That
# makes the build output portable when building inside a dev container and
# loading/pushing from the host Docker client.
IMAGE_TAG ?= edge

FRONTEND_IMAGE_NAME ?= repo2ree-frontend
BACKEND_IMAGE_NAME ?= repo2ree-backend
WORKBENCH_IMAGE_NAME ?= repo2ree-workbench

LOCAL_FRONTEND_IMAGE := $(FRONTEND_IMAGE_NAME):latest
LOCAL_BACKEND_IMAGE := $(BACKEND_IMAGE_NAME):latest
LOCAL_WORKBENCH_IMAGE := $(WORKBENCH_IMAGE_NAME):latest

IMAGE_ARCHIVE_DIR ?= dist/images
FRONTEND_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(FRONTEND_IMAGE_NAME)-latest.tar
BACKEND_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(BACKEND_IMAGE_NAME)-latest.tar
WORKBENCH_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(WORKBENCH_IMAGE_NAME)-latest.tar

GHCR_REGISTRY ?= ghcr.io
GHCR_NAMESPACE ?= vuducanh1112

DOCKERHUB_REGISTRY ?= docker.io
DOCKERHUB_NAMESPACE ?= vuducanh1112

image-archive-dir:
	@mkdir -p $(IMAGE_ARCHIVE_DIR)

# Nix only sees files git tracks, so intent-add the untracked executor sources
# before building the workbench image.
stage-nix-sources:
	@git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor 2>/dev/null || true

# ---- Normal path: build and load straight into the local Docker. ----
# These do NOT write tarballs; use the *-image-archive targets for that.

workbench-image: stage-nix-sources
	@echo "Building workbench image..."
	nix build .#workbench-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: $(LOCAL_WORKBENCH_IMAGE)"

frontend-image:
	@echo "Building frontend image..."
	nix build .#frontend-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: $(LOCAL_FRONTEND_IMAGE)"

# Backend is a Dockerfile build (uv sync at image-build time), not a nix image,
# so `docker build` already loads it into the local Docker. The tag matches what
# docker-compose expects.
backend-image:
	@echo "Building backend image..."
	docker build -f docker/demo/backend.Dockerfile -t $(LOCAL_BACKEND_IMAGE) .
	@echo "Done: $(LOCAL_BACKEND_IMAGE)"

images: frontend-image backend-image workbench-image

# Regenerate the pinned npm-deps hash from frontend/package-lock.json. Run this
# manually after any lockfile change (it is intentionally NOT a build prereq, so
# building an image never re-prefetches or rewrites this tracked file). It uses
# prefetch-npm-deps (the same tool buildNpmPackage uses), so it can't disagree
# with the build.
frontend-npm-hash:
	@echo "Computing npm deps hash from frontend/package-lock.json..."
	nix run nixpkgs#prefetch-npm-deps -- frontend/package-lock.json > nix/frontend-npm-deps.hash
	@echo "Wrote nix/frontend-npm-deps.hash: $$(cat nix/frontend-npm-deps.hash)"

# ---- Archive path (opt-in): write loadable tarballs under IMAGE_ARCHIVE_DIR. ----
# For building inside the dev container and loading/pushing from the host Docker
# client: `make image-archives`, copy dist/images to the host, then
# `make load-image-archives` + `make push-dockerhub-local` there. Kept off the
# normal images/push-* path so a plain build/push writes no tarballs.

workbench-image-archive: stage-nix-sources | image-archive-dir
	@echo "Building workbench image archive..."
	nix build .#workbench-image
	cp -fL result $(WORKBENCH_IMAGE_ARCHIVE)
	@echo "Wrote $(WORKBENCH_IMAGE_ARCHIVE)"

frontend-image-archive: | image-archive-dir
	@echo "Building frontend image archive..."
	nix build .#frontend-image
	cp -fL result $(FRONTEND_IMAGE_ARCHIVE)
	@echo "Wrote $(FRONTEND_IMAGE_ARCHIVE)"

# Backend reuses the already-built/loaded image, so there's no second build.
backend-image-archive: backend-image | image-archive-dir
	@echo "Writing $(BACKEND_IMAGE_ARCHIVE)..."
	docker save $(LOCAL_BACKEND_IMAGE) -o $(BACKEND_IMAGE_ARCHIVE)
	@echo "Wrote $(BACKEND_IMAGE_ARCHIVE)"

image-archives: frontend-image-archive backend-image-archive workbench-image-archive

load-image-archives:
	docker load -i $(FRONTEND_IMAGE_ARCHIVE)
	docker load -i $(BACKEND_IMAGE_ARCHIVE)
	docker load -i $(WORKBENCH_IMAGE_ARCHIVE)

# Host-side one-shot: load the archives built in the devcontainer, then push.
# Lets the devcontainer build credential-free (`make image-archives`) while the
# host (the only place with registry creds) loads and pushes in a single step.
push-dockerhub-archives: load-image-archives push-dockerhub-local

push-ghcr-archives: load-image-archives push-ghcr-local

push-ghcr:
	$(MAKE) images
	$(MAKE) push-ghcr-local

push-ghcr-local:
	docker tag $(LOCAL_FRONTEND_IMAGE) $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_BACKEND_IMAGE) $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_WORKBENCH_IMAGE) $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(WORKBENCH_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(WORKBENCH_IMAGE_NAME):$(IMAGE_TAG)

push-dockerhub:
	$(MAKE) images
	$(MAKE) push-dockerhub-local

push-dockerhub-local:
	docker tag $(LOCAL_FRONTEND_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_BACKEND_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_WORKBENCH_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(WORKBENCH_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(WORKBENCH_IMAGE_NAME):$(IMAGE_TAG)

push-registries:
	$(MAKE) images
	$(MAKE) push-ghcr-local
	$(MAKE) push-dockerhub-local
