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
_source-stack-playwright project locations:
    python -m repo2ree_testbed e2e --project {{ quote(project) }} --compute-locations {{ quote(locations) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# The per-test tiers below run as the assurance gate runs them, with `jobs` stacks side by side.
# Trailing parts of test ids run only the tests whose id contains one (e.g. `just test-e2e-faults 4
# test_a_paused`); a run limited so certifies nothing.

# Run the instant GUI tier: each test on a fresh stack, into test-artifacts/e2e/<run>/tests/<test>/.
[group('E2E tests')]
test-e2e-gui-instant jobs=E2E_JOBS *select: build-e2e-bundles (_tier-gui-instant jobs "tests" select)

# Run the system tier, no browser: each test on a fresh stack, into test-artifacts/e2e/<run>/tests/<test>/.
[group('E2E tests')]
test-e2e-system jobs=E2E_JOBS *select: build-e2e-bundles (_tier-system jobs "tests" select)

# Run the fault suite, a tier of the assurance gate: each test on a fresh stack that injects the faults it asks for.
[group('E2E tests')]
test-e2e-faults jobs=E2E_JOBS *select: build-e2e-bundles (_tier-faults jobs "tests" select)

# Build and load the image of a machine the environments tier installs a workbench on.
[private]
_load-environment name: _stage-nix-sources
    nix build .#testbed-environment-{{ name }} -o {{ quote(ROOT + "/dist/environments/" + name) }}
    docker load --input {{ quote(ROOT + "/dist/environments/" + name) }}

# Check one machine a workbench is installed on starts, runs what it offers, and leaves nothing behind.
[group('E2E tests')]
check-environment name: (_load-environment name)
    python -m repo2ree_testbed environment {{ quote(name) }}

# Run the golden path on one machine a workbench is installed on (bare, docker, podman, podman-host, slurm), not gated.
[group('E2E tests')]
test-e2e-environment name: (_load-environment name)
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/testbed/suites/environments/run_environment_suite.py") }} --tier e2e-environment-{{ name }} --environment {{ quote(name) }} --per-test --exit-on tests

# Run what else holds of REEs whose author's scripts submit to Slurm or enter Apptainer, on the Slurm machine, not gated.
[group('E2E tests')]
test-e2e-slurm *select: (_load-environment "slurm")
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/testbed/suites/slurm/run_slurm_suite.py") }} --tier e2e-slurm --environment slurm --per-test --exit-on tests {{ if select != "" { "--select " + quote(select) } else { "" } }}

# Run seeded random author sessions with faults between steps, not gated: each seed on a fresh stack, replayable.
[group('E2E tests')]
test-e2e-chaos seeds="4" steps="12" jobs=E2E_JOBS: build-e2e-bundles
    CHAOS_SEEDS={{ quote(seeds) }} CHAOS_STEPS={{ quote(steps) }} python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/testbed/suites/chaos/run_chaos_suite.py") }} --tier e2e-chaos --per-test --jobs {{ quote(jobs) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Fuzz every API operation against its contract on one stack, not gated.
[group('E2E tests')]
test-e2e-fuzz: build-e2e-bundles
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/testbed/suites/fuzz/run_fuzz_suite.py") }} --tier e2e-fuzz --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# Run every API showcase, authoring and review, each test on a fresh stack on the machine its showcase names; assess the run and certify it if it qualifies. Select tests by parts of their ids (e.g. `just test-showcase-api 4 conda/`).
[group('E2E tests')]
test-showcase-api jobs=E2E_JOBS *select: (_tier-showcase-api jobs select) (assess-behaviour "--invocation" REPO2REE_TEST_RUN_ID)
    python -m scripts.gates.tiers certify --tier showcase-api --if-eligible

[private]
_tier-showcase-api jobs *select: _load-showcase-environments
    python -m repo2ree_testbed api-showcase run --jobs {{ quote(jobs) }} {{ if select != "" { "--select " + select } else { "" } }}

# Build and load the image of each machine an API showcase runs on.
[private]
_load-showcase-environments:
    #!/usr/bin/env bash
    set -euo pipefail
    for environment in $(python -m repo2ree_testbed api-showcase environments); do
        just --justfile {{ quote(ROOT + "/justfile") }} _load-environment "$environment"
    done

# Run the showcase tier, real projects end to end: each scenario on a fresh stack of two compute locations; assess the run and certify it if it qualifies.
[group('E2E tests')]
test-showcase jobs=E2E_JOBS *select: (_tier-showcase jobs select) (assess-behaviour "--invocation" REPO2REE_TEST_RUN_ID)
    python -m scripts.gates.tiers certify --tier showcase --if-eligible

[private]
_tier-showcase jobs *select: build-e2e-bundles
    python -m repo2ree_testbed e2e --project showcase --per-test --exit-on tests --jobs {{ quote(jobs) }} --compute-locations 2 --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} {{ if select != "" { "--select " + quote(select) } else { "" } }}

# A machine is where a recipe runs: `local`, or one in .config/machines.toml (untracked), whose
# dev container runs one job at a time from a clone of HEAD and hands back what the job wrote.

# Run a recipe on a machine (e.g. `just on vm test-backend-integration`) and bring back what it wrote under test-artifacts/, .receipts/, and logs/.
[group('Machines')]
on machine +recipe:
    python -m repo2ree_testbed machine run {{ quote(machine) }} {{ recipe }}

# Run a recipe on a machine against the working tree, committed beside the branch (e.g. `just on-wip vm test-e2e-faults 8 test_a_paused`).
[group('Machines')]
on-wip machine +recipe:
    python -m repo2ree_testbed machine run --wip {{ quote(machine) }} {{ recipe }}

# Run the assurance gate on a machine with that machine's jobs, and check its receipt holds for HEAD.
[group('Machines')]
gate-e2e-on machine="local" jobs="":
    python -m repo2ree_testbed machine gate {{ quote(machine) }} {{ if jobs != "" { "--jobs " + quote(jobs) } else { "" } }}
    python -m scripts.gates.assurance_gate verify

# Manage the machines: `list`; `cancel <machine>` stops its job and cleans up after it; `gc <machine>` prunes its clone, Docker build cache unused for a day, and images unused for a week; `remove <machine>` takes its dev container down and deletes its clone.
[group('Machines')]
machine +args:
    python -m repo2ree_testbed machine {{ args }}

# Record the narrated browser demo: the Python Docker showcase scenario, captioned and paced, with video.
[group('Demos')]
demo-gui: build-e2e-bundles (_source-stack-playwright "demo-gui" "1")

# Record the measured pure-API walkthrough and render its transcript.
[group('Demos')]
demo-api cast=DEFAULT_API_DEMO_CAST transcript="": build-e2e-bundles
    #!/usr/bin/env bash
    set -euo pipefail
    cast={{ quote(cast) }}
    transcript={{ quote(transcript) }}
    transcript=${transcript:-${cast%.cast}.md}
    mkdir -p "$(dirname "$cast")"
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/testbed/suites/walkthrough/api_walkthrough.py") }} --tier demo-api --compute-locations 1 --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} --record "$cast"
    python3 {{ quote(ROOT + "/testbed/suites/walkthrough/render_cast_transcript.py") }} "$cast" "$transcript"

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

# Remove the job and bench containers runs left, and the volumes nothing uses any more.
[group('Stack management')]
clean-workbenches:
    python -m repo2ree_testbed workbench-cleanup

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
