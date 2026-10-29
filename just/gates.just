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

# Each tier, run per test. `exit_on` is `tests` (fail when a test failed) or `run` (fail only when
# the run broke, for the gate, which judges the tests itself). With `select` (parts of test ids) it
# runs only those tests, which the gate never asks for and never certifies.
[private]
_e2e-gui-instant jobs mode docker_mode exit_on *select:
    python -m repo2ree_testbed e2e --project e2e-gui-instant --per-test --exit-on {{ quote(exit_on) }} --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations 1 --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} {{ if select != "" { "--select " + quote(select) } else { "" } }}

[private]
_e2e-system jobs locations mode docker_mode exit_on *select:
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/system/run_system_suite.py") }} --tier e2e-system --per-test --exit-on {{ quote(exit_on) }} --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations {{ quote(locations) }} --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} {{ if select != "" { "--select " + quote(select) } else { "" } }}

[private]
_e2e-faults jobs exit_on *select:
    python -m repo2ree_testbed e2e --script {{ quote(ROOT + "/api/tests/faults/run_fault_suite.py") }} --tier e2e-faults --per-test --exit-on {{ quote(exit_on) }} --jobs {{ quote(jobs) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }} {{ if select != "" { "--select " + quote(select) } else { "" } }}

# Every tier at once, each in a run directory of its own that names this invocation. A tier fails
# only when its run broke; which tests failed is certify's to judge.
[private]
[parallel]
_gated-tiers jobs: (_e2e-system jobs "1" DEFAULT_E2E_COMPUTE_LOCATION_MODE DEFAULT_E2E_PROVIDER_DOCKER_MODE "run") (_e2e-gui-instant jobs DEFAULT_E2E_COMPUTE_LOCATION_MODE DEFAULT_E2E_PROVIDER_DOCKER_MODE "run") (_e2e-faults jobs "run")

# A test is accepted when it passed and its behaviour passed, or it is excused by
# assurance/checker/expected-verdicts.toml (as every xfail must be) and left exactly those rules open.
# The suite together must reach every specified rule, edge, and message the same file does not excuse.
# Run the per-test e2e tiers on HEAD, judge every test's behaviour, and certify HEAD's tree.
[group('Release gates')]
assurance-gate jobs=E2E_JOBS: _require-clean-tree build-e2e-bundles (_gated-tiers jobs)
    python -m scripts.gates.assurance_gate certify --invocation "$REPO2REE_TEST_RUN_ID"

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
