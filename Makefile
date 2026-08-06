# Entry point: every configuration knob lives here; the targets live in
# topic files under mk/ and `make <target>` works the same as before the
# split.
#
#   mk/checks.mk   static checks (shell, nix, gui, python)
#   mk/metrics.mk  advisory code-metric reports
#   mk/architecture.mk  generated architecture diagrams
#   mk/docs.mk          prose linting
#   mk/contracts.mk contract generation (OpenAPI + GUI API types)
#   mk/tests.mk    unit/integration suites and coverage variants
#   mk/e2e.mk      e2e bundles, stacks, playwright runs
#   mk/images.mk   image builds and the archive path
#   mk/publish.mk  gates and the push → validate → promote publish flow

.DEFAULT_GOAL := docs-lint

# ================================================
# Configuration
# ================================================

# The tag push-image-set-tag publishes under. Candidate targets override it
# with a Git revision; `edge` is only moved from a validated digest receipt.
IMAGE_TAG ?= edge

# Every deployable image, always built/tagged/pushed as a set (the
# agent↔control-plane protocol requires matching versions).
IMAGES = repo2ree-gui repo2ree-backend repo2ree-agent

# Where image-archives writes loadable image tarballs. Makes the build output
# portable when building inside the dev container and loading/pushing from
# the host Docker client.
IMAGE_ARCHIVE_DIR ?= dist/images

# Publish destinations: every push goes to all REGISTRIES under one tag.
# Narrow with REGISTRIES="docker.io/somens" if needed. The published-stack
# e2e targets pull from the Docker Hub pair specifically.
GHCR_REGISTRY ?= ghcr.io
GHCR_NAMESPACE ?= vuducanh1112
DOCKERHUB_REGISTRY ?= docker.io
DOCKERHUB_NAMESPACE ?= vuducanh1112
REGISTRIES ?= $(GHCR_REGISTRY)/$(GHCR_NAMESPACE) $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)

# The Git revision identifying the three-image candidate being pushed,
# validated, or promoted. Name an older candidate explicitly when validation
# and registry credentials live in a checkout at a different revision.
GIT_REV = $(shell git describe --always --dirty)
IMAGE_CANDIDATE_REV ?= $(GIT_REV)

# Which bench the e2e backend's catalog offers. Empty (the default) means the
# backend's own catalog default — the pinned docker:dind digest in
# api/src/repo2ree_api/settings.py — which every browser tier runs on.
# Set it to pin the run to a specific image instead.
E2E_WORKBENCH_IMAGE ?=
E2E_WORKBENCH_DOCKER_MODE ?= dind

# ================================================
# Shared guards
# ================================================

# Images and bundles build from the working tree (stage-nix-sources even
# intent-adds untracked files), so everything published or archived must
# come from a committed state to correspond to a commit.
.PHONY: require-clean-tree
require-clean-tree:
	@[ -z "$$(git status --porcelain)" ] \
		|| { echo "working tree dirty — commit first, so published images match a commit"; exit 1; }

include mk/checks.mk
include mk/metrics.mk
include mk/architecture.mk
include mk/journals.mk
include mk/docs.mk
include mk/contracts.mk
include mk/tests.mk
include mk/e2e.mk
include mk/images.mk
include mk/publish.mk
