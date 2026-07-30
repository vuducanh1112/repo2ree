# Unit/integration test suites and their coverage variants. The e2e suite
# lives in mk/e2e.mk.

.PHONY: gui-tests gui-coverage-unit \
	be-tests be-unit-tests be-integration-tests \
	protocol-tests core-tests core-unit-tests core-integration-tests \
	supervisor-tests supervisor-unit-tests supervisor-integration-tests \
	api-tests api-unit-tests api-integration-tests executor-tests agent-tests \
	be-coverage-unit be-coverage-integration be-coverage-context be-coverage-combined be-coverage-report

# ================================================
# GUI — tests
# ================================================

gui-tests:
	@echo "Running GUI unit tests..."
	cd gui && npx vitest run

# The GUI's own coverage, from the vitest suite — the `node` runtime, because
# these 57 files are pure logic with no component rendering. Reports into
# test-artifacts/coverage/node/unit/, sibling to the browser V8 reports the
# stack tiers write; the whole coverage config lives in gui/vite.config.js.
#
# Reads low by design: the React shell is barely imported here, and the browser
# tier is what covers it. The two are never added together — see the runtime map
# in the coverage section below.
gui-coverage-unit:
	@echo "Running GUI unit coverage..."
	cd gui && npx vitest run --coverage.enabled
	@echo ">> node/unit report: test-artifacts/coverage/node/unit/index.html"

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

supervisor-unit-tests:
	pytest supervisor/tests/unit

be-unit-tests: protocol-tests core-unit-tests api-unit-tests supervisor-unit-tests executor-tests agent-tests

# Integration tests — flows spanning multiple components.
core-integration-tests:
	pytest core/tests/integration

# Real-component API tier: the actual FastAPI app over HTTP against real
# workbench containers (pinned dind + injected bundles). Skips when docker or
# the bundles are absent (build with `make e2e-bundles`). Spans land
# in test-artifacts/traces/api-integration/traces.ndjson for post-run inspection.
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

supervisor-tests: supervisor-unit-tests supervisor-integration-tests

be-tests: be-unit-tests be-integration-tests

# ================================================
# Coverage — one report per tier, plus the union
# ================================================
#
# Four measured tiers:
#
#   unit         container-free single-component suites  (mk/tests.mk)
#   integration  flows spanning components, mostly docker-gated (mk/tests.mk)
#   e2e          the live stack, browser-driven           (mk/e2e.mk)
#   demo         the narrated/demonstration runs          (mk/e2e.mk)
#
# Not every way this project is tested is a tier: `e2e-review`,
# `e2e-demo-code-ocean` and the `e2e-api` walkthrough have no tier of their own
# — e2e-stack.sh accepts only e2e and demo for --coverage — so the reviewer-side
# lifecycle is exercised by push-gate but measured by nothing.
#
# Each tier owns a directory — data under
# test-artifacts/coverage/python/data/<tier>/, HTML under
# test-artifacts/coverage/python/<tier>/ — so a tier's number always means "what
# this way of testing reaches", never a blend. `be-coverage-combined` unions
# them. Per-tier *directories* rather than per-tier
# `.coverage.<tier>` files is deliberate: see the data_file comment in
# pyproject.toml.
#
# The `python/` level is what keeps `combined` meaningful. Runtime sits *above*
# tier under test-artifacts/coverage/, one subtree per measuring tool:
#
#   coverage/python/    coverage.py, the six uv packages (`be-coverage-*`)
#   coverage/browser/   monocart over browser V8      (`coverage-e2e`/`-demo`)
#   coverage/node/      istanbul via vitest         (`make gui-coverage-unit`)
#
# The `be-`/`gui-` prefixes follow the runtime, matching the rest of the
# Makefile (`be-tests`, `gui-tests`). The two stack targets — `coverage-e2e` and
# `coverage-demo` — carry no prefix precisely because one run measures both
# halves at once.
#
# Combining tiers is a *coverage.py operation* — `coverage combine`, over
# .coverage databases. Monocart has its own merge over its own captures. No
# algorithm unions a Python line count with a browser byte count and the two
# share no denominator, so each tool owns its own `combined/` inside its own
# subtree and there is deliberately no coverage/combined/ above them.
#
# Every tier is additionally broken down by source package into
# <tier>/by-module/<package>/ — filters over the tier's own data, so the
# breakdown costs no extra test run and exists for every tier (see
# coverage_render below, which every tier reports through).
#
# The `--cov` source list lives in pyproject.toml, so a bare `--cov` is all
# pytest needs.

COVERAGE_DATA = test-artifacts/coverage/python/data
COVERAGE_HTML = test-artifacts/coverage/python
# Every tier is measured through this: point COVERAGE_FILE at the tier's own
# data directory. Exported for the whole recipe line, subprocesses included.
tier_coverage = COVERAGE_FILE=$(CURDIR)/$(COVERAGE_DATA)/$(1)/.coverage

# The packages each tier is broken down by, mirroring the coverage source list
# in pyproject.toml. Listed rather than derived: the two change together about
# once a package, and a missing entry shows up as an absent line in the summary
# below rather than as a wrong number.
COVERAGE_PACKAGES = protocol core supervisor api executor agent

# coverage_render <tier>: the tier's HTML total, then one report per package
# filtered to that package's src/, then the summary line for each. Filters over
# the tier's own data, so this adds no test run and works for every tier —
# including the stack tiers, which are a single run and cannot be split by
# suite. Written as one shell command so the loop is one recipe line.
#
# Carries no `@`: be-coverage-combined splices this into the middle of its own
# shell chain, where a leading `@` is no longer make's silent-recipe prefix but
# a literal word the shell tries to run. Callers that start a recipe line with
# it add their own.
coverage_render = set -e; \
	[ -f $(COVERAGE_DATA)/$(1)/.coverage ] \
		|| { echo "no coverage data for the $(1) tier — measure it first:" \
			"be-coverage-unit, be-coverage-integration, coverage-e2e or coverage-demo" >&2; exit 1; }; \
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

# Render a tier that was measured elsewhere: scripts/e2e-stack.sh runs the stack
# under coverage and calls back here, so the stack tiers report identically to
# the pytest ones instead of growing their own variant.
be-coverage-report:
	@$(call coverage_render,$(TIER))

# The container-free tier: fast and deterministic, runs on any machine. It is a
# *subset* of what `commit-gate` requires green — the gate also runs gui-tests
# and core-integration-tests, the latter being container-free but living in the
# integration tier (see below). So a green gate implies a green unit tier, not
# the reverse.
#
# The docker-gated transport (supervisor manager, hbom profilers, the agent's
# docker runtime) is not exercised here, so it reads as uncovered — this number
# is a floor, not the truth. The integration tier below is where that floor gets
# lifted.
be-coverage-unit:
	$(call tier_coverage,unit) pytest protocol/tests core/tests/unit api/tests/unit supervisor/tests/unit executor/tests agent/tests \
		--cov --cov-report=term-missing
	@$(call coverage_render,unit)

# The multi-component tier: real containers, real docker exec, real workbench
# volumes. Mostly docker-gated, but not by definition — core/tests/integration
# drives the real command handlers against a temp REE tree and needs no docker,
# so it pays for the `e2e-bundles` prerequisite below without using it. The tier
# is "flows spanning components", and docker is what most of those flows happen
# to need.
#
# Builds the executor/tools bundles from the current tree first, so it
# cannot accidentally exercise a stale command protocol. Individual tests still
# skip (never fake) when Docker itself is absent — which makes an unguarded run
# of this target on a docker-less machine report a floor of its own, so treat a
# suspiciously low number here as "did it actually run" before "did coverage
# regress".
#
# One invocation, not two: the process split the single blended backend-coverage
# target used to need was only ever between the api *unit* and *integration*
# tiers (they collide on OpenTelemetry's set-once tracer provider — the tier
# conftests enforce it).
# Those now live in different tiers and different processes by construction, so
# the three integration suites share one.
be-coverage-integration: e2e-bundles
	$(call tier_coverage,integration) pytest core/tests/integration api/tests/integration supervisor/tests/integration \
		--cov --cov-report=term-missing
	@$(call coverage_render,integration)

# Per-test coverage over the two pytest tiers: each line is tagged with the test
# that executed it (--cov-context=test), and the HTML is built with
# `coverage html --show-contexts` so every source line lists which tests hit it
# (use the filter box in the report's index.html to narrow to one test).
# --show-contexts is kept on this target alone, so the plain tier reports stay
# uncluttered. Writes its own data dir rather than reusing the tiers': contexts
# make the database much larger, and a plain tier report should not pay for it.
be-coverage-context: e2e-bundles
	$(call tier_coverage,context) pytest protocol/tests core/tests api/tests/unit supervisor/tests/unit executor/tests agent/tests \
		--cov --cov-context=test --cov-report=
	$(call tier_coverage,context) pytest api/tests/integration supervisor/tests/integration \
		--cov --cov-append --cov-context=test --cov-report=
	$(call tier_coverage,context) coverage html --show-contexts -d $(COVERAGE_HTML)/context
	$(call tier_coverage,context) coverage report

# The union of whatever tiers have been measured on this checkout.
#
# --keep is load-bearing: without it `coverage combine` *deletes* the per-tier
# data it consumed, and the tier reports could never be regenerated without
# re-running the suites. Tiers that were never run are skipped rather than
# failing the target, so this is useful after any subset — but a combined
# number spans all four tiers only when all four ran on the same tree, which is
# what `push-gate` arranges, and never spans the suites with no tier of their
# own at all (see the tier map above). The tier list is deliberately not a
# prerequisite: combining is cheap, and re-running the e2e stack because
# someone asked for a union report is not.
#
# Inputs are named file-by-file, not by directory: `coverage combine <dir>`
# looks only for *suffixed* parallel-mode files (.coverage.<host>.<pid>) and
# silently reports "No data to combine" for a directory holding a plain
# .coverage — which is exactly what each tier writes. The glob covers both, so
# a tier that ran under --parallel-mode (e2e, demo: server + agents in separate
# processes) combines the same way as a single-process pytest tier.
be-coverage-combined:
	@set -e; files=""; \
	for tier in unit integration e2e demo; do \
		found=$$(ls $(COVERAGE_DATA)/$$tier/.coverage* 2>/dev/null || true); \
		if [ -n "$$found" ]; then files="$$files $$found"; \
		else echo "note: no coverage data for the $$tier tier — skipping"; fi; \
	done; \
	[ -n "$$files" ] || { echo "no tier has been measured; run e.g. 'make be-coverage-unit' first"; exit 1; }; \
	echo ">> combining:$$files"; \
	rm -rf $(COVERAGE_DATA)/combined; mkdir -p $(COVERAGE_DATA)/combined; \
	$(call tier_coverage,combined) coverage combine --keep $$files; \
	$(call tier_coverage,combined) coverage report; \
	$(call coverage_render,combined)
