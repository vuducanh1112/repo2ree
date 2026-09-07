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
DEFAULT_E2E_PROVIDER_DOCKER_MODE := "dind"
DEFAULT_E2E_CAPACITY_MODE := "provider"
DEFAULT_E2E_CAPACITY := "2"
DEFAULT_STACK_PROVIDERS := "2"
DEFAULT_STACK_IMAGE_REPO := DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE
DEFAULT_STACK_IMAGE_TAG := IMAGE_TAG

DIAGRAM_DIR := "dist/diagrams"
ARCH_DIR := DIAGRAM_DIR + "/architecture"
DOMAIN_DIR := DIAGRAM_DIR + "/domain"
JOURNAL_DIR := DIAGRAM_DIR + "/journals"
METRICS_DIR := "test-artifacts/metrics"

import 'just/checks.just'
import 'just/config.just'
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
[private]
_require-clean-tree:
    @test -z "$(git status --porcelain)" || { echo "working tree dirty — commit first, so published images match a commit"; exit 1; }

# Generate every architecture, domain, and run-journal diagram.
[group('Diagrams')]
diagrams: architecture-diagrams domain-diagrams journals
    @printf '>> diagrams written under %s\n' {{ quote(DIAGRAM_DIR + "/") }}
