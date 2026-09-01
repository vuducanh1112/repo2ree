COVERAGE_DATA := "test-artifacts/coverage/python/data"
COVERAGE_HTML := "test-artifacts/coverage/python"
COVERAGE_TIERS := "unit integration e2e-gui e2e-gui-review demo-gui demo-api demo-gui-code-ocean"
COVERAGE_PACKAGES := "protocol core supervisor api executor agent"
UNIT_SUITES := "protocol/tests core/tests/unit api/tests/unit supervisor/tests/unit executor/tests agent/tests"
INTEGRATION_SUITES := "core/tests/integration api/tests/integration supervisor/tests/integration"

# Run protocol tests without recording tier coverage.
[group('Backend tests')]
protocol-tests:
    pytest protocol/tests

# Run core unit tests without recording tier coverage.
[group('Backend tests')]
core-unit-tests:
    pytest core/tests/unit

# Run API unit tests without recording tier coverage.
[group('Backend tests')]
api-unit-tests:
    pytest api/tests/unit

# Run executor tests without recording tier coverage.
[group('Backend tests')]
executor-tests:
    pytest executor/tests

# Run agent tests without recording tier coverage.
[group('Backend tests')]
agent-tests:
    pytest agent/tests

# Run supervisor unit tests without recording tier coverage.
[group('Backend tests')]
supervisor-unit-tests:
    pytest supervisor/tests/unit

# Run core integration tests without recording tier coverage.
[group('Backend tests')]
core-integration-tests:
    pytest core/tests/integration

# Run API integration tests without recording tier coverage.
[group('Backend tests')]
api-integration-tests:
    pytest api/tests/integration

# Run supervisor integration tests without recording tier coverage.
[group('Backend tests')]
supervisor-integration-tests:
    pytest supervisor/tests/integration

# Run all core unit and integration tests.
[group('Backend tests')]
core-tests: core-unit-tests core-integration-tests

# Run all API unit and integration tests.
[group('Backend tests')]
api-tests: api-unit-tests api-integration-tests

# Run all supervisor unit and integration tests.
[group('Backend tests')]
supervisor-tests: supervisor-unit-tests supervisor-integration-tests

# Run the complete measured, container-free backend unit tier.
[group('Backend tests')]
be-unit-tests COV_REPORT=env("COV_REPORT", ""):
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-report={{ quote(COV_REPORT) }}

# Run the complete measured backend integration tier.
[group('Backend tests')]
be-integration-tests COV_REPORT=env("COV_REPORT", ""): e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-report={{ quote(COV_REPORT) }}

# Run both measured backend tiers.
[group('Backend tests')]
be-tests: be-unit-tests be-integration-tests

# Render one measured tier's total and per-package HTML coverage reports.
[group('Coverage')]
be-coverage-report TIER=env("TIER", ""):
    #!/usr/bin/env bash
    set -euo pipefail
    tier={{ quote(TIER) }}
    test -n "$tier" || { echo "TIER is required — run: just be-coverage-report <tier>" >&2; exit 2; }
    data='{{ COVERAGE_DATA }}/'"$tier/.coverage"
    test -f "$data" || {
      echo "no coverage data for the $tier tier — run it first: one of {{ COVERAGE_TIERS }}" >&2
      exit 1
    }
    coverage_file={{ quote(ROOT + "/") }}"$data"
    COVERAGE_FILE="$coverage_file" coverage html -d '{{ COVERAGE_HTML }}/'"$tier" --title "repo2ree — $tier tier, python" >/dev/null
    echo ">> $tier tier, by module"
    for package in {{ COVERAGE_PACKAGES }}; do
      COVERAGE_FILE="$coverage_file" coverage html --include="$package/src/*" \
        -d '{{ COVERAGE_HTML }}/'"$tier/by-module/$package" \
        --title "repo2ree — $package ($tier tier, python)" >/dev/null
      printf '   %-12s %s%%\n' "$package" "$(COVERAGE_FILE="$coverage_file" coverage report --include="$package/src/*" --format=total)"
    done
    printf '   %-12s %s%%\n' TOTAL "$(COVERAGE_FILE="$coverage_file" coverage report --format=total)"
    echo ">> $tier reports: {{ COVERAGE_HTML }}/$tier (by module: .../by-module/<package>)"

# Generate per-test coverage attribution over both pytest tiers.
[group('Coverage')]
be-coverage-context: e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/context/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/context/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-append --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/context/.coverage") }} coverage html --show-contexts -d '{{ COVERAGE_HTML }}/context'
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/context/.coverage") }} coverage report

# Combine whichever measured backend tiers exist on this checkout.
[group('Coverage')]
be-coverage-combined:
    #!/usr/bin/env bash
    set -euo pipefail
    files=()
    included=()
    missing=()
    for tier in {{ COVERAGE_TIERS }}; do
      shopt -s nullglob
      found=('{{ COVERAGE_DATA }}'/"$tier"/.coverage*)
      if (( ${#found[@]} )); then
        files+=("${found[@]}")
        included+=("$tier")
      else
        missing+=("$tier")
      fi
    done
    (( ${#files[@]} )) || { echo "no tier has been measured; run e.g. 'just be-unit-tests' first"; exit 1; }
    echo ">> combined: ${included[*]}"
    (( ${#missing[@]} == 0 )) || echo ">> NOT included (never measured on this tree): ${missing[*]}"
    combined_dir='{{ COVERAGE_DATA }}/combined'
    rm -rf "$combined_dir"
    mkdir -p "$combined_dir"
    coverage_file={{ quote(ROOT + "/") }}"$combined_dir/.coverage"
    COVERAGE_FILE="$coverage_file" coverage combine --keep "${files[@]}"
    COVERAGE_FILE="$coverage_file" coverage report
    COVERAGE_FILE="$coverage_file" coverage html -d '{{ COVERAGE_HTML }}/combined' --title 'repo2ree — combined tier, python' >/dev/null
    echo ">> combined tier, by module"
    for package in {{ COVERAGE_PACKAGES }}; do
      COVERAGE_FILE="$coverage_file" coverage html --include="$package/src/*" \
        -d '{{ COVERAGE_HTML }}/combined/by-module/'"$package" \
        --title "repo2ree — $package (combined tier, python)" >/dev/null
      printf '   %-12s %s%%\n' "$package" "$(COVERAGE_FILE="$coverage_file" coverage report --include="$package/src/*" --format=total)"
    done
    printf '   %-12s %s%%\n' TOTAL "$(COVERAGE_FILE="$coverage_file" coverage report --format=total)"
    echo ">> combined reports: {{ COVERAGE_HTML }}/combined (by module: .../by-module/<package>)"
