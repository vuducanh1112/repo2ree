# Unit/integration test suites and their coverage variants. The e2e suite
# lives in mk/e2e.mk.

.PHONY: fe-tests \
	be-tests be-unit-tests be-integration-tests \
	protocol-tests core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests agent-tests \
	be-coverage be-coverage-unit be-coverage-context

# ================================================
# Frontend — tests
# ================================================

fe-tests:
	@echo "Running frontend unit tests..."
	cd frontend && npx vitest run

# ================================================
# Backend - tests
# ================================================

# Unit tests — single-component, no external infra.
protocol-tests:
	pytest protocol/tests

core-unit-tests:
	pytest core/tests/unit

api-unit-tests:
	pytest api/tests/unit

executor-tests:
	pytest executor/tests

agent-tests:
	pytest agent/tests

be-unit-tests: protocol-tests core-unit-tests api-unit-tests executor-tests agent-tests

# Integration tests — flows spanning multiple components.
core-integration-tests:
	pytest core/tests/integration

# Real-component API tier: the actual FastAPI app over HTTP against real
# workbench containers (pinned dind + injected bundles). Skips when docker or
# the bundles are absent (build with `make e2e-bundles`). Spans land
# in test-results/api-integration/traces.ndjson for post-run inspection.
api-integration-tests:
	pytest api/tests/integration

# Real workbench e2e: provisions a container from the pinned dind bench with
# the executor/tools bundles injected, over the live docker exec transport.
# Skips when docker or the bundles are absent (build with `make e2e-bundles`).
supervisor-integration-tests:
	pytest supervisor/tests/integration

be-integration-tests: core-integration-tests api-integration-tests supervisor-integration-tests

# Per-package and full suites.
core-tests: core-unit-tests core-integration-tests

api-tests: api-unit-tests api-integration-tests

supervisor-tests: supervisor-integration-tests

be-tests: be-unit-tests be-integration-tests

# ================================================
# Backend - tests with coverage
# ================================================
#
# Reports land under test-artifacts/coverage/<variant>/ (one per target, so they
# never clobber each other); the .coverage data lives under
# test-artifacts/coverage/data (set in [tool.coverage.run] in pyproject.toml).
# The `--cov` source list also lives there, so a bare `--cov` is all pytest needs.

# Container-free tiers in one process: fast and deterministic, runs anywhere.
# Includes the agent unit tests (no docker) so the agent tier's own coverage is
# counted rather than reading 0% on files only its unit tests exercise. The
# Docker-gated transport (supervisor manager, hbom profilers) is not exercised,
# so it reads as uncovered — this number is a floor, not the truth.
be-coverage-unit:
	pytest protocol/tests core/tests/unit api/tests/unit executor/tests agent/tests core/tests/integration \
		--cov --cov-report=term-missing --cov-report=html:test-artifacts/coverage/unit

# Full suite: the honest number, but the integration tiers skip silently
# without docker + the executor/tools bundles (build with `make e2e-bundles`).
#
# Two invocations, not one: the api unit and integration tiers must run in
# separate processes (they collide on OpenTelemetry's set-once tracer provider
# — the tier conftests enforce this). The first run measures everything bar the
# api integration tier and writes .coverage fresh; the second appends the api
# integration tier and reports the combined total.
be-coverage:
	pytest protocol/tests core/tests api/tests/unit supervisor/tests executor/tests agent/tests \
		--cov --cov-report=
	pytest api/tests/integration \
		--cov --cov-append --cov-report=term-missing --cov-report=html:test-artifacts/coverage/full

# Per-test coverage: same two-process split as be-coverage, but each line is
# tagged with the test that executed it (--cov-context=test). The HTML report
# is built with `coverage html --show-contexts` so each source line lists which
# tests hit it (use the filter box in the report's index.html to narrow to one
# test). --show-contexts is kept on this target only, so the plain be-coverage
# report stays uncluttered.
be-coverage-context:
	pytest protocol/tests core/tests api/tests/unit supervisor/tests executor/tests agent/tests \
		--cov --cov-context=test --cov-report=
	pytest api/tests/integration \
		--cov --cov-append --cov-context=test --cov-report=
	coverage html --show-contexts -d test-artifacts/coverage/context
	coverage report
