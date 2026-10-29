# The gates, and the tiers the assurance gate runs. This file is protected (zones.toml, gates):
# what runs and how it is judged decide what a receipt covers, so it changes apart
# from the product it judges.

# The receipt records the exact tree only after every prerequisite passes;
# the pre-commit hook performs the cheap content comparison later.
# Run the fast checks, documentation build, and unit tests, then certify the tree.
[group('Release gates')]
commit-gate: check build-docs test-unit
    python -m scripts.gates.commit_gate write
    @echo ">> commit gate green — receipt written for the current tree"

# Require the current clean content to have passed the commit gate.
[private]
_require-current-commit-gate:
    python -m scripts.gates.commit_gate verify

[private]
_e2e-gui-instant jobs mode docker_mode:
    python -m repo2ree_testbed e2e --project e2e-gui-instant --per-test --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations 1 --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_e2e-system jobs locations mode docker_mode:
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/system/run_system_suite.py") }} --tier e2e-system --per-test --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations {{ quote(locations) }} --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_e2e-faults jobs:
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/faults/run_fault_suite.py") }} --tier e2e-faults --per-test --jobs {{ quote(jobs) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# A test is accepted when it passed and its behaviour passed, or it is excused by
# assurance/checker/expected-verdicts.toml (as every xfail must be) and left exactly those rules open.
# The suite together must reach every specified rule, edge, and message the same file does not excuse.
# Run the per-test e2e tiers on HEAD, judge every test's behaviour, and certify HEAD's tree.
[group('Release gates')]
assurance-gate jobs=E2E_JOBS: _require-clean-tree build-e2e-bundles
    #!/usr/bin/env bash
    set -euo pipefail
    # Every tier at once, each in a run directory of its own; each run is read from its tier's own output.
    logs=$(mktemp -d)
    just _e2e-system {{ quote(jobs) }} 1 {{ quote(DEFAULT_E2E_COMPUTE_LOCATION_MODE) }} {{ quote(DEFAULT_E2E_PROVIDER_DOCKER_MODE) }} > "$logs/system.log" 2>&1 &
    system=$!
    just _e2e-gui-instant {{ quote(jobs) }} {{ quote(DEFAULT_E2E_COMPUTE_LOCATION_MODE) }} {{ quote(DEFAULT_E2E_PROVIDER_DOCKER_MODE) }} > "$logs/gui.log" 2>&1 &
    gui=$!
    just _e2e-faults {{ quote(jobs) }} > "$logs/faults.log" 2>&1 &
    faults=$!
    wait "$system" || true
    wait "$gui" || true
    wait "$faults" || true
    runs=()
    for tier in system gui faults; do
        grep -E '^>> (\[|passed|failed|xfailed|skipped|per-test run)' "$logs/$tier.log" || true
        run=$(sed -n 's/^>> per-test run: //p' "$logs/$tier.log" | tail -n 1)
        [[ -n "$run" ]] || { tail -n 60 "$logs/$tier.log" >&2; echo ">> the $tier tier left no per-test run (log: $logs/$tier.log)" >&2; exit 1; }
        runs+=("$run")
    done
    python -m scripts.gates.assurance_gate certify "${runs[@]}"

# Require an assurance-gate receipt for HEAD's clean tree.
[private]
_require-current-assurance-gate:
    python -m scripts.gates.assurance_gate verify

# Run the complete pre-publish gate and certify the local image set.
[group('Release gates')]
publish-gate: _require-clean-tree _require-current-commit-gate _require-current-assurance-gate test-backend-integration test-gui-accessibility test-gui-screenshots test-e2e-gui test-e2e-review build-images
    #!/usr/bin/env bash
    set -euo pipefail
    python -m repo2ree_testbed image-suite --suite e2e-gui --compute-locations {{ quote(DEFAULT_STACK_LOCATIONS) }} --images local
    python -m repo2ree_testbed image-suite --suite e2e-gui-review --compute-locations 1 --images local
    revision=$(git describe --always)
    python -m scripts.gates.publish_gate write {{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }} "$revision"
    echo ">> publish gate green — certified local image set for $revision"
    echo ">> publish with: just publish-candidate"
