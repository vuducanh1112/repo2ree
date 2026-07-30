# Test suites and the coverage they produce. Running a tier *is* measuring it,
# so there is one definition of each tier rather than a "run" target and a
# "measure" target that can disagree. The e2e/demo tiers live in mk/e2e.mk; the
# rationale for the tier scheme and the runtime-above-tier artifact layout lives
# in docs/engineering/testing.md, not here.

.PHONY: gui-tests \
	be-tests be-unit-tests be-integration-tests \
	protocol-tests core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-unit-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests agent-tests \
	be-coverage-context be-coverage-combined be-coverage-report

# ================================================
# Test tiers
# ================================================
#
# The one definition of each backend tier. The tier targets below run exactly
# these paths under coverage; nothing else enumerates them.

UNIT_SUITES = protocol/tests core/tests/unit api/tests/unit \
	supervisor/tests/unit executor/tests agent/tests

INTEGRATION_SUITES = core/tests/integration api/tests/integration \
	supervisor/tests/integration

# ================================================
# Coverage plumbing
# ================================================

COVERAGE_DATA = test-artifacts/coverage/python/data
COVERAGE_HTML = test-artifacts/coverage/python

# Point COVERAGE_FILE at a tier's own data directory. Exported for the whole
# recipe line, subprocesses included.
tier_coverage = COVERAGE_FILE=$(CURDIR)/$(COVERAGE_DATA)/$(1)/.coverage

# Terminal report shape for a measured run. Empty by default: a tier run's job
# is to produce data, and the per-package summary belongs to the render step.
# `make be-unit-tests COV_REPORT=term-missing` when you are actively closing
# gaps.
COV_REPORT ?=

# The packages each tier is broken down by, mirroring the coverage source list
# in pyproject.toml. Listed rather than derived: the two change together about
# once a package, and a missing entry shows up as an absent line in the summary
# rather than as a wrong number.
COVERAGE_PACKAGES = protocol core supervisor api executor agent

# coverage_render <tier>: the tier's HTML total, then one report per package
# filtered to that package's src/, then the summary line for each. Filters over
# the tier's own data, so this adds no test run and works for every tier —
# including the stack tiers, which are a single run and cannot be split by suite.
#
# Carries no `@`: be-coverage-combined splices this into the middle of its own
# shell chain, where a leading `@` is no longer make's silent-recipe prefix but
# a literal word the shell tries to run. Callers that start a recipe line with
# it add their own.
coverage_render = set -e; \
	[ -f $(COVERAGE_DATA)/$(1)/.coverage ] \
		|| { echo "no coverage data for the $(1) tier — run it first:" \
			"be-unit-tests, be-integration-tests, coverage-e2e or coverage-demo" >&2; exit 1; }; \
	$(call tier_coverage,$(1)) coverage html -d $(COVERAGE_HTML)/$(1) \
		--title "repo2ree — $(1) tier, python" >/dev/null; \
	echo ">> $(1) tier, by module"; \
	for pkg in $(COVERAGE_PACKAGES); do \
		$(call tier_coverage,$(1)) coverage html --include="$$pkg/src/*" \
			-d $(COVERAGE_HTML)/$(1)/by-module/$$pkg --title "repo2ree — $$pkg ($(1) tier, python)" >/dev/null; \
		printf '   %-12s %s%%\n' "$$pkg" \
			"$$($(call tier_coverage,$(1)) coverage report --include="$$pkg/src/*" --format=total)"; \
	done; \
	printf '   %-12s %s%%\n' TOTAL "$$($(call tier_coverage,$(1)) coverage report --format=total)"; \
	echo ">> $(1) reports: $(COVERAGE_HTML)/$(1) (by module: .../by-module/<package>)"

# ================================================
# GUI
# ================================================

# Always measured, like the backend tiers: this suite *is* the node tier. Vitest
# writes its report inline (reportsDirectory in gui/vite.config.js), so there is
# no separate render step to match the python side's.
#
# Reads ~23% by design — 57 files of pure logic, no component rendering, the
# React shell covered by the browser tier instead. See docs/engineering/testing.md.
gui-tests:
	@echo "Running GUI unit tests..."
	cd gui && npx vitest run --coverage.enabled
	@echo ">> node/unit report: test-artifacts/coverage/node/unit/index.html"

# ================================================
# Backend — per-package suites
# ================================================
#
# Bare and fast: this is the debugging loop. Deliberately unmeasured — a partial
# run writing a tier's data directory would make that tier's number mean "core,
# plus whatever else someone happened to run", which is the blend the tier split
# exists to prevent.

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

supervisor-unit-tests:
	pytest supervisor/tests/unit

# Real command handlers against a temp REE tree. No docker, despite belonging to
# the integration tier — the tier axis is scope, not infrastructure.
core-integration-tests:
	pytest core/tests/integration

# Real-component API tier: the actual FastAPI app over HTTP against real
# workbench containers (pinned dind + injected bundles). Skips when docker or
# the bundles are absent (build with `make e2e-bundles`). Spans land in
# test-artifacts/traces/api-integration/ for post-run inspection.
api-integration-tests:
	pytest api/tests/integration

# Real workbench e2e: provisions a container from the pinned dind bench with the
# executor/tools bundles injected, over the live docker exec transport. Skips
# when docker or the bundles are absent.
supervisor-integration-tests:
	pytest supervisor/tests/integration

core-tests: core-unit-tests core-integration-tests

api-tests: api-unit-tests api-integration-tests

supervisor-tests: supervisor-unit-tests supervisor-integration-tests

# ================================================
# Backend — tiers (measured)
# ================================================

# The container-free tier: fast, deterministic, runs on any machine. One pytest
# process over every unit suite, writing the unit tier's data directory.
#
# A strict subset of what `commit-gate` requires green — the gate also runs
# gui-tests and core-integration-tests — so a green gate implies a green unit
# tier, not the reverse.
#
# The docker-gated transport (supervisor manager, hbom profilers, the agent's
# docker runtime) is not exercised here, so it reads as uncovered: this number
# is a floor, not the truth. The integration tier is where that floor lifts.
be-unit-tests:
	$(call tier_coverage,unit) pytest $(UNIT_SUITES) --cov --cov-report=$(COV_REPORT)

# Flows spanning components — mostly docker-gated, though core/tests/integration
# needs no containers.
#
# Builds the executor/tools bundles first, so the tier cannot exercise a stale
# command protocol. That prerequisite used to sit on the coverage target alone,
# which meant a plain `make be-integration-tests` could run against bundles from
# an older tree; merging the two targets fixes that rather than inheriting it.
#
# Individual tests still skip (never fake) when docker is absent, so an
# unguarded run on a docker-less machine reports a floor of its own — treat a
# suspiciously low number here as "did it actually run" before "did coverage
# regress".
#
# One invocation, not two: the process split the old blended target needed was
# only ever between the api *unit* and *integration* suites (they collide on
# OpenTelemetry's set-once tracer provider — the tier conftests enforce it).
# Those now live in different tiers by construction.
be-integration-tests: e2e-bundles
	$(call tier_coverage,integration) pytest $(INTEGRATION_SUITES) --cov --cov-report=$(COV_REPORT)

be-tests: be-unit-tests be-integration-tests

# ================================================
# Reports
# ================================================

# Render a tier from data already on disk. scripts/e2e-stack.sh calls this after
# a measured stack run, so the stack tiers report identically to the pytest ones
# instead of growing their own variant.
be-coverage-report:
	@$(call coverage_render,$(TIER))

# Per-test attribution over the two pytest tiers: each line is tagged with the
# test that executed it (--cov-context=test), and the HTML lists which tests hit
# each source line (filter box in index.html narrows to one test).
#
# A different *view* over the same suites, not a fifth tier — never part of
# be-coverage-combined. Writes its own data dir: contexts make the database much
# larger, and a plain tier report should not pay for it. Two invocations,
# because the api unit and integration suites cannot share a process.
be-coverage-context: e2e-bundles
	$(call tier_coverage,context) pytest $(UNIT_SUITES) \
		--cov --cov-context=test --cov-report=
	$(call tier_coverage,context) pytest $(INTEGRATION_SUITES) \
		--cov --cov-append --cov-context=test --cov-report=
	$(call tier_coverage,context) coverage html --show-contexts -d $(COVERAGE_HTML)/context
	$(call tier_coverage,context) coverage report

# The union of whatever tiers have been measured on this checkout.
#
# --keep is load-bearing: without it `coverage combine` *deletes* the per-tier
# data it consumed, and the tier reports could never be regenerated without
# re-running the suites. Tiers that were never run are skipped rather than
# failing the target, so this is useful after any subset — but a combined number
# spans all four tiers only when all four ran on the same tree, which is what
# `push-gate` arranges, and never spans the suites with no tier of their own.
# The tier list is deliberately not a prerequisite: combining is cheap, and
# re-running the e2e stack because someone asked for a union report is not.
#
# Inputs are named file-by-file, not by directory: `coverage combine <dir>` looks
# only for *suffixed* parallel-mode files (.coverage.<host>.<pid>) and silently
# reports "No data to combine" for a directory holding a plain .coverage — which
# is exactly what each pytest tier writes. The glob covers both, so a tier that
# ran under --parallel-mode (e2e, demo: server + agents in separate processes)
# combines the same way as a single-process pytest tier.
be-coverage-combined:
	@set -e; files=""; \
	for tier in unit integration e2e demo; do \
		found=$$(ls $(COVERAGE_DATA)/$$tier/.coverage* 2>/dev/null || true); \
		if [ -n "$$found" ]; then files="$$files $$found"; \
		else echo "note: no coverage data for the $$tier tier — skipping"; fi; \
	done; \
	[ -n "$$files" ] || { echo "no tier has been measured; run e.g. 'make be-unit-tests' first"; exit 1; }; \
	echo ">> combining:$$files"; \
	rm -rf $(COVERAGE_DATA)/combined; mkdir -p $(COVERAGE_DATA)/combined; \
	$(call tier_coverage,combined) coverage combine --keep $$files; \
	$(call tier_coverage,combined) coverage report; \
	$(call coverage_render,combined)
