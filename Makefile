.PHONY: \
	docs-lint \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks supervisor-checks api-checks executor-checks agent-checks \
	be-tests be-unit-tests be-integration-tests \
	core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests agent-tests \
	be-coverage be-coverage-unit be-coverage-context \
	test-checks \
	image-archive-dir stage-nix-sources \
	agent-image agent-image-archive \
	frontend-image frontend-image-archive frontend-npm-hash \
	backend-image backend-image-archive \
	image-archives images load-image-archives \
	push-dockerhub-archives push-ghcr-archives \
	push-ghcr push-ghcr-local push-dockerhub push-dockerhub-local push-registries \
	e2e-tests e2e-demo e2e-demo-code-ocean e2e-coverage e2e-bundles

# ================================================
# Docs — prose linting
# ================================================

docs-lint:
	@echo "Linting docs with Vale..."
	vale sync
	vale docs README.md


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

agent-checks:
	@echo "Running agent checks..."
	ruff check agent/src agent/tests
	ruff format agent/src agent/tests
	mypy agent/src agent/tests

be-checks: protocol-checks core-checks supervisor-checks api-checks executor-checks agent-checks

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

agent-tests:
	pytest agent/tests

be-unit-tests: core-unit-tests api-unit-tests executor-tests agent-tests

# Integration tests — flows spanning multiple components.
core-integration-tests:
	pytest core/tests/integration

# Real-component API tier: the actual FastAPI app over HTTP against real
# workbench containers (pinned dind + injected bundles). Skips when docker or
# the bundles are absent (build with `make e2e-bundles`). Spans land
# in test-results/api-integration/traces.ndjson for post-run inspection.
api-integration-tests:
	pytest api/tests/integration

# Real workbench e2e: provisions a container from the pinned dind bench with
# the executor/tools bundles injected, over the live docker exec transport.
# Skips when docker or the bundles are absent (build with `make e2e-bundles`).
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
# without docker + the executor/tools bundles (build with `make e2e-bundles`).
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
E2E_AGENT_LOG = $(CURDIR)/test-artifacts/agent.log
E2E_AGENT_STATE_DIR = $(CURDIR)/test-artifacts/e2e-agent-state
E2E_WORKBENCH_DOCKER_MODE ?= dind

# Which bench the e2e backend's catalog offers. Empty (the default) means the
# backend's own catalog default — the pinned docker:dind digest in
# api/src/repo2ree_api/settings.py — which every browser tier runs on.
# Set it to pin the run to a specific image instead.
E2E_WORKBENCH_IMAGE ?=
define E2E_WORKBENCH_IMAGE_CATALOG
[{"id":"pinned","ref":"$(E2E_WORKBENCH_IMAGE)","label":"Pinned bench","description":"Bench image pinned for this e2e run."}]
endef
E2E_CATALOG_ENV = $(if $(E2E_WORKBENCH_IMAGE),WORKBENCH_IMAGE_CATALOG='$(E2E_WORKBENCH_IMAGE_CATALOG)')

# The e2e agent always gets the executor/tools bundles: lean env images (the
# dind default, custom benches) need the injection, and images that ship their
# own /nix (the full workbench) skip it — so this is safe for every tier.
E2E_EXEC_BUNDLE = $(CURDIR)/test-artifacts/exec-bundle
E2E_TOOLS_BUNDLE = $(CURDIR)/test-artifacts/tools-bundle

e2e-bundles: stage-nix-sources
	nix build .#exec-bundle -o $(E2E_EXEC_BUNDLE)
	nix build .#tools-bundle -o $(E2E_TOOLS_BUNDLE)

define e2e_run  # $(1) = playwright --project name
	@mkdir -p test-artifacts
	@rm -f $(E2E_API_LOG) $(E2E_AGENT_LOG)
	@set -e; \
	echo ">> starting backend on :8000 (log: $(E2E_API_LOG))"; \
	$(E2E_CATALOG_ENV) \
	uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
		> $(E2E_API_LOG) 2>&1 & \
	api_pid=$$!; \
	agent_pid=; \
	trap 'if [ -n "$$agent_pid" ]; then kill -TERM $$agent_pid 2>/dev/null || true; wait $$agent_pid 2>/dev/null || true; fi; kill -TERM $$api_pid 2>/dev/null || true; wait $$api_pid 2>/dev/null || true' EXIT; \
	api_ready=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1; then api_ready=1; break; fi; \
		echo "  waiting for backend... ($$i/30)"; sleep 1; \
	done; \
	if [ "$$api_ready" -ne 1 ]; then echo "backend did not become ready"; exit 1; fi; \
	echo ">> starting workbench agent (log: $(E2E_AGENT_LOG))"; \
	WORKBENCH_API_WS_URL=ws://127.0.0.1:8000/agent/connect \
	WORKBENCH_DOCKER_MODE=$(E2E_WORKBENCH_DOCKER_MODE) \
	WORKBENCH_AGENT_STATE_DIR=$(E2E_AGENT_STATE_DIR) \
	REPO2REE_EXEC_BUNDLE=$(E2E_EXEC_BUNDLE) \
	REPO2REE_TOOLS_BUNDLE=$(E2E_TOOLS_BUNDLE) \
	uv run --package repo2ree-agent python -m repo2ree_agent \
		> $(E2E_AGENT_LOG) 2>&1 & \
	agent_pid=$$!; \
	agent_ready=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://127.0.0.1:8000/api/v1/agents | grep -q '"agents":\[{'; then agent_ready=1; break; fi; \
		echo "  waiting for workbench agent... ($$i/30)"; sleep 1; \
	done; \
	if [ "$$agent_ready" -ne 1 ]; then echo "workbench agent did not connect"; exit 1; fi; \
	echo ">> backend ready — running playwright project=$(1)"; \
	( cd frontend && npm exec -- playwright test \
		-c playwright.config.ts --project=$(1) ); \
	status=$$?; \
	trap - EXIT; \
	echo ">> stopping workbench agent and backend"; \
	kill -TERM $$agent_pid 2>/dev/null || true; \
	wait $$agent_pid 2>/dev/null || true; \
	kill -TERM $$api_pid 2>/dev/null || true; \
	wait $$api_pid 2>/dev/null || true; \
	exit $$status
endef

e2e-tests: e2e-bundles
	$(call e2e_run,e2e)

e2e-demo: e2e-bundles
	$(call e2e_run,demo)

e2e-demo-code-ocean: e2e-bundles
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

e2e-coverage: e2e-bundles
	@echo ">> starting backend under coverage on :8000"
	@rm -f $(E2E_COVERAGE_FILE) $(E2E_COVERAGE_FILE).* test-artifacts/coverage/e2e/agent.log
	@rm -rf frontend/test-artifacts/coverage-raw
	@mkdir -p test-artifacts/coverage/e2e
	@set -e; \
	$(E2E_CATALOG_ENV) \
	COVERAGE_FILE=$(E2E_COVERAGE_FILE) coverage run --parallel-mode \
		-m uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
		> test-artifacts/coverage/e2e/backend.log 2>&1 & \
	api_pid=$$!; \
	agent_pid=; \
	trap 'if [ -n "$$agent_pid" ]; then kill -TERM $$agent_pid 2>/dev/null || true; wait $$agent_pid 2>/dev/null || true; fi; kill -TERM $$api_pid 2>/dev/null || true' EXIT; \
	api_ready=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1; then api_ready=1; break; fi; sleep 1; \
	done; \
	if [ "$$api_ready" -ne 1 ]; then echo "backend did not become ready"; exit 1; fi; \
	echo ">> starting workbench agent"; \
	WORKBENCH_API_WS_URL=ws://127.0.0.1:8000/agent/connect \
	WORKBENCH_DOCKER_MODE=$(E2E_WORKBENCH_DOCKER_MODE) \
	WORKBENCH_AGENT_STATE_DIR=$(E2E_AGENT_STATE_DIR) \
	REPO2REE_EXEC_BUNDLE=$(E2E_EXEC_BUNDLE) \
	REPO2REE_TOOLS_BUNDLE=$(E2E_TOOLS_BUNDLE) \
	uv run --package repo2ree-agent python -m repo2ree_agent \
		> test-artifacts/coverage/e2e/agent.log 2>&1 & \
	agent_pid=$$!; \
	agent_ready=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://127.0.0.1:8000/api/v1/agents | grep -q '"agents":\[{'; then agent_ready=1; break; fi; sleep 1; \
	done; \
	if [ "$$agent_ready" -ne 1 ]; then echo "workbench agent did not connect"; exit 1; fi; \
	status=0; \
	( cd frontend && E2E_COVERAGE=1 npm exec -- playwright test \
		-c playwright.config.ts --project=e2e ) || status=$$?; \
	echo ">> stopping workbench agent and backend (SIGTERM) so coverage flushes"; \
	kill -TERM $$agent_pid 2>/dev/null || true; \
	wait $$agent_pid 2>/dev/null || true; \
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
AGENT_IMAGE_NAME ?= repo2ree-agent

LOCAL_FRONTEND_IMAGE := $(FRONTEND_IMAGE_NAME):latest
LOCAL_BACKEND_IMAGE := $(BACKEND_IMAGE_NAME):latest
LOCAL_AGENT_IMAGE := $(AGENT_IMAGE_NAME):latest

IMAGE_ARCHIVE_DIR ?= dist/images
FRONTEND_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(FRONTEND_IMAGE_NAME)-latest.tar
BACKEND_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(BACKEND_IMAGE_NAME)-latest.tar
AGENT_IMAGE_ARCHIVE := $(IMAGE_ARCHIVE_DIR)/$(AGENT_IMAGE_NAME)-latest.tar

GHCR_REGISTRY ?= ghcr.io
GHCR_NAMESPACE ?= vuducanh1112

DOCKERHUB_REGISTRY ?= docker.io
DOCKERHUB_NAMESPACE ?= vuducanh1112

image-archive-dir:
	@mkdir -p $(IMAGE_ARCHIVE_DIR)

# Nix only sees files git tracks, so intent-add the untracked python sources
# before any nix image/bundle build that packages them.
stage-nix-sources:
	@git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor agent/src 2>/dev/null || true

# ---- Normal path: build and load straight into the local Docker. ----
# These do NOT write tarballs; use the *-image-archive targets for that.

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

# The agent image is the self-carrying deployable third parties run: agent
# process + embedded executor/tools bundles (see nix/agent-image.nix).
agent-image: stage-nix-sources
	@echo "Building agent image..."
	nix build .#agent-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: $(LOCAL_AGENT_IMAGE)"

images: frontend-image backend-image agent-image

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

agent-image-archive: stage-nix-sources | image-archive-dir
	@echo "Building agent image archive..."
	nix build .#agent-image
	cp -fL result $(AGENT_IMAGE_ARCHIVE)
	@echo "Wrote $(AGENT_IMAGE_ARCHIVE)"

image-archives: frontend-image-archive backend-image-archive agent-image-archive

load-image-archives:
	docker load -i $(FRONTEND_IMAGE_ARCHIVE)
	docker load -i $(BACKEND_IMAGE_ARCHIVE)
	docker load -i $(AGENT_IMAGE_ARCHIVE)

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
	docker tag $(LOCAL_AGENT_IMAGE) $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(AGENT_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(AGENT_IMAGE_NAME):$(IMAGE_TAG)

push-dockerhub:
	$(MAKE) images
	$(MAKE) push-dockerhub-local

push-dockerhub-local:
	docker tag $(LOCAL_FRONTEND_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_BACKEND_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(LOCAL_AGENT_IMAGE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(AGENT_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(FRONTEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(BACKEND_IMAGE_NAME):$(IMAGE_TAG)
	docker push $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)/$(AGENT_IMAGE_NAME):$(IMAGE_TAG)

push-registries:
	$(MAKE) images
	$(MAKE) push-ghcr-local
	$(MAKE) push-dockerhub-local
