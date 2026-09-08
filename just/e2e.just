E2E_BUNDLE_DIR := ROOT + "/dist/bundles"
E2E_EXEC_BUNDLE := E2E_BUNDLE_DIR + "/exec"
E2E_TOOLS_BUNDLE := E2E_BUNDLE_DIR + "/tools"
DEFAULT_API_DEMO_CAST := ROOT + "/test-artifacts/casts/api-walkthrough.cast"
DEFAULT_E2E_GIT_ORIGIN := "https://github.com/vuducanh1112/ree-e2e-fixture.git"
DEFAULT_E2E_PYTHON_IMAGE := "docker.io/library/python:3.11-slim"

# Source-run suites are measured because the host can collect coverage from
# their backend and workbench processes. Image-backed variants deliberately are
# not: they validate the deployed topology, whose container processes are
# outside host instrumentation. The -on-stack recipes attach without owning
# lifecycle; the -stack-* recipes own startup and always tear down volumes.

# Build the executor and tools bundles injected into workbenches.
[group('E2E tests')]
e2e-bundles: _stage-nix-sources
    @mkdir -p {{ quote(E2E_BUNDLE_DIR) }}
    nix build .#exec-bundle -o {{ quote(E2E_EXEC_BUNDLE) }}
    nix build .#tools-bundle -o {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_source-stack-playwright project compute_locations mode docker_mode python_image git_origin:
    python scripts/test-stack/e2e_stack.py --project {{ quote(project) }} --mode {{ quote(mode) }} --compute-locations {{ quote(compute_locations) }} --docker-mode {{ quote(docker_mode) }} --python-image {{ quote(python_image) }} --git-origin {{ quote(git_origin) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run the measured author-side browser E2E tier.
[group('E2E tests')]
e2e-gui compute_locations=DEFAULT_E2E_COMPUTE_LOCATIONS mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: e2e-bundles (_source-stack-playwright "e2e-gui" compute_locations mode docker_mode python_image git_origin)

# Run the measured reviewer-side browser E2E tier.
[group('E2E tests')]
e2e-gui-review mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: e2e-bundles (_source-stack-playwright "e2e-gui-review" "1" mode docker_mode python_image git_origin)

# Record the measured narrated browser demo.
[group('Demos')]
demo-gui mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: e2e-bundles (_source-stack-playwright "demo-gui" "1" mode docker_mode python_image git_origin)

# Record the measured external-capsule browser demo.
[group('Demos')]
demo-gui-code-ocean mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: e2e-bundles (_source-stack-playwright "demo-gui-code-ocean" "1" mode docker_mode python_image git_origin)

# Record the measured pure-API walkthrough and render its transcript.
[group('Demos')]
demo-api mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE cast=DEFAULT_API_DEMO_CAST transcript="": e2e-bundles
    #!/usr/bin/env bash
    set -euo pipefail
    cast={{ quote(cast) }}
    transcript={{ quote(transcript) }}
    transcript=${transcript:-${cast%.cast}.md}
    mkdir -p "$(dirname "$cast")"
    python scripts/test-stack/e2e_stack.py --script {{ quote(ROOT + "/api/tests/e2e/api_walkthrough.py") }} --tier demo-api --mode {{ quote(mode) }} --compute-locations 1 --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} --record "$cast"
    python3 {{ quote(ROOT + "/api/tests/e2e/render_cast_transcript.py") }} "$cast" "$transcript"

# Start the local image-backed stack.
[group('Stack management')]
stack-up compute_locations=DEFAULT_STACK_COMPUTE_LOCATIONS:
    python scripts/test-stack/image_stack.py up --compute-locations {{ quote(compute_locations) }}

# Stop the image-backed stack while retaining volumes.
[group('Stack management')]
stack-down:
    python scripts/test-stack/image_stack.py down

# Stop the image-backed stack and remove its volumes and workbenches.
[group('Stack management')]
stack-clean:
    python scripts/test-stack/image_stack.py down --volumes

# Remove leftover workbenches; run `just workbench-clean 1` to include bundle stores.
[group('Stack management')]
workbench-clean store="":
    python scripts/test-stack/workbench_cleanup.py {{ if store != "" { "--store" } else { "" } }}

# Run any browser or API suite against an owned image-backed stack.
[group('Stack tests')]
stack-test suite compute_locations="1" images="local" repository="" tag="":
    python scripts/test-stack/run_image_suite.py --suite {{ quote(suite) }} --compute-locations {{ quote(compute_locations) }} --images {{ quote(images) }} --repository {{ quote(repository) }} --tag {{ quote(tag) }}

# Evict unreferenced bundle-store caches older than the requested days.
[group('Stack management')]
store-gc days="14":
    python scripts/test-stack/workbench_cleanup.py --store-gc {{ quote(days) }}

[private]
_check-image-stack:
    @python scripts/test-stack/image_stack.py check

# Run the author-side browser suite against an already-running image stack.
[group('Stack tests')]
e2e-gui-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(python ../scripts/test-stack/image_stack.py gui-url)" npm exec -- playwright test -c playwright.config.ts --project=e2e-gui

# Run the reviewer-side browser suite against an already-running image stack.
[group('Stack tests')]
e2e-gui-review-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(python ../scripts/test-stack/image_stack.py gui-url)" npm exec -- playwright test -c playwright.config.ts --project=e2e-gui-review

# Run the GUI demo against an already-running image stack.
[group('Stack tests')]
demo-gui-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(python ../scripts/test-stack/image_stack.py gui-url)" npm exec -- playwright test -c playwright.config.ts --project=demo-gui

# Run the API walkthrough against an already-running image stack.
[group('Stack tests')]
demo-api-on-stack: _check-image-stack
    api/tests/e2e/api_walkthrough.py --base-url "$(python scripts/test-stack/image_stack.py api-url)"

# Build local images and run the author-side browser suite against them.
[group('Stack tests')]
e2e-gui-stack-local compute_locations=DEFAULT_STACK_COMPUTE_LOCATIONS: images
    just stack-test e2e-gui {{ quote(compute_locations) }} local

# Run the author-side browser suite against published images.
[group('Stack tests')]
e2e-gui-stack-published compute_locations=DEFAULT_STACK_COMPUTE_LOCATIONS repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    just stack-test e2e-gui {{ quote(compute_locations) }} published {{ quote(repository) }} {{ quote(tag) }}

# Build local images and run the reviewer-side browser suite against them.
[group('Stack tests')]
e2e-gui-review-stack-local: images
    just stack-test e2e-gui-review 1 local

# Run the reviewer-side browser suite against published images.
[group('Stack tests')]
e2e-gui-review-stack-published repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    just stack-test e2e-gui-review 1 published {{ quote(repository) }} {{ quote(tag) }}

# Build local images and run the narrated GUI demo against them.
[group('Stack tests')]
demo-gui-stack-local: images
    just stack-test demo-gui 1 local

# Run the narrated GUI demo against published images.
[group('Stack tests')]
demo-gui-stack-published repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    just stack-test demo-gui 1 published {{ quote(repository) }} {{ quote(tag) }}

# Build local images and run the API walkthrough against them.
[group('Stack tests')]
demo-api-stack-local: images
    just stack-test demo-api 1 local

# Run the API walkthrough against published images.
[group('Stack tests')]
demo-api-stack-published repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    just stack-test demo-api 1 published {{ quote(repository) }} {{ quote(tag) }}
