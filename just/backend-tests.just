COVERAGE_HTML := REPO2REE_TEST_RUN_DIR + "/python/coverage"
COVERAGE_DATA := COVERAGE_HTML + "/data"
UNIT_COVERAGE_PARTS := COVERAGE_DATA + "/unit-parts"
INTEGRATION_COVERAGE_PARTS := COVERAGE_DATA + "/integration-parts"

# Each package writes an isolated coverage data file. The tier aggregates
# explicitly require and combine every part, so an incomplete run cannot be
# mistaken for a complete tier. Stack tiers similarly use parallel coverage
# files (server plus workbenches), which the stack driver folds into the same
# single-file shape before rendering. Combined reports use --keep so their
# inputs remain available for regenerating individual tier reports. The packages
# and their suites come from pyproject.toml (scripts/workspace.py).

# Run backend packages' unit suites, each into its own unit coverage part (e.g. `just test-unit-package core api`).
[group('Backend tests')]
test-unit-package +packages:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -f {{ quote(COVERAGE_DATA + "/unit/.coverage") }}
    for package in {{ packages }}; do
        mkdir -p {{ quote(UNIT_COVERAGE_PARTS) }}/"$package"
        COVERAGE_FILE={{ quote(UNIT_COVERAGE_PARTS) }}/"$package"/.coverage pytest $(python scripts/workspace.py suites unit "$package") --cov --cov-report=
    done

# Run backend packages' integration suites, each into its own integration coverage part; packages without one are skipped.
[group('Backend tests')]
test-integration-package +packages:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -f {{ quote(COVERAGE_DATA + "/integration/.coverage") }}
    for package in {{ packages }}; do
        suite=$(python scripts/workspace.py suites integration "$package")
        [[ -n "$suite" ]] || { echo ">> $package has no integration suite"; continue; }
        mkdir -p {{ quote(INTEGRATION_COVERAGE_PARTS) }}/"$package"
        COVERAGE_FILE={{ quote(INTEGRATION_COVERAGE_PARTS) }}/"$package"/.coverage pytest "$suite" --cov --cov-report=
    done

# Run and merge the complete measured, container-free backend unit tier.
[group('Backend tests')]
test-backend-unit: (test-unit-package `python scripts/workspace.py backend`)
    python -m repo2ree_testbed coverage combine-unit

# Run and merge the complete measured backend integration tier.
[group('Backend tests')]
test-backend-integration: build-e2e-bundles (test-integration-package `python scripts/workspace.py backend`)
    python -m repo2ree_testbed coverage combine-integration

# Run both measured backend tiers concurrently.
[group('Backend tests')]
[parallel]
test-backend: test-backend-unit test-backend-integration && (combine-backend-coverage "unit,integration")

# Render one measured tier's total and per-package HTML coverage reports.
[group('Coverage')]
render-backend-coverage tier run="":
    python -m repo2ree_testbed coverage render {{ quote(tier) }} {{ if run == "" { "" } else { "--run " + quote(run) } }}

# This is a separate view, not another tier: contexts make the database larger,
# and API unit and integration tests remain separate processes because their
# OpenTelemetry providers cannot safely share one interpreter.
# Generate per-test coverage attribution over both pytest tiers.
[group('Coverage')]
attribute-backend-coverage: build-e2e-bundles
    COVERAGE_FILE={{ quote(REPO2REE_TEST_RUN_DIR + "/python/coverage/data/context/.coverage") }} pytest $(python scripts/workspace.py suites unit) --cov --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(REPO2REE_TEST_RUN_DIR + "/python/coverage/data/context/.coverage") }} pytest $(python scripts/workspace.py suites integration) --cov --cov-append --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(REPO2REE_TEST_RUN_DIR + "/python/coverage/data/context/.coverage") }} coverage html --show-contexts -d '{{ COVERAGE_HTML }}/context'
    COVERAGE_FILE={{ quote(REPO2REE_TEST_RUN_DIR + "/python/coverage/data/context/.coverage") }} coverage report

# Combine selected measured backend tiers, or every available tier by default.
[group('Coverage')]
combine-backend-coverage tiers="" run="":
    python -m repo2ree_testbed coverage combine --tiers {{ quote(tiers) }} --render {{ if run == "" { "" } else { "--run " + quote(run) } }}
