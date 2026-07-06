.PHONY: \
	docs-lint scripts-checks \
	fe-checks fe-tests \
	be-checks \
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
	push-archives push-tag push-rev validate-rev promote-edge \
	e2e-tests e2e-tests-images e2e-tests-stack e2e-tests-stack-published \
	e2e-demo e2e-demo-images e2e-demo-stack e2e-demo-stack-published \
	e2e-demo-code-ocean e2e-coverage e2e-bundles \
	stack-up stack-down commit-gate push-gate

# ================================================
# Docs — prose linting
# ================================================

docs-lint:
	@echo "Linting docs with Vale..."
	vale sync
	vale docs README.md

# ================================================
# Scripts — shell linting
# ================================================

scripts-checks:
	@echo "Running shellcheck..."
	shellcheck scripts/*.sh


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

# Python workspace packages. <pkg>-checks runs ruff + mypy over the package's
# src (and tests, where the package has them — protocol doesn't).
PY_PACKAGES = protocol core supervisor api executor agent

.PHONY: $(addsuffix -checks,$(PY_PACKAGES))
$(addsuffix -checks,$(PY_PACKAGES)): %-checks:
	@echo "Running $* checks..."
	ruff check $(wildcard $*/src $*/tests)
	ruff format $(wildcard $*/src $*/tests)
	mypy $(wildcard $*/src $*/tests)

be-checks: $(addsuffix -checks,$(PY_PACKAGES))

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

# Stack orchestration (backend + agent + playwright, readiness polling,
# teardown, the coverage variant) lives in scripts/e2e-stack.sh.

# Which bench the e2e backend's catalog offers. Empty (the default) means the
# backend's own catalog default — the pinned docker:dind digest in
# api/src/repo2ree_api/settings.py — which every browser tier runs on.
# Set it to pin the run to a specific image instead.
E2E_WORKBENCH_IMAGE ?=
E2E_WORKBENCH_DOCKER_MODE ?= dind

# The e2e agent always gets the executor/tools bundles: lean env images (the
# dind default, custom benches) need the injection, and images that ship their
# own /nix (the full workbench) skip it — so this is safe for every tier.
E2E_EXEC_BUNDLE = $(CURDIR)/test-artifacts/exec-bundle
E2E_TOOLS_BUNDLE = $(CURDIR)/test-artifacts/tools-bundle

e2e-bundles: stage-nix-sources
	nix build .#exec-bundle -o $(E2E_EXEC_BUNDLE)
	nix build .#tools-bundle -o $(E2E_TOOLS_BUNDLE)

E2E_STACK = E2E_WORKBENCH_IMAGE='$(E2E_WORKBENCH_IMAGE)' \
	E2E_WORKBENCH_DOCKER_MODE=$(E2E_WORKBENCH_DOCKER_MODE) \
	E2E_EXEC_BUNDLE=$(E2E_EXEC_BUNDLE) \
	E2E_TOOLS_BUNDLE=$(E2E_TOOLS_BUNDLE) \
	scripts/e2e-stack.sh

e2e-tests: e2e-bundles
	$(E2E_STACK) --project e2e

e2e-demo: e2e-bundles
	$(E2E_STACK) --project demo

# Image-backed demo stack: the compose control plane on :local tags plus the
# agent container compose deliberately doesn't manage. Expects `make images`
# to have run; lifecycle lives in scripts/image-stack.sh.
stack-up:
	scripts/image-stack.sh up

stack-down:
	scripts/image-stack.sh down

# Run a playwright project against the already-running image-backed stack:
# the Caddy-served frontend (its /api reverse proxy included) instead of a
# vite dev server, and whatever backend + agent images are behind it.
# Nothing is started or stopped here — `make stack-up` first (or start
# compose + agent by hand, see README).
define playwright_against_stack  # $(1) = playwright --project name
	@scripts/image-stack.sh check
	cd frontend && E2E_BASE_URL=$$(../scripts/image-stack.sh frontend-url) \
		npm exec -- playwright test -c playwright.config.ts --project=$(1)
endef

e2e-tests-images:
	$(call playwright_against_stack,e2e)

e2e-demo-images:
	$(call playwright_against_stack,demo)

# One-command flows: build the :local images (or pull the pushed ones),
# stack-up, run against the stack, and tear it down again (also on failure).
define run_then_stack_down  # $(1) = target to run against the running stack
	@status=0; $(MAKE) $(1) || status=$$?; \
	$(MAKE) stack-down; exit $$status
endef

# The pushed images default to the Docker Hub set at IMAGE_TAG; use
# IMAGE_TAG=<rev> to validate a freshly pushed rev before promoting it.
PUBLISHED_STACK = STACK_IMAGE_REPO=$(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE) \
	STACK_IMAGE_TAG=$(IMAGE_TAG)

e2e-tests-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-tests-images)

# The commit gate: fast and container-free by design — static checks plus
# every test tier that runs without docker/nix/browsers, so it's cheap enough
# to run before each commit. The heavyweight counterpart is push-gate.
commit-gate:
	$(MAKE) scripts-checks fe-checks be-checks
	$(MAKE) fe-tests be-unit-tests core-integration-tests

# The push gate: everything that must be green before publishing images, in
# one command. Refuses a dirty tree first — images build from the working
# tree (stage-nix-sources even intent-adds untracked files), so only a
# committed state gives the pushed images a commit they correspond to.
# Slow by design: it runs the e2e suite twice, source-run and image-backed.
# When it passes, the :local images it just built are exactly what push-rev
# will publish.
push-gate:
	@[ -z "$$(git status --porcelain)" ] \
		|| { echo "working tree dirty — commit first, so pushed images match a commit"; exit 1; }
	$(MAKE) scripts-checks fe-checks be-checks
	$(MAKE) e2e-bundles
	$(MAKE) fe-tests be-tests
	$(MAKE) e2e-tests
	$(MAKE) e2e-tests-stack
	@echo ">> push gate green — publish with: make push-rev"

e2e-tests-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-tests-images)

e2e-demo-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)

e2e-demo-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)

e2e-demo-code-ocean: e2e-bundles
	$(E2E_STACK) --project code-ocean

# Full-stack e2e coverage: browser (frontend) + server (backend) in one run.
# Reports land in test-artifacts/coverage/e2e/ (backend) and
# frontend/test-artifacts/coverage/ (browser V8). Needs docker + the workbench
# image + browsers, like the e2e suite itself.
e2e-coverage: e2e-bundles
	$(E2E_STACK) --project e2e --coverage

# ================================================
# Build
# ================================================

# Image archive targets write loadable tarballs under IMAGE_ARCHIVE_DIR. That
# makes the build output portable when building inside a dev container and
# loading/pushing from the host Docker client.
IMAGE_TAG ?= edge

# Every deployable image, always built/tagged/pushed as a set (the
# agent↔control-plane protocol requires matching versions).
IMAGES = repo2ree-frontend repo2ree-backend repo2ree-agent

IMAGE_ARCHIVE_DIR ?= dist/images

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
	@echo "Done: repo2ree-frontend:local"

# Backend is a Dockerfile build (uv sync at image-build time), not a nix image,
# so `docker build` already loads it into the local Docker. The :local tag marks
# never-pushed workbench builds (the compose local-override path uses it);
# published channels are minted at push time.
backend-image:
	@echo "Building backend image..."
	docker build -f docker/demo/backend.Dockerfile -t repo2ree-backend:local .
	@echo "Done: repo2ree-backend:local"

# The agent image is the self-carrying deployable third parties run: agent
# process + embedded executor/tools bundles (see nix/agent-image.nix).
agent-image: stage-nix-sources
	@echo "Building agent image..."
	nix build .#agent-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-agent:local"

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
# `make push-archives` there. Kept off the normal images/push-* path so a
# plain build/push writes no tarballs.

frontend-image-archive: | image-archive-dir
	@echo "Building frontend image archive..."
	nix build .#frontend-image
	cp -fL result $(IMAGE_ARCHIVE_DIR)/repo2ree-frontend-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-frontend-local.tar"

# Backend reuses the already-built/loaded image, so there's no second build.
backend-image-archive: backend-image | image-archive-dir
	docker save repo2ree-backend:local -o $(IMAGE_ARCHIVE_DIR)/repo2ree-backend-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-backend-local.tar"

agent-image-archive: stage-nix-sources | image-archive-dir
	@echo "Building agent image archive..."
	nix build .#agent-image
	cp -fL result $(IMAGE_ARCHIVE_DIR)/repo2ree-agent-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-agent-local.tar"

image-archives: frontend-image-archive backend-image-archive agent-image-archive

load-image-archives:
	@set -e; for img in $(IMAGES); do \
		docker load -i $(IMAGE_ARCHIVE_DIR)/$$img-local.tar; \
	done

# Host-side one-shot: load the archives built in the devcontainer, then push.
# Lets the devcontainer build credential-free (`make image-archives`) while the
# host (the only place with registry creds) loads and pushes in a single step.
push-archives: load-image-archives push-tag

# ---- Publish: push → validate → promote ----
# Every push goes to all REGISTRIES under one tag; `edge` is only ever moved
# by promoting a rev that was pushed and validated first:
#   make push-rev       # immutable :<rev>, clean tree only
#   make validate-rev   # full e2e suite against the pushed set
#   make promote-edge   # registry-side retag <rev> -> edge

REGISTRIES ?= $(GHCR_REGISTRY)/$(GHCR_NAMESPACE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)
GIT_REV = $(shell git describe --always --dirty)

# Plumbing: tag + push the already-built :local images to every registry
# under IMAGE_TAG. Narrow with REGISTRIES="docker.io/somens" if needed.
push-tag:
	@set -e; for reg in $(REGISTRIES); do for img in $(IMAGES); do \
		docker tag $$img:local $$reg/$$img:$(IMAGE_TAG); \
		docker push $$reg/$$img:$(IMAGE_TAG); \
	done; done

# Immutable publish: build from a committed tree, push under the git rev.
# Never moves `edge`, so it is safe to run at any time.
push-rev:
	@case "$(GIT_REV)" in (*-dirty) echo "working tree dirty — commit first," \
		"so the pushed images match a commit"; exit 1;; esac
	$(MAKE) images
	$(MAKE) push-tag IMAGE_TAG=$(GIT_REV)
	@echo ">> pushed :$(GIT_REV) — next: make validate-rev && make promote-edge"

# Validate the pushed rev with the full e2e suite before promoting it.
# Like promote-edge, REV defaults to the current HEAD's rev — so the whole
# publish flow runs tag-free from the commit being published.
validate-rev:
	@case "$(REV)" in (*-dirty) echo "tree is dirty — name the pushed rev" \
		"explicitly: make validate-rev REV=<rev>"; exit 1;; esac
	$(MAKE) e2e-tests-stack-published IMAGE_TAG=$(REV)

# Promote a validated rev to edge by retagging on the registry — no rebuild,
# no local images involved, so the promoted digests are exactly the validated
# ones. REV defaults to the current HEAD's rev.
REV ?= $(GIT_REV)

promote-edge:
	@case "$(REV)" in (*-dirty) echo "tree is dirty — name the pushed rev" \
		"explicitly: make promote-edge REV=<rev>"; exit 1;; esac
	@set -e; for reg in $(REGISTRIES); do for img in $(IMAGES); do \
		echo ">> $$reg/$$img: $(REV) -> edge"; \
		docker buildx imagetools create -t $$reg/$$img:edge $$reg/$$img:$(REV); \
	done; done
