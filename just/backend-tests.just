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
test-protocol:
    pytest protocol/tests

# Run core unit tests without recording tier coverage.
[group('Backend tests')]
test-core-unit:
    pytest core/tests/unit

# Run API unit tests without recording tier coverage.
[group('Backend tests')]
test-api-unit:
    pytest api/tests/unit

# Run executor tests without recording tier coverage.
[group('Backend tests')]
test-executor:
    pytest executor/tests

# Run workbench tests without recording tier coverage.
[group('Backend tests')]
test-workbench:
    pytest workbench/tests

# Run Docker support tests without recording tier coverage.
[group('Backend tests')]
test-docker-support:
    pytest docker-support/tests

# Run Docker provider tests without recording tier coverage.
[group('Backend tests')]
test-provider:
    pytest provider/tests

# Run supervisor unit tests without recording tier coverage.
[group('Backend tests')]
test-supervisor-unit:
    pytest supervisor/tests/unit

# Run core integration tests without recording tier coverage.
[group('Backend tests')]
test-core-integration:
    pytest core/tests/integration

# Run API integration tests without recording tier coverage.
[group('Backend tests')]
test-api-integration:
    pytest api/tests/integration

# Run supervisor integration tests without recording tier coverage.
[group('Backend tests')]
test-supervisor-integration:
    pytest supervisor/tests/integration

# Run all core unit and integration tests.
[group('Backend tests')]
test-core: test-core-unit test-core-integration

# Run all API unit and integration tests.
[group('Backend tests')]
test-api: test-api-unit test-api-integration

# Run all supervisor unit and integration tests.
[group('Backend tests')]
test-supervisor: test-supervisor-unit test-supervisor-integration

# Run the complete measured, container-free backend unit tier.
[group('Backend tests')]
test-backend-unit coverage_report="":
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/unit/.coverage") }} pytest {{ UNIT_SUITES }} --cov --cov-report={{ quote(coverage_report) }}

# Run the complete measured backend integration tier.
[group('Backend tests')]
test-backend-integration coverage_report="": build-e2e-bundles
    COVERAGE_FILE={{ quote(ROOT + "/" + COVERAGE_DATA + "/integration/.coverage") }} pytest {{ INTEGRATION_SUITES }} --cov --cov-report={{ quote(coverage_report) }}

# Run both measured backend tiers concurrently.
[group('Backend tests')]
[parallel]
test-backend coverage_report="": (test-backend-unit coverage_report) (test-backend-integration coverage_report)

# Render one measured tier's total and per-package HTML coverage reports.
[group('Coverage')]
report-backend-coverage tier:
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

# Combine whichever measured backend tiers exist on this checkout.
[group('Coverage')]
combine-backend-coverage:
    python scripts/coverage/python_coverage.py combine
