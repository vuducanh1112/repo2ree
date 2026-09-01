E2E_BUNDLE_DIR := ROOT + "/dist/bundles"
E2E_EXEC_BUNDLE := E2E_BUNDLE_DIR + "/exec"
E2E_TOOLS_BUNDLE := E2E_BUNDLE_DIR + "/tools"
API_DEMO_CAST := env("API_DEMO_CAST", ROOT + "/test-artifacts/casts/api-agent-walkthrough.cast")
API_DEMO_TRANSCRIPT := env("API_DEMO_TRANSCRIPT", replace_regex(API_DEMO_CAST, "[.]cast$", ".md"))

# Source-run suites are measured because the host can collect coverage from
# their backend and agent processes. Image-backed variants deliberately are
# not: they validate the deployed topology, whose container processes are
# outside host instrumentation. The -on-stack recipes attach without owning
# lifecycle; the -stack-* recipes own startup and always tear down volumes.

# Build the executor and tools bundles injected into workbenches.
[group('E2E tests')]
e2e-bundles: stage-nix-sources
    @mkdir -p {{ quote(E2E_BUNDLE_DIR) }}
    nix build .#exec-bundle -o {{ quote(E2E_EXEC_BUNDLE) }}
    nix build .#tools-bundle -o {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_source-stack-playwright PROJECT AGENTS:
    E2E_WORKBENCH_IMAGE={{ quote(E2E_WORKBENCH_IMAGE) }} E2E_WORKBENCH_DOCKER_MODE={{ quote(E2E_WORKBENCH_DOCKER_MODE) }} E2E_EXEC_BUNDLE={{ quote(E2E_EXEC_BUNDLE) }} E2E_TOOLS_BUNDLE={{ quote(E2E_TOOLS_BUNDLE) }} scripts/test-stack/e2e-stack.sh --project {{ quote(PROJECT) }} --agents {{ quote(AGENTS) }}

# Run the measured author-side browser E2E tier.
[group('E2E tests')]
e2e-gui E2E_AGENTS=E2E_AGENTS: e2e-bundles (_source-stack-playwright "e2e-gui" E2E_AGENTS)

# Run the measured reviewer-side browser E2E tier.
[group('E2E tests')]
e2e-gui-review: e2e-bundles (_source-stack-playwright "e2e-gui-review" "1")

# Record the measured narrated browser demo.
[group('Demos')]
demo-gui: e2e-bundles (_source-stack-playwright "demo-gui" "1")

# Record the measured external-capsule browser demo.
[group('Demos')]
demo-gui-code-ocean: e2e-bundles (_source-stack-playwright "demo-gui-code-ocean" "1")

# Record the measured pure-API walkthrough and render its transcript.
[group('Demos')]
demo-api API_DEMO_CAST=API_DEMO_CAST API_DEMO_TRANSCRIPT=API_DEMO_TRANSCRIPT: e2e-bundles
    @mkdir -p "$(dirname {{ quote(API_DEMO_CAST) }})"
    E2E_WORKBENCH_IMAGE={{ quote(E2E_WORKBENCH_IMAGE) }} E2E_WORKBENCH_DOCKER_MODE={{ quote(E2E_WORKBENCH_DOCKER_MODE) }} E2E_EXEC_BUNDLE={{ quote(E2E_EXEC_BUNDLE) }} E2E_TOOLS_BUNDLE={{ quote(E2E_TOOLS_BUNDLE) }} scripts/test-stack/e2e-stack.sh --script {{ quote(ROOT + "/api/tests/e2e/api_agent_walkthrough.py") }} --tier demo-api --record {{ quote(API_DEMO_CAST) }}
    python3 {{ quote(ROOT + "/api/tests/e2e/render_cast_transcript.py") }} {{ quote(API_DEMO_CAST) }} {{ quote(API_DEMO_TRANSCRIPT) }}

# Start the local image-backed stack.
[group('Stack management')]
stack-up E2E_AGENTS=E2E_AGENTS:
    STACK_AGENTS={{ quote(E2E_AGENTS) }} scripts/test-stack/image-stack.sh up

# Stop the image-backed stack while retaining volumes.
[group('Stack management')]
stack-down:
    scripts/test-stack/image-stack.sh down

# Stop the image-backed stack and remove its volumes and workbenches.
[group('Stack management')]
stack-clean:
    scripts/test-stack/image-stack.sh down --volumes

# Remove leftover workbenches; pass STORE=1 to include bundle stores.
[group('Stack management')]
workbench-clean STORE=env("STORE", ""):
    scripts/test-stack/workbench-cleanup.sh {{ if STORE != "" { "--store" } else { "" } }}

# Evict unreferenced bundle-store caches older than the requested days.
[group('Stack management')]
store-gc STORE_GC_DAYS=env("STORE_GC_DAYS", "14"):
    scripts/test-stack/workbench-cleanup.sh --store-gc {{ quote(STORE_GC_DAYS) }}

[private]
_check-image-stack:
    @scripts/test-stack/image-stack.sh check

# Run the author-side browser suite against an already-running image stack.
[group('Stack tests')]
e2e-gui-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(../scripts/test-stack/image-stack.sh gui-url)" npm exec -- playwright test -c playwright.config.ts --project=e2e-gui

# Run the reviewer-side browser suite against an already-running image stack.
[group('Stack tests')]
e2e-gui-review-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(../scripts/test-stack/image-stack.sh gui-url)" npm exec -- playwright test -c playwright.config.ts --project=e2e-gui-review

# Run the GUI demo against an already-running image stack.
[group('Stack tests')]
demo-gui-on-stack: _check-image-stack
    cd gui && E2E_BASE_URL="$(../scripts/test-stack/image-stack.sh gui-url)" npm exec -- playwright test -c playwright.config.ts --project=demo-gui

# Run the API walkthrough against an already-running image stack.
[group('Stack tests')]
demo-api-on-stack: _check-image-stack
    API_BASE_URL="$(scripts/test-stack/image-stack.sh api-url)" api/tests/e2e/api_agent_walkthrough.py

[private]
_stack-suite SUITE E2E_AGENTS STACK_IMAGE_REPO="" STACK_IMAGE_TAG="":
    #!/usr/bin/env bash
    set -euo pipefail
    cleanup() { {{ quote(ROOT + "/scripts/test-stack/image-stack.sh") }} down --volumes; }
    trap cleanup EXIT
    if [[ -n {{ quote(STACK_IMAGE_REPO) }} ]]; then
      STACK_IMAGE_REPO={{ quote(STACK_IMAGE_REPO) }} STACK_IMAGE_TAG={{ quote(STACK_IMAGE_TAG) }} STACK_AGENTS={{ quote(E2E_AGENTS) }} scripts/test-stack/image-stack.sh up
    else
      STACK_AGENTS={{ quote(E2E_AGENTS) }} scripts/test-stack/image-stack.sh up
    fi
    scripts/test-stack/image-stack.sh check
    if [[ {{ quote(SUITE) }} == demo-api ]]; then
      API_BASE_URL="$(scripts/test-stack/image-stack.sh api-url)" api/tests/e2e/api_agent_walkthrough.py
    else
      cd gui
      E2E_BASE_URL="$(../scripts/test-stack/image-stack.sh gui-url)" npm exec -- playwright test -c playwright.config.ts --project={{ quote(SUITE) }}
    fi
    cd {{ quote(ROOT) }}
    cleanup
    trap - EXIT

# Build local images and run the author-side browser suite against them.
[group('Stack tests')]
e2e-gui-stack-local E2E_AGENTS=E2E_AGENTS: images (_stack-suite "e2e-gui" E2E_AGENTS)

# Run the author-side browser suite against published images.
[group('Stack tests')]
e2e-gui-stack-published E2E_AGENTS=E2E_AGENTS STACK_IMAGE_REPO=(DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE) STACK_IMAGE_TAG=IMAGE_TAG: (_stack-suite "e2e-gui" E2E_AGENTS STACK_IMAGE_REPO STACK_IMAGE_TAG)

# Build local images and run the reviewer-side browser suite against them.
[group('Stack tests')]
e2e-gui-review-stack-local: images (_stack-suite "e2e-gui-review" "1")

# Run the reviewer-side browser suite against published images.
[group('Stack tests')]
e2e-gui-review-stack-published STACK_IMAGE_REPO=(DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE) STACK_IMAGE_TAG=IMAGE_TAG: (_stack-suite "e2e-gui-review" "1" STACK_IMAGE_REPO STACK_IMAGE_TAG)

# Build local images and run the narrated GUI demo against them.
[group('Stack tests')]
demo-gui-stack-local: images (_stack-suite "demo-gui" "1")

# Run the narrated GUI demo against published images.
[group('Stack tests')]
demo-gui-stack-published STACK_IMAGE_REPO=(DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE) STACK_IMAGE_TAG=IMAGE_TAG: (_stack-suite "demo-gui" "1" STACK_IMAGE_REPO STACK_IMAGE_TAG)

# Build local images and run the API walkthrough against them.
[group('Stack tests')]
demo-api-stack-local: images (_stack-suite "demo-api" "1")

# Run the API walkthrough against published images.
[group('Stack tests')]
demo-api-stack-published STACK_IMAGE_REPO=(DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE) STACK_IMAGE_TAG=IMAGE_TAG: (_stack-suite "demo-api" "1" STACK_IMAGE_REPO STACK_IMAGE_TAG)
