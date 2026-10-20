# The behaviour gate and the tiers it runs. This file is oracle (specifications/zones.toml):
# what runs and how it is judged decide what a receipt certifies, so it changes apart
# from the product it judges.

[private]
_e2e-gui-instant jobs mode docker_mode:
    python scripts/test-stack/e2e_stack.py --project e2e-gui-instant --per-test --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations 1 --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

[private]
_e2e-system jobs locations mode docker_mode:
    python scripts/test-stack/e2e_stack.py --script {{ quote(ROOT + "/api/tests/system/run_system_suite.py") }} --tier e2e-system --per-test --jobs {{ quote(jobs) }} --mode {{ quote(mode) }} --compute-locations {{ quote(locations) }} --docker-mode {{ quote(docker_mode) }} --exec-bundle {{ quote(E2E_EXEC_BUNDLE) }} --tools-bundle {{ quote(E2E_TOOLS_BUNDLE) }}

# A test is accepted when it passed and its behaviour passed, or it is excused by
# conformance/expected-verdicts.toml (as every xfail must be) and left exactly those rules open.
# The suite together must reach every specified rule, edge, and message the same file does not excuse.
# Run the per-test e2e tiers on HEAD, judge every test's behaviour, and certify HEAD's tree.
[group('Release gates')]
behaviour-gate jobs=E2E_JOBS: _require-clean-tree build-e2e-bundles
    #!/usr/bin/env bash
    set -euo pipefail
    # Both tiers at once, each in a run directory of its own; each run is read from its tier's own output.
    logs=$(mktemp -d)
    just _e2e-system {{ quote(jobs) }} 1 {{ quote(DEFAULT_E2E_COMPUTE_LOCATION_MODE) }} {{ quote(DEFAULT_E2E_PROVIDER_DOCKER_MODE) }} > "$logs/system.log" 2>&1 &
    system=$!
    just _e2e-gui-instant {{ quote(jobs) }} {{ quote(DEFAULT_E2E_COMPUTE_LOCATION_MODE) }} {{ quote(DEFAULT_E2E_PROVIDER_DOCKER_MODE) }} > "$logs/gui.log" 2>&1 &
    gui=$!
    wait "$system" || true
    wait "$gui" || true
    runs=()
    for tier in system gui; do
        grep -E '^>> (\[|passed|failed|xfailed|skipped|per-test run)' "$logs/$tier.log" || true
        run=$(sed -n 's/^>> per-test run: //p' "$logs/$tier.log" | tail -n 1)
        [[ -n "$run" ]] || { tail -n 60 "$logs/$tier.log" >&2; echo ">> the $tier tier left no per-test run (log: $logs/$tier.log)" >&2; exit 1; }
        runs+=("$run")
    done
    python scripts/publish/behaviour_gate.py certify "${runs[@]}"

# Require a behaviour receipt for HEAD's clean tree.
[private]
_require-current-behaviour-receipt:
    python scripts/publish/behaviour_gate.py verify

# Judge per-test runs as the behaviour gate would (the newest of each tier by default), certifying nothing.
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
    python scripts/publish/behaviour_gate.py judge $runs

# With paths, name the zone of each; `--files oracle[.group]` lists a zone's files.
# Draw which parts of the repository are oracle (humans review), product (the gate judges), and support.
[group('Behaviour')]
show-oracle *args:
    python scripts/oracle.py show {{ args }}
