# Run GUI unit tests with coverage.
[group('GUI tests')]
gui-tests:
    @echo "Running GUI unit tests..."
    cd gui && npx vitest run --coverage.enabled
    @echo ">> node/unit report: test-artifacts/coverage/node/unit/index.html"

# Run browser-rendered accessibility checks against deterministic fixtures.
[group('GUI tests')]
gui-accessibility-tests:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-accessibility-tests

# Run GUI screenshot regression tests.
[group('GUI tests')]
gui-screenshot-tests:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests

# Update intentional GUI screenshot baselines.
[group('GUI tests')]
gui-screenshot-baselines:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests --update-snapshots
