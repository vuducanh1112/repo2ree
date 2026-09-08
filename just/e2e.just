E2E_BUNDLE_DIR := ROOT + "/dist/bundles"
E2E_EXEC_BUNDLE := E2E_BUNDLE_DIR + "/exec"
E2E_TOOLS_BUNDLE := E2E_BUNDLE_DIR + "/tools"
DEFAULT_API_DEMO_CAST := ROOT + "/test-artifacts/casts/api-walkthrough.cast"
DEFAULT_E2E_GIT_ORIGIN := "https://github.com/vuducanh1112/ree-e2e-fixture.git"
DEFAULT_E2E_PYTHON_IMAGE := "docker.io/library/python:3.11-slim"

# Source-run suites are measured because the host can collect coverage from
# their backend and workbench processes. Image-backed variants deliberately are
# not: they validate the deployed topology, whose container processes are
# outside host instrumentation. Existing-stack runs attach without owning the
# lifecycle; local and published runs own startup and always tear down volumes.

# Build the executor and tools bundles injected into workbenches.
[group('E2E tests')]
build-e2e-bundles: _stage-nix-sources
    @mkdir -p {{ quote(E2E_BUNDLE_DIR) }}
    nix build .#exec-bundle -o {{ quote(E2E_EXEC_BUNDLE) }}
    nix build .#tools-bundle -o {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_source-stack-playwright project locations mode docker_mode python_image git_origin:
    python scripts/test-stack/e2e_stack.py --project {{ quote(project) }} --mode {{ quote(mode) }} --compute-locations {{ quote(locations) }} --docker-mode {{ quote(docker_mode) }} --python-image {{ quote(python_image) }} --git-origin {{ quote(git_origin) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run the measured author-side browser E2E tier.
[group('E2E tests')]
test-e2e-gui locations=DEFAULT_E2E_LOCATIONS mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: build-e2e-bundles (_source-stack-playwright "e2e-gui" locations mode docker_mode python_image git_origin)

# Run the measured reviewer-side browser E2E tier.
[group('E2E tests')]
test-e2e-review mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: build-e2e-bundles (_source-stack-playwright "e2e-gui-review" "1" mode docker_mode python_image git_origin)

# Record the measured narrated browser demo.
[group('Demos')]
demo-gui mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: build-e2e-bundles (_source-stack-playwright "demo-gui" "1" mode docker_mode python_image git_origin)

# Record the measured external-capsule browser demo.
[group('Demos')]
demo-gui-code-ocean mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE python_image=DEFAULT_E2E_PYTHON_IMAGE git_origin=DEFAULT_E2E_GIT_ORIGIN: build-e2e-bundles (_source-stack-playwright "demo-gui-code-ocean" "1" mode docker_mode python_image git_origin)

# Record the measured pure-API walkthrough and render its transcript.
[group('Demos')]
demo-api mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE cast=DEFAULT_API_DEMO_CAST transcript="": build-e2e-bundles
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
stack-up locations=DEFAULT_STACK_LOCATIONS:
    python scripts/test-stack/image_stack.py up --compute-locations {{ quote(locations) }}

# Stop the image-backed stack while retaining volumes.
[group('Stack management')]
stack-down:
    python scripts/test-stack/image_stack.py down

# Stop the image-backed stack and remove its volumes and workbenches.
[group('Stack management')]
stack-clean:
    python scripts/test-stack/image_stack.py down --volumes

# Remove leftover workbenches; run `just clean-workbenches 1` to include bundle stores.
[group('Stack management')]
clean-workbenches store="":
    python scripts/test-stack/workbench_cleanup.py {{ if store != "" { "--store" } else { "" } }}

# Build local images and run any browser or API suite against an owned stack.
[group('Stack tests')]
test-stack-local suite locations="1": build-images
    python scripts/test-stack/run_image_suite.py --suite {{ quote(suite) }} --compute-locations {{ quote(locations) }} --images local

# Run any browser or API suite against published images in an owned stack.
[group('Stack tests')]
test-stack-published suite locations="1" repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    python scripts/test-stack/run_image_suite.py --suite {{ quote(suite) }} --compute-locations {{ quote(locations) }} --images published --repository {{ quote(repository) }} --tag {{ quote(tag) }}

# Run any browser or API suite against the already-running image stack.
[group('Stack tests')]
test-stack-existing suite:
    python scripts/test-stack/run_image_suite.py --suite {{ quote(suite) }} --compute-locations 1 --images local --existing

# Evict unreferenced bundle-store caches older than the requested days.
[group('Stack management')]
gc-bundle-store days="14":
    python scripts/test-stack/workbench_cleanup.py --store-gc {{ quote(days) }}
