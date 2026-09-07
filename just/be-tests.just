COVERAGE_HTML := "test-artifacts/coverage/python"
COVERAGE_DATA := COVERAGE_HTML + "/data"
UNIT_SUITES := "protocol/tests core/tests/unit api/tests/unit supervisor/tests/unit executor/tests docker-support/tests provider/tests workbench/tests"
INTEGRATION_SUITES := "core/tests/integration api/tests/integration supervisor/tests/integration"

# Running a measured tier is the only operation that writes that tier's data.
# Per-package recipes stay unmeasured so a partial debugging run cannot make a
# tier report look complete. Stack tiers use parallel coverage files (server
# plus workbenches); the stack driver folds those into the same single-file shape as
# pytest tiers before rendering. Combined reports use --keep so their inputs
# remain available for regenerating individual tier reports.

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

# Run workbench tests without recording tier coverage.
[group('Backend tests')]
workbench-tests:
    pytest workbench/tests

# Run Docker support tests without recording tier coverage.
[group('Backend tests')]
docker-support-tests:
    pytest docker-support/tests

# Run Docker provider tests without recording tier coverage.
[group('Backend tests')]
provider-tests:
    pytest provider/tests

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
be-unit-tests coverage_report="":
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-report={{ quote(coverage_report) }}

# Run the complete measured backend integration tier.
[group('Backend tests')]
be-integration-tests coverage_report="": e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-report={{ quote(coverage_report) }}

# Run both measured backend tiers concurrently.
[group('Backend tests')]
[parallel]
be-tests coverage_report="": (be-unit-tests coverage_report) (be-integration-tests coverage_report)

# Render one measured tier's total and per-package HTML coverage reports.
[group('Coverage')]
be-coverage-report tier:
    scripts/coverage/python-coverage.sh render {{ quote(tier) }}

# This is a separate view, not another tier: contexts make the database larger,
# and API unit and integration tests remain separate processes because their
# OpenTelemetry providers cannot safely share one interpreter.
# Generate per-test coverage attribution over both pytest tiers.
[group('Coverage')]
be-coverage-context: e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-append --cov-context=test --cov-report=
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} coverage html --show-contexts -d '{{ COVERAGE_HTML }}/context'
    COVERAGE_FILE={{ quote(ROOT + "/test-artifacts/coverage/python/data/context/.coverage") }} coverage report

# Combine whichever measured backend tiers exist on this checkout.
[group('Coverage')]
be-coverage-combined:
    scripts/coverage/python-coverage.sh combine
