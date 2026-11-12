# Repository task-runner interface. Topic imports keep the command surface in
# one place while the implementation stays close to the concern it serves.

set shell := ["bash", "-euo", "pipefail", "-c"]
set default-list

ROOT := justfile_directory()

# One identity is inherited by every process in an aggregate invocation.
export REPO2REE_TEST_RUN_DIR := env("REPO2REE_TEST_RUN_DIR", ROOT + "/test-artifacts")
export REPO2REE_TEST_RUN_ID := env("REPO2REE_TEST_RUN_ID", `python -c 'import uuid; print(uuid.uuid4().hex)'`)


IMAGE_TAG := env("IMAGE_TAG", "edge")
DEFAULT_IMAGE_ARCHIVE_DIR := "dist/images"
GHCR_REGISTRY := env("GHCR_REGISTRY", "ghcr.io")
GHCR_NAMESPACE := env("GHCR_NAMESPACE", "vuducanh1112")
DOCKERHUB_REGISTRY := env("DOCKERHUB_REGISTRY", "docker.io")
DOCKERHUB_NAMESPACE := env("DOCKERHUB_NAMESPACE", "vuducanh1112")
REGISTRIES := env("REGISTRIES", GHCR_REGISTRY + "/" + GHCR_NAMESPACE + " " + DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
DEFAULT_STACK_LOCATIONS := "2"
DEFAULT_STACK_IMAGE_REPO := DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE
DEFAULT_STACK_IMAGE_TAG := IMAGE_TAG
DEFAULT_IMAGE_CANDIDATE_STATE_DIR := ".receipts/image-candidates"
# Every platform a published image set carries; each is built and gated on a machine of its own.
PUBLISH_PLATFORMS := env("PUBLISH_PLATFORMS", "linux/amd64 linux/arm64")

export REPO2REE_ASSURANCE_DIR := env("REPO2REE_ASSURANCE_DIR", REPO2REE_TEST_RUN_DIR + "/assurance")
# Views of the repository, as opposed to what ships (dist/) and what tests leave (test-artifacts/).
REPORTS_DIR := "reports"
DIAGRAM_DIR := REPORTS_DIR + "/diagrams"
JUST_RECIPE_GRAPH := DIAGRAM_DIR + "/just-recipes.svg"
REE_ANATOMY := DIAGRAM_DIR + "/ree/anatomy.svg"
# Records the commit each generated diagram or metric came from (repo2ree_repoview stamp).
STAMP_DIAGRAMS := "python -m repo2ree_repoview stamp --manifest " + DIAGRAM_DIR + "/manifest.json"
ARCH_DIR := DIAGRAM_DIR + "/architecture"
METRICS_DIR := REPORTS_DIR + "/metrics"
# The owners' exports the overview reads (zones, behaviour spec, operations), stamped like the diagrams.
EXPORT_DIR := REPORTS_DIR + "/exports"
STAMP_EXPORTS := "python -m repo2ree_repoview stamp --manifest " + EXPORT_DIR + "/manifest.json"

import 'just/checks.just'
import 'just/config.just'
import 'just/metrics.just'
import 'just/architecture.just'
import 'just/domain.just'
import 'just/docs.just'
import 'just/presentations.just'
import 'just/contracts.just'
import 'just/gui-tests.just'
import 'just/backend-tests.just'
import 'just/assurance.just'
import 'just/e2e.just'
import 'just/images.just'
import 'just/gates.just'
import 'just/publish.just'

# Refuse workflows whose outputs must correspond to a committed tree.
[private]
_require-clean-tree:
    @test -z "$(git status --porcelain)" || { echo "working tree dirty — commit first, so published images match a commit"; exit 1; }

# Generate every architecture, domain, specification, REE anatomy, and recipe graph diagram.
[group('Diagrams')]
generate-diagrams: generate-architecture-diagrams generate-spec-diagrams generate-just-recipe-graph generate-ree-anatomy
    @printf '>> diagrams written under %s\n' {{ quote(DIAGRAM_DIR + "/") }}

# Run every generated tree's own prune and list what no one owns (scripts/generated.toml); `--dry-run`, `--remove-unclaimed`.
[group('Housekeeping')]
prune *args:
    python scripts/prune.py {{ args }}

# Build the repository overview in reports/overview/<revision>/ (reports/overview/latest): zones, gates, behaviour and its coverage by the gate and the showcases, architecture, recipes, configuration, API.
[group('Repository')]
repo-overview: generate-diagrams export-zones export-spec visualize-behaviour visualize-showcases export-operations export-just-recipes
    python -m repo2ree_repoview overview

# Write the zones and each tracked file's place as JSON (repo2ree-zones/1) for the overview.
[group('Repository')]
export-zones:
    mkdir -p {{ quote(EXPORT_DIR) }}
    python scripts/zones.py export > {{ quote(EXPORT_DIR + "/zones.json") }}
    {{ STAMP_EXPORTS }} --by export-zones {{ quote(EXPORT_DIR + "/zones.json") }}

# Write Just's JSON dump of every recipe for the recipe graph and the overview.
[group('Repository')]
export-just-recipes:
    mkdir -p {{ quote(EXPORT_DIR) }}
    {{ just_executable() }} --justfile {{ quote(justfile()) }} --dump --dump-format json > {{ quote(EXPORT_DIR + "/just-recipes.json") }}
    {{ STAMP_EXPORTS }} --by export-just-recipes {{ quote(EXPORT_DIR + "/just-recipes.json") }}

# Generate the declared Just recipe dependency graph.
[group('Diagrams')]
generate-just-recipe-graph: export-just-recipes
    python -m repo2ree_repoview recipes --dump {{ quote(EXPORT_DIR + "/just-recipes.json") }} -o {{ quote(JUST_RECIPE_GRAPH) }}
    {{ STAMP_DIAGRAMS }} --by generate-just-recipe-graph {{ quote(JUST_RECIPE_GRAPH) }}

# Draw the REE contract's anatomy from contracts/ree/ree.schema.json: every part, and which declared field each receipt repeats.
[group('Diagrams')]
generate-ree-anatomy:
    python -m repo2ree_repoview ree-anatomy -o {{ quote(REE_ANATOMY) }}
    {{ STAMP_DIAGRAMS }} --by generate-ree-anatomy {{ quote(REE_ANATOMY) }}
