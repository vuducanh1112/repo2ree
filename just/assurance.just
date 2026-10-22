# Assurance collects evidence, checks specifications, and presents results.
# Collect gathers a deployment's evidence through its control plane into a
# recording. Conformance checks owner journals, REE histories, and stores against
# specifications/behaviour, separately from the backend it observes. Traceview
# draws what conformance verified (its verification.json), operation by operation, with
# spans as context. Each is its own step on the previous one's artifact.

# Static checks for every assurance package.
[group('Assurance')]
check-assurance: check-conformance check-traceview check-collect check-recording

# Tests for every assurance package.
[group('Assurance')]
test-assurance: test-conformance test-traceview test-collect test-recording

# System evidence tooling has independent checks and test artifacts.
ASSURANCE_METRIC_PATHS := "conformance/src traceview/src collect/src recording/src"

# Static checks, the checker's independence contracts, and a fresh generated contract (contracts/behaviour).
[group('Assurance')]
check-conformance: (_check-python-package "conformance")
    lint-imports --config conformance/pyproject.toml
    python -m repo2ree_conformance generate --check

# Conformance tests; the system test drives the real owners and needs git.
[group('Assurance')]
test-conformance:
    pytest conformance/tests

# Static checks and the views' import contracts: public checker surface only, no runtime packages.
[group('Assurance')]
check-traceview: (_check-python-package "traceview")
    lint-imports --config traceview/pyproject.toml

# Traceview tests; the recording smoke test needs an e2e run's recording under test-artifacts/e2e.
[group('Assurance')]
test-traceview:
    pytest traceview/tests

# Static checks and the collector's import contracts: HTTP to the control plane, no runtime packages.
[group('Assurance')]
check-collect: (_check-python-package "collect")
    lint-imports --config collect/pyproject.toml

# Static checks and the format's import contract: the leaf every assurance step shares, knowing none of them.
[group('Assurance')]
check-recording: (_check-python-package "recording")
    lint-imports --config recording/pyproject.toml

# Tests of the recording format.
[group('Assurance')]
test-recording:
    pytest recording/tests

# Collector tests; they serve the control plane's behaviour endpoints from a local stub.
[group('Assurance')]
test-collect:
    pytest collect/tests

# Collect a running deployment's behaviour evidence through its control plane (exit 1 if any source is missing).
[group('Assurance')]
collect-behaviour control_plane output *rees:
    python -m repo2ree_collect {{ quote(output) }} --control-plane {{ quote(control_plane) }} {{ prepend("--ree ", rees) }}

# Regenerate the published event schema (contracts/behaviour) after editing specifications/behaviour.
[group('Assurance')]
generate-behaviour:
    python -m repo2ree_conformance generate

# Print the behaviour specification as JSON (repo2ree-behaviour-spec/1), as of a Git revision if given, or write it to output.
[group('Assurance')]
export-behaviour-spec rev="" output="":
    python -m repo2ree_conformance export {{ if rev != "" { "--at " + quote(rev) } else { "" } }} {{ if output != "" { "-o " + quote(output) } else { "" } }}

# Every e2e run leaves one recording per test (a whole-suite run, one for the suite) under its run directory.
E2E_RUNS_DIR := REPO2REE_TEST_RUN_DIR + "/e2e"

# The newest recording any e2e run left, or the one given; never empty.
[private]
_recording recording:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n {{ quote(recording) }} ]]; then printf '%s\n' {{ quote(recording) }}; exit 0; fi
    latest=$(ls -td {{ quote(E2E_RUNS_DIR) }}/*/tests/*/recording/manifest.json 2>/dev/null | head -n 1 || true)
    [[ -n "$latest" ]] || { echo "no recording under {{ E2E_RUNS_DIR }}; run an e2e suite (just demo-gui)" >&2; exit 2; }
    dirname "$latest"

# Where a recording's report and views go: beside it in its run's test directory, as the gate writes them;
# for a recording collected elsewhere (collect-behaviour), under the assurance directory by its name.
[private]
_beside recording kind:
    #!/usr/bin/env bash
    set -euo pipefail
    parent=$(dirname {{ quote(recording) }})
    if [[ -f "$parent/test.json" ]]; then printf '%s\n' "$parent/{{ kind }}"; exit 0; fi
    printf '%s\n' {{ quote(ASSURANCE_DIR) }}/{{ kind }}/"$(basename {{ quote(recording) }})"

# Judge a collected recording against the behaviour specification, apart from the run that collected it.
# Exit 0 passed, 1 violated, 2 inconclusive. The report goes beside, never into, the recording.
[group('Assurance')]
check-behaviour recording="" output="":
    #!/usr/bin/env bash
    set -euo pipefail
    recording=$(just _recording {{ quote(recording) }})
    output={{ quote(output) }}
    output=${output:-$(just _beside "$recording" verification)}
    python -m repo2ree_conformance check --recording "$recording" -o "$output"

# The verification check-behaviour wrote for a recording (the newest by default); drawing never verifies.
[private]
_verification recording:
    #!/usr/bin/env bash
    set -euo pipefail
    recording=$(just _recording {{ quote(recording) }})
    verification=$(just _beside "$recording" verification)
    [[ -f "$verification/verification.json" ]] || { echo "no verification of $recording; run: just check-behaviour $recording" >&2; exit 2; }
    printf '%s\n' "$verification"

# Draw one operation trace page per REE of a verified recording: setup, operations across components, rules triggered.
[group('Assurance')]
trace-behaviour recording="" output="":
    #!/usr/bin/env bash
    set -euo pipefail
    recording=$(just _recording {{ quote(recording) }})
    output={{ quote(output) }}
    output=${output:-$(just _beside "$recording" traces)}
    python -m repo2ree_traceview "$(just _verification "$recording")" -o "$output"

# Print why a verified recording's sealed REE can be trusted: each step's evidence back to its request.
[group('Assurance')]
provenance-behaviour recording="":
    python -m repo2ree_traceview "$(just _verification {{ quote(recording) }})" --provenance

[group('Assurance')]
generate-assurance-metrics:
    mkdir -p {{ quote(METRICS_DIR + "/assurance") }}
    lizard -l python -i -1 -o {{ quote(METRICS_DIR + "/assurance/complexity.html") }} {{ ASSURANCE_METRIC_PATHS }}
    lizard -l python -i -1 --csv {{ ASSURANCE_METRIC_PATHS }} > {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
    python -m repo2ree_repoview stamp --manifest {{ quote(METRICS_DIR + "/manifest.json") }} --by generate-assurance-metrics {{ quote(METRICS_DIR + "/assurance/complexity.html") }} {{ quote(METRICS_DIR + "/assurance/complexity.csv") }}
