# GUI test suites: the vitest tier and the two browser suites that need nothing
# but a vite dev server.
#
# The line against mk/e2e.mk is what a suite has to bring up, not which language
# it exercises. Everything here starts Vite and mocks the API boundary, so it
# runs on any machine, container-free and in seconds; the browser suites in
# mk/e2e.mk provision a real backend, agent, and workbench container. Backend
# suites and the python coverage plumbing are in mk/be-tests.mk. The rationale
# for the tier scheme and the runtime-above-tier artifact layout lives in
# docs/engineering/how-to/testing.md, not here.

.PHONY: gui-tests gui-accessibility-tests gui-screenshot-tests \
	gui-screenshot-baselines

# Always measured, like the backend tiers: this suite *is* the node tier. Vitest
# writes its report inline (reportsDirectory in gui/vite.config.mjs), so there is
# no separate render step to match the python side's.
# Component and pure-logic tests contribute to this report. The Playwright
# suites deliberately record no JavaScript coverage; see
# docs/engineering/how-to/testing.md.
gui-tests:
	@echo "Running GUI unit tests..."
	cd gui && npx vitest run --coverage.enabled
	@echo ">> node/unit report: test-artifacts/coverage/node/unit/index.html"

# Page-level accessibility and screenshot regression with deterministic API
# fixtures. These start only Vite: the browser renders the real routed
# application while Playwright mocks the slow backend boundary.
gui-accessibility-tests:
	cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-accessibility-tests

gui-screenshot-tests:
	cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests

# Redraw every baseline against the current renderer. Not a test target: it
# makes the suite green by definition, so it is only ever correct when the
# renderer moved (aa-renderer.spec.ts says so by name) or when a visual change
# is intended and reviewed in the resulting PNG diff.
gui-screenshot-baselines:
	cd gui && npm exec -- playwright test -c playwright.config.ts \
		--project=gui-screenshot-tests --update-snapshots
