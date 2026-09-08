COVERAGE_HTML := "test-artifacts/coverage/python"
COVERAGE_DATA := COVERAGE_HTML + "/data"
UNIT_COVERAGE_PARTS := COVERAGE_DATA + "/unit-parts"
INTEGRATION_COVERAGE_PARTS := COVERAGE_DATA + "/integration-parts"
UNIT_SUITES := "protocol/tests core/tests/unit api/tests/unit supervisor/tests/unit executor/tests docker-support/tests provider/tests workbench/tests"
INTEGRATION_SUITES := "core/tests/integration api/tests/integration supervisor/tests/integration"

# Each package recipe writes an isolated coverage data file. The tier aggregates
# explicitly require and combine every part, so an incomplete run cannot be
# mistaken for a complete tier. Stack tiers similarly use parallel coverage
# files (server plus workbenches), which the stack driver folds into the same
# single-file shape before rendering. Combined reports use --keep so their
# inputs remain available for regenerating individual tier reports.

# Run protocol tests and record their unit coverage contribution.
[group('Backend tests')]
test-protocol:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/protocol") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/protocol/.coverage") }} pytest protocol/tests --cov --cov-report=

# Run core unit tests and record their unit coverage contribution.
[group('Backend tests')]
test-core-unit:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/core") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/core/.coverage") }} pytest core/tests/unit --cov --cov-report=

# Run API unit tests and record their unit coverage contribution.
[group('Backend tests')]
test-api-unit:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/api") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/api/.coverage") }} pytest api/tests/unit --cov --cov-report=

# Run executor tests and record their unit coverage contribution.
[group('Backend tests')]
test-executor:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/executor") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/executor/.coverage") }} pytest executor/tests --cov --cov-report=

# Run workbench tests and record their unit coverage contribution.
[group('Backend tests')]
test-workbench:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/workbench") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/workbench/.coverage") }} pytest workbench/tests --cov --cov-report=

# Run Docker support tests and record their unit coverage contribution.
[group('Backend tests')]
test-docker-support:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/docker-support") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/docker-support/.coverage") }} pytest docker-support/tests --cov --cov-report=

# Run Docker provider tests and record their unit coverage contribution.
[group('Backend tests')]
test-provider:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/provider") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/provider/.coverage") }} pytest provider/tests --cov --cov-report=

# Run supervisor unit tests and record their unit coverage contribution.
[group('Backend tests')]
test-supervisor-unit:
    mkdir -p {{ quote(UNIT_COVERAGE_PARTS + "/supervisor") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + UNIT_COVERAGE_PARTS + "/supervisor/.coverage") }} pytest supervisor/tests/unit --cov --cov-report=

# Run core integration tests and record their integration coverage contribution.
[group('Backend tests')]
test-core-integration coverage_report="":
    mkdir -p {{ quote(INTEGRATION_COVERAGE_PARTS + "/core") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + INTEGRATION_COVERAGE_PARTS + "/core/.coverage") }} pytest core/tests/integration --cov --cov-report={{ quote(coverage_report) }}

# Run API integration tests and record their integration coverage contribution.
[group('Backend tests')]
test-api-integration coverage_report="":
    mkdir -p {{ quote(INTEGRATION_COVERAGE_PARTS + "/api") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + INTEGRATION_COVERAGE_PARTS + "/api/.coverage") }} pytest api/tests/integration --cov --cov-report={{ quote(coverage_report) }}

# Run supervisor integration tests and record their integration coverage contribution.
[group('Backend tests')]
test-supervisor-integration coverage_report="":
    mkdir -p {{ quote(INTEGRATION_COVERAGE_PARTS + "/supervisor") }}
    rm -f {{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }}
    COVERAGE_FILE={{ quote(ROOT + "/" + INTEGRATION_COVERAGE_PARTS + "/supervisor/.coverage") }} pytest supervisor/tests/integration --cov --cov-report={{ quote(coverage_report) }}

# Run all core unit and integration tests.
[group('Backend tests')]
test-core: test-core-unit test-core-integration

# Run all API unit and integration tests.
[group('Backend tests')]
test-api: test-api-unit test-api-integration

# Run all supervisor unit and integration tests.
[group('Backend tests')]
test-supervisor: test-supervisor-unit test-supervisor-integration

# Run and merge the complete measured, container-free backend unit tier.
[group('Backend tests')]
test-backend-unit: test-protocol test-core-unit test-api-unit test-supervisor-unit test-executor test-docker-support test-provider test-workbench
    python scripts/coverage/python_coverage.py combine-unit

# Run and merge the complete measured backend integration tier.
[group('Backend tests')]
test-backend-integration coverage_report="": build-e2e-bundles (test-core-integration coverage_report) (test-api-integration coverage_report) (test-supervisor-integration coverage_report)
    python scripts/coverage/python_coverage.py combine-integration

# Run both measured backend tiers concurrently.
[group('Backend tests')]
[parallel]
test-backend: test-backend-unit test-backend-integration && (combine-backend-coverage "unit,integration")

# Render one measured tier's total and per-package HTML coverage reports.
[group('Coverage')]
render-backend-coverage tier:
    python scripts/coverage/python_coverage.py render {{ quote(tier) }}

# This is a separate view, not another tier: contexts make the database larger,
# and API unit and integration tests remain separate processes because their
# OpenTelemetry providers cannot safely share one interpreter.
# Generate per-test coverage attribution over both pytest tiers.
[group('Coverage')]
attribute-backend-coverage: build-e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-append --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} coverage html --show-contexts -d '{{ COVERAGE_HTML }}/context'
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} coverage report

# Combine selected measured backend tiers, or every available tier by default.
[group('Coverage')]
combine-backend-coverage tiers="": && (render-backend-coverage "combined")
    python scripts/coverage/python_coverage.py combine --tiers {{ quote(tiers) }}
