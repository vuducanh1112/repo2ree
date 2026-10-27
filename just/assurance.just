# Assurance collects evidence about the product, checks it against the specification,
# and presents the results; none of it ships. The collector gathers a deployment's
# evidence through its control plane into a dossier. The checker judges owner
# journals, REE histories, and stores against assurance/spec, separately from the
# backend it observes. Traceview draws what the checker verified (its
# verification.json), one behaviour trace per REE, with spans as context, and folds
# many verifications into one catalogue of operations for the overview. Each is its
# own step on the previous one's artifact.

# Static checks for every assurance package.
[group('Assurance')]
check-assurance: check-assurance-checker check-assurance-dossier check-assurance-collector check-assurance-traceview

# Tests for every assurance package.
[group('Assurance')]
test-assurance: test-assurance-checker test-assurance-dossier test-assurance-collector test-assurance-traceview

# System evidence tooling has independent checks and test artifacts.
ASSURANCE_METRIC_PATHS := "assurance/checker/src assurance/dossier/src assurance/collector/src assurance/traceview/src"

# Static checks, the checker's independence contracts, and a fresh generated contract (contracts/behaviour).
[group('Assurance')]
check-assurance-checker: (_check-python-package "assurance/checker")
    lint-imports --config assurance/checker/pyproject.toml
    python -m repo2ree_assurance_checker generate --check

# Checker tests; the history tests need git.
[group('Assurance')]
test-assurance-checker:
    pytest assurance/checker/tests

# Static checks and the views' import contracts: public checker surface only, no runtime packages.
[group('Assurance')]
check-assurance-traceview: (_check-python-package "assurance/traceview")
    lint-imports --config assurance/traceview/pyproject.toml

# Traceview tests; the dossier smoke test needs an e2e run's dossier under test-artifacts/e2e.
[group('Assurance')]
test-assurance-traceview:
    pytest assurance/traceview/tests

# Static checks and the collector's import contracts: HTTP to the control plane, no runtime packages.
[group('Assurance')]
check-assurance-collector: (_check-python-package "assurance/collector")
    lint-imports --config assurance/collector/pyproject.toml

# Static checks and the format's import contract: the leaf every assurance step shares, knowing none of them.
[group('Assurance')]
check-assurance-dossier: (_check-python-package "assurance/dossier")
    lint-imports --config assurance/dossier/pyproject.toml

# Tests of the dossier format.
[group('Assurance')]
test-assurance-dossier:
    pytest assurance/dossier/tests

# Collector tests; they serve the control plane's behaviour endpoints from a local stub.
[group('Assurance')]
test-assurance-collector:
    pytest assurance/collector/tests

# Collect a running deployment's behaviour evidence through its control plane (exit 1 if any source is missing).
[group('Assurance')]
collect-dossier control_plane output *rees:
    python -m repo2ree_assurance_collector {{ quote(output) }} --control-plane {{ quote(control_plane) }} {{ prepend("--ree ", rees) }}

# Regenerate the published event schema (contracts/behaviour) after editing assurance/spec.
[group('Assurance')]
generate-behaviour:
    python -m repo2ree_assurance_checker generate

# Print the behaviour specification as JSON (repo2ree-behaviour-spec/1), as of a Git revision if given, or write it to output.
[group('Assurance')]
export-behaviour-spec rev="" output="":
    python -m repo2ree_assurance_checker export {{ if rev != "" { "--at " + quote(rev) } else { "" } }} {{ if output != "" { "-o " + quote(output) } else { "" } }}

# Judge per-test runs as the assurance gate would (the newest of each tier by default), certifying nothing.
[group('E2E tests')]
judge-e2e *runs:
    #!/usr/bin/env bash
    set -euo pipefail
    runs="{{ runs }}"
    if [[ -z "$runs" ]]; then
        for tier in e2e-system e2e-gui-instant; do
            runs+=" $(ls -td {{ quote(REPO2REE_TEST_RUN_DIR + "/e2e") }}/"$tier"-*/ 2>/dev/null | head -n 1)"
        done
    fi
    [[ -n "${runs// /}" ]] || { echo "no per-test run under {{ REPO2REE_TEST_RUN_DIR }}/e2e" >&2; exit 2; }
    python -m scripts.gates.assurance_gate judge $runs

# Reports go into the dossier's run test directory, or for one collected elsewhere (collect-dossier) under the
# assurance directory; exit 0 passed, 1 violated, 2 inconclusive.
# Judge one dossier and draw its traces and provenance (the newest any e2e run left by default).
[group('Assurance')]
inspect-dossier dossier="":
    python -m repo2ree_testbed inspect --dossier {{ quote(dossier) }}

[group('Assurance')]
generate-assurance-metrics:
    mkdir -p {{ quote(METRICS_DIR + "/assurance") }}
    lizard -l python -i -1 -o {{ quote(METRICS_DIR + "/assurance/complexity.html") }} {{ ASSURANCE_METRIC_PATHS }}
    lizard -l python -i -1 --csv {{ ASSURANCE_METRIC_PATHS }} > {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
    python -m repo2ree_repoview stamp --manifest {{ quote(METRICS_DIR + "/manifest.json") }} --by generate-assurance-metrics {{ quote(METRICS_DIR + "/assurance/complexity.html") }} {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
