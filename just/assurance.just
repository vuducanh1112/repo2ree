# Assurance collects evidence about the product, checks it against the specification,
# and presents the results; none of it ships. The collector gathers a deployment's
# evidence through its control plane into a dossier. The checker judges owner
# journals, REE histories, and stores against assurance/spec, separately from the
# backend it observes. Traceview draws what the checker verified (its
# verification.json), one behaviour trace per REE, with spans as context, and folds
# many verifications into one catalogue of operations for the overview. Each is its
# own step on the previous one's artifact.

# Static checks for every assurance package, each with its own import contracts, and a fresh
# generated contract (contracts/behaviour). The checker stays independent of the product, the
# collector reaches it only over HTTP, the views see only the checker's public surface, and the
# dossier format, the leaf every step shares, knows none of them.
[group('Assurance')]
check-assurance: (check-package `python scripts/workspace.py assurance`)
    python -m repo2ree_assurance_checker generate --check

# Tests for every assurance package. The checker's history tests need git; the collector's serve
# the control plane's behaviour endpoints from a local stub; the traceview dossier smoke test needs
# an e2e run's dossier under test-artifacts/e2e.
[group('Assurance')]
test-assurance:
    for package in $(python scripts/workspace.py assurance); do pytest "$package/tests"; done

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

# Write the behaviour specification as JSON (repo2ree-behaviour-spec/1) for the overview.
[group('Assurance')]
export-spec:
    mkdir -p {{ quote(EXPORT_DIR) }}
    python -m repo2ree_assurance_checker export -o {{ quote(EXPORT_DIR + "/spec.json") }}
    {{ STAMP_EXPORTS }} --by export-spec {{ quote(EXPORT_DIR + "/spec.json") }}

# Judge and draw the assurance-gate receipt's tests again with this tree, from the evidence their runs left
# (seconds, no e2e run): verdicts and traces under reports/assurance/, for the overview.
[group('Assurance')]
report-assurance-gate:
    python -m repo2ree_repoview gate-reports -o {{ quote(GATE_REPORT_DIR) }}
    python -m repo2ree_repoview stamp --manifest {{ quote(GATE_REPORT_DIR + "/manifest.json") }} --by report-assurance-gate {{ quote(GATE_REPORT_DIR + "/reports.json") }}

# Fold this tree's verifications of the assurance-gate receipt's tests into the catalogue of operations (JSON) for the overview.
[group('Assurance')]
export-operations: report-assurance-gate
    #!/usr/bin/env bash
    set -euo pipefail
    listed=$(python -m repo2ree_repoview gate-verifications)
    verifications=()
    [[ -z "$listed" ]] || mapfile -t verifications <<< "$listed"
    python -m repo2ree_assurance_traceview operations "${verifications[@]}" -o {{ quote(EXPORT_DIR + "/operations.json") }}
    {{ STAMP_EXPORTS }} --by export-operations {{ quote(EXPORT_DIR + "/operations.json") }}

# Judge per-test runs as the assurance gate would (the newest of each tier by default), certifying nothing.
[group('E2E tests')]
judge-e2e *runs:
    #!/usr/bin/env bash
    set -euo pipefail
    runs="{{ runs }}"
    if [[ -z "$runs" ]]; then
        for tier in e2e-system e2e-gui-instant e2e-faults; do
            runs+=" $(ls -td {{ quote(REPO2REE_TEST_RUN_DIR + "/e2e") }}/"$tier"-*/ 2>/dev/null | head -n 1)"
        done
    fi
    [[ -n "${runs// /}" ]] || { echo "no per-test run under {{ REPO2REE_TEST_RUN_DIR }}/e2e" >&2; exit 2; }
    python -m scripts.gates.assurance_gate judge $runs

# Assess the behaviour of a per-test run's tests, or of one dossier (the newest run by default): check each
# dossier against the behaviour specification and record its verdict. A run's verdicts go into its run.json,
# a test's into its verification/; a dossier collected elsewhere (collect-dossier) is assessed under the
# assurance directory. A dossier exits with its verdict: 0 passed, 1 violated, 2 inconclusive.
[group('Assurance')]
assess-behaviour path="":
    python -m repo2ree_testbed assess {{ quote(path) }}

# Visualize what assess-behaviour recorded, for a run or a dossier (the newest run by default): each test's
# behaviour traces and provenance, and the pages to browse a run by.
[group('Assurance')]
visualize-behaviour path="":
    python -m repo2ree_testbed visualize {{ quote(path) }}

[group('Assurance')]
generate-assurance-metrics:
    mkdir -p {{ quote(METRICS_DIR + "/assurance") }}
    lizard -l python -i -1 -o {{ quote(METRICS_DIR + "/assurance/complexity.html") }} $(python scripts/workspace.py assurance --src)
    lizard -l python -i -1 --csv $(python scripts/workspace.py assurance --src) > {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
    python -m repo2ree_repoview stamp --manifest {{ quote(METRICS_DIR + "/manifest.json") }} --by generate-assurance-metrics {{ quote(METRICS_DIR + "/assurance/complexity.html") }} {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
