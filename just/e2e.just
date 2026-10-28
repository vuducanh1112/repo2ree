E2E_BUNDLE_DIR := ROOT + "/dist/bundles"
E2E_EXEC_BUNDLE := E2E_BUNDLE_DIR + "/exec"
E2E_TOOLS_BUNDLE := E2E_BUNDLE_DIR + "/tools"
DEFAULT_API_DEMO_CAST := REPO2REE_TEST_RUN_DIR + "/python/attachments/api-walkthrough.cast"
# Per-test stacks running side by side in the per-test tiers (a recipe argument overrides it).
E2E_JOBS := "4"

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
_source-stack-playwright project locations mode docker_mode:
    python -m repo2ree_testbed e2e --project {{ quote(project) }} --mode {{ quote(mode) }} --compute-locations {{ quote(locations) }} --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run the measured author-side browser E2E tier.
[group('E2E tests')]
test-e2e-gui locations=DEFAULT_E2E_LOCATIONS mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE: build-e2e-bundles (_source-stack-playwright "e2e-gui" locations mode docker_mode)

# Run the instant GUI tier: each test on a fresh stack, into test-artifacts/e2e/<run>/tests/<test>/.
[group('E2E tests')]
test-e2e-gui-instant mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE jobs=E2E_JOBS: build-e2e-bundles (_e2e-gui-instant jobs mode docker_mode)

# Run the system tier, no browser: each test on a fresh stack, into test-artifacts/e2e/<run>/tests/<test>/.
[group('E2E tests')]
test-e2e-system locations="1" mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE jobs=E2E_JOBS: build-e2e-bundles (_e2e-system jobs locations mode docker_mode)

# Run the fault suite, not gated: each test on a fresh stack that injects the faults it asks for.
[group('E2E tests')]
test-e2e-faults jobs=E2E_JOBS: build-e2e-bundles
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/faults/run_fault_suite.py") }} --tier e2e-faults --per-test --jobs {{ quote(jobs) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run seeded random author sessions with faults between steps, not gated: each seed on a fresh stack, replayable.
[group('E2E tests')]
test-e2e-chaos seeds="4" steps="12" jobs=E2E_JOBS: build-e2e-bundles
    CHAOS_SEEDS={{ quote(seeds) }} CHAOS_STEPS={{ quote(steps) }} python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/chaos/run_chaos_suite.py") }} --tier e2e-chaos --per-test --jobs {{ quote(jobs) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Fuzz every API operation against its contract on one stack, not gated.
[group('E2E tests')]
test-e2e-fuzz: build-e2e-bundles
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/fuzz/run_fuzz_suite.py") }} --tier e2e-fuzz --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run the measured reviewer-side browser E2E tier.
[group('E2E tests')]
test-e2e-review mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE: build-e2e-bundles (_source-stack-playwright "e2e-gui-review" "1" mode docker_mode)

# List the machines the e2e tiers can run on: `local`, and those in .config/machines.toml (untracked).
[group('E2E tests')]
list-e2e-machines:
    python -m repo2ree_testbed machine list

# Clean up what runs left on an e2e machine, take its dev container down, and delete its clone.
[group('E2E tests')]
remove-e2e-machine machine:
    python -m repo2ree_testbed machine remove {{ quote(machine) }}

# Stop the job running on an e2e machine: restart its dev container and clean up the stacks the job left.
[group('E2E tests')]
cancel-e2e-on machine:
    python -m repo2ree_testbed machine cancel {{ quote(machine) }}

# Run the assurance gate on an e2e machine, bring its receipt and runs here, and check the receipt holds for HEAD.
[group('E2E tests')]
gate-e2e-on machine="local" jobs="":
    python -m repo2ree_testbed machine gate {{ quote(machine) }} {{ if jobs != "" { "--jobs " + quote(jobs) } else { "" } }}
    python -m scripts.gates.assurance_gate verify

# Run an e2e recipe on a machine (e.g. `just test-e2e-on vm test-e2e-system`) and bring back the per-test runs it made.
[group('E2E tests')]
test-e2e-on machine +recipe:
    python -m repo2ree_testbed machine run {{ quote(machine) }} {{ recipe }}

# Check and draw a per-test run again: verdicts, traces, and index pages (the newest run by default).
[group('E2E tests')]
inspect-e2e run="":
    python -m repo2ree_testbed inspect {{ quote(run) }}

# Record the measured narrated browser demo.
[group('Demos')]
demo-gui mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE: build-e2e-bundles (_source-stack-playwright "demo-gui" "1" mode docker_mode)

# Record the measured external-capsule browser demo.
[group('Demos')]
demo-gui-code-ocean mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE: build-e2e-bundles (_source-stack-playwright "demo-gui-code-ocean" "1" mode docker_mode)

# Record the measured pure-API walkthrough and render its transcript.
[group('Demos')]
demo-api mode=DEFAULT_E2E_COMPUTE_LOCATION_MODE docker_mode=DEFAULT_E2E_PROVIDER_DOCKER_MODE cast=DEFAULT_API_DEMO_CAST transcript="": build-e2e-bundles
    #!/usr/bin/env bash
    set -euo pipefail
    cast={{ quote(cast) }}
    transcript={{ quote(transcript) }}
    transcript=${transcript:-${cast%.cast}.md}
    mkdir -p "$(dirname "$cast")"
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/e2e/api_walkthrough.py") }} --tier demo-api --mode {{ quote(mode) }} --compute-locations 1 --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} --record "$cast"
    python3 {{ quote(ROOT + "/api/tests/e2e/render_cast_transcript.py") }} "$cast" "$transcript"

# Start the local image-backed stack.
[group('Stack management')]
stack-up locations=DEFAULT_STACK_LOCATIONS:
    python -m repo2ree_testbed images up --compute-locations {{ quote(locations) }}

# Stop the image-backed stack while retaining volumes.
[group('Stack management')]
stack-down:
    python -m repo2ree_testbed images down

# Stop the image-backed stack and remove its volumes and workbenches.
[group('Stack management')]
stack-clean:
    python -m repo2ree_testbed images down --volumes

# Remove leftover workbenches; run `just clean-workbenches 1` to include bundle stores.
[group('Stack management')]
clean-workbenches store="":
    python -m repo2ree_testbed workbench-cleanup {{ if store != "" { "--store" } else { "" } }}

# Build local images and run any browser or API suite against an owned stack.
[group('Stack tests')]
test-stack-local suite locations="1": build-images
    python -m repo2ree_testbed image-suite --suite {{ quote(suite) }} --compute-locations {{ quote(locations) }} --images local

# Run any browser or API suite against published images in an owned stack.
[group('Stack tests')]
test-stack-published suite locations="1" repository=DEFAULT_STACK_IMAGE_REPO tag=DEFAULT_STACK_IMAGE_TAG:
    python -m repo2ree_testbed image-suite --suite {{ quote(suite) }} --compute-locations {{ quote(locations) }} --images published --repository {{ quote(repository) }} --tag {{ quote(tag) }}

# Run any browser or API suite against the already-running image stack.
[group('Stack tests')]
test-stack-existing suite:
    python -m repo2ree_testbed image-suite --suite {{ quote(suite) }} --compute-locations 1 --images local --existing

# Remove old e2e runs, suite recordings, and stale stack state; every e2e run does this first.
[group('Stack management')]
prune-test-artifacts *args:
    python -m repo2ree_testbed prune {{ args }}

# Remove unused bundle-store caches, keeping the current checkout's and the newest `keep` others.
[group('Stack management')]
gc-bundle-store keep="0":
    python -m repo2ree_testbed workbench-cleanup --store-gc {{ quote(keep) }}
