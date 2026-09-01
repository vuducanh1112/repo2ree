# Repository task-runner interface. Topic imports keep the command surface in
# one place while the implementation stays close to the concern it serves.

set shell := ["bash", "-euo", "pipefail", "-c"]
set default-list

ROOT := justfile_directory()

IMAGE_TAG := env("IMAGE_TAG", "edge")
IMAGE_ARCHIVE_DIR := env("IMAGE_ARCHIVE_DIR", "dist/images")
GHCR_REGISTRY := env("GHCR_REGISTRY", "ghcr.io")
GHCR_NAMESPACE := env("GHCR_NAMESPACE", "vuducanh1112")
DOCKERHUB_REGISTRY := env("DOCKERHUB_REGISTRY", "docker.io")
DOCKERHUB_NAMESPACE := env("DOCKERHUB_NAMESPACE", "vuducanh1112")
REGISTRIES := env("REGISTRIES", GHCR_REGISTRY + "/" + GHCR_NAMESPACE + " " + DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
E2E_WORKBENCH_IMAGE := env("E2E_WORKBENCH_IMAGE", "")
E2E_WORKBENCH_DOCKER_MODE := env("E2E_WORKBENCH_DOCKER_MODE", "dind")
E2E_AGENTS := env("E2E_AGENTS", "2")

DIAGRAM_DIR := env("DIAGRAM_DIR", "dist/diagrams")
ARCH_DIR := env("ARCH_DIR", DIAGRAM_DIR + "/architecture")
DOMAIN_DIR := env("DOMAIN_DIR", DIAGRAM_DIR + "/domain")
JOURNAL_DIR := env("JOURNAL_DIR", DIAGRAM_DIR + "/journals")
METRICS_DIR := env("METRICS_DIR", "test-artifacts/metrics")

import 'just/checks.just'
import 'just/metrics.just'
import 'just/architecture.just'
import 'just/domain.just'
import 'just/journals.just'
import 'just/docs.just'
import 'just/contracts.just'
import 'just/gui-tests.just'
import 'just/be-tests.just'
import 'just/e2e.just'
import 'just/images.just'
import 'just/publish.just'

# Refuse workflows whose outputs must correspond to a committed tree.
[group('Maintenance')]
require-clean-tree:
    @test -z "$(git status --porcelain)" || { echo "working tree dirty — commit first, so published images match a commit"; exit 1; }

# Generate every architecture, domain, and run-journal diagram.
[group('Diagrams')]
diagrams: architecture-diagrams domain-diagrams journals
    @printf '>> diagrams written under %s\n' {{ quote(DIAGRAM_DIR + "/") }}
