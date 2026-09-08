# Repository task-runner interface. Topic imports keep the command surface in
# one place while the implementation stays close to the concern it serves.

set shell := ["bash", "-euo", "pipefail", "-c"]
set default-list

ROOT := justfile_directory()

IMAGE_TAG := env("IMAGE_TAG", "edge")
DEFAULT_IMAGE_ARCHIVE_DIR := "dist/images"
GHCR_REGISTRY := env("GHCR_REGISTRY", "ghcr.io")
GHCR_NAMESPACE := env("GHCR_NAMESPACE", "vuducanh1112")
DOCKERHUB_REGISTRY := env("DOCKERHUB_REGISTRY", "docker.io")
DOCKERHUB_NAMESPACE := env("DOCKERHUB_NAMESPACE", "vuducanh1112")
REGISTRIES := env("REGISTRIES", GHCR_REGISTRY + "/" + GHCR_NAMESPACE + " " + DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
DEFAULT_E2E_PROVIDER_DOCKER_MODE := "dind"
DEFAULT_E2E_COMPUTE_LOCATION_MODE := "provider"
DEFAULT_E2E_LOCATIONS := "2"
DEFAULT_STACK_LOCATIONS := "2"
DEFAULT_STACK_IMAGE_REPO := DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE
DEFAULT_STACK_IMAGE_TAG := IMAGE_TAG
DEFAULT_IMAGE_CANDIDATE_STATE_DIR := ".validation-certificates/image-candidates"
DEFAULT_PUBLISH_GATE_RECEIPT := ".validation-certificates/publish-gate-ok"

DIAGRAM_DIR := "dist/diagrams"
JUST_RECIPE_GRAPH := DIAGRAM_DIR + "/just-recipes.svg"
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
import 'just/backend-tests.just'
import 'just/e2e.just'
import 'just/images.just'
import 'just/publish.just'

# Refuse workflows whose outputs must correspond to a committed tree.
[private]
_require-clean-tree:
    @test -z "$(git status --porcelain)" || { echo "working tree dirty — commit first, so published images match a commit"; exit 1; }

# Generate every architecture, domain, run-journal, and recipe graph diagram.
[group('Diagrams')]
generate-diagrams: generate-architecture-diagrams generate-domain-diagrams generate-journals generate-just-recipe-graph
    @printf '>> diagrams written under %s\n' {{ quote(DIAGRAM_DIR + "/") }}

# Generate the declared Just recipe dependency graph.
[group('Diagrams')]
generate-just-recipe-graph:
    python scripts/diagrams/just_graph.py -o {{ quote(JUST_RECIPE_GRAPH) }}
