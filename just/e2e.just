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
e2e-bundles: _stage-nix-sources
    @mkdir -p {{ quote(E2E_BUNDLE_DIR) }}
    nix build .#exec-bundle -o {{ quote(E2E_EXEC_BUNDLE) }}
    nix build .#tools-bundle -o {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_source-stack-playwright project agents:
    E2E_WORKBENCH_IMAGE={{ quote(E2E_WORKBENCH_IMAGE) }} E2E_WORKBENCH_DOCKER_MODE={{ quote(E2E_WORKBENCH_DOCKER_MODE) }} E2E_EXEC_BUNDLE={{ quote(E2E_EXEC_BUNDLE) }} E2E_TOOLS_BUNDLE={{ quote(E2E_TOOLS_BUNDLE) }} scripts/test-stack/e2e-stack.sh --project {{ quote(project) }} --agents {{ quote(agents) }}

# Run the measured author-side browser E2E tier.
[group('E2E tests')]
e2e-gui agents=E2E_AGENTS: e2e-bundles (_source-stack-playwright "e2e-gui" agents)

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
demo-api: e2e-bundles
    @mkdir -p "$(dirname {{ quote(API_DEMO_CAST) }})"
    E2E_WORKBENCH_IMAGE={{ quote(E2E_WORKBENCH_IMAGE) }} E2E_WORKBENCH_DOCKER_MODE={{ quote(E2E_WORKBENCH_DOCKER_MODE) }} E2E_EXEC_BUNDLE={{ quote(E2E_EXEC_BUNDLE) }} E2E_TOOLS_BUNDLE={{ quote(E2E_TOOLS_BUNDLE) }} scripts/test-stack/e2e-stack.sh --script {{ quote(ROOT + "/api/tests/e2e/api_agent_walkthrough.py") }} --tier demo-api --record {{ quote(API_DEMO_CAST) }}
    python3 {{ quote(ROOT + "/api/tests/e2e/render_cast_transcript.py") }} {{ quote(API_DEMO_CAST) }} {{ quote(API_DEMO_TRANSCRIPT) }}

# Start the local image-backed stack.
[group('Stack management')]
stack-up agents=E2E_AGENTS:
    STACK_AGENTS={{ quote(agents) }} scripts/test-stack/image-stack.sh up

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
workbench-clean:
    scripts/test-stack/workbench-cleanup.sh {{ if env("STORE", "") != "" { "--store" } else { "" } }}

# Evict unreferenced bundle-store caches older than the requested days.
[group('Stack management')]
store-gc:
    scripts/test-stack/workbench-cleanup.sh --store-gc {{ quote(env("STORE_GC_DAYS", "14")) }}

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

# Build local images and run the author-side browser suite against them.
[group('Stack tests')]
e2e-gui-stack-local agents=E2E_AGENTS: images
    scripts/test-stack/run-image-suite.sh e2e-gui {{ quote(agents) }}

# Run the author-side browser suite against published images.
[group('Stack tests')]
e2e-gui-stack-published agents=E2E_AGENTS:
    scripts/test-stack/run-image-suite.sh e2e-gui {{ quote(agents) }} {{ quote(STACK_IMAGE_REPO) }} {{ quote(STACK_IMAGE_TAG) }}

# Build local images and run the reviewer-side browser suite against them.
[group('Stack tests')]
e2e-gui-review-stack-local: images
    scripts/test-stack/run-image-suite.sh e2e-gui-review 1

# Run the reviewer-side browser suite against published images.
[group('Stack tests')]
e2e-gui-review-stack-published:
    scripts/test-stack/run-image-suite.sh e2e-gui-review 1 {{ quote(STACK_IMAGE_REPO) }} {{ quote(STACK_IMAGE_TAG) }}

# Build local images and run the narrated GUI demo against them.
[group('Stack tests')]
demo-gui-stack-local: images
    scripts/test-stack/run-image-suite.sh demo-gui 1

# Run the narrated GUI demo against published images.
[group('Stack tests')]
demo-gui-stack-published:
    scripts/test-stack/run-image-suite.sh demo-gui 1 {{ quote(STACK_IMAGE_REPO) }} {{ quote(STACK_IMAGE_TAG) }}

# Build local images and run the API walkthrough against them.
[group('Stack tests')]
demo-api-stack-local: images
    scripts/test-stack/run-image-suite.sh demo-api 1

# Run the API walkthrough against published images.
[group('Stack tests')]
demo-api-stack-published:
    scripts/test-stack/run-image-suite.sh demo-api 1 {{ quote(STACK_IMAGE_REPO) }} {{ quote(STACK_IMAGE_TAG) }}
