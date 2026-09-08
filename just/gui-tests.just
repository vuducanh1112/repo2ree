# Run GUI unit tests with coverage.
[group('GUI tests')]
test-gui:
    @echo "Running GUI unit tests..."
    cd gui && npx vitest run --coverage.enabled
    @echo ">> node/unit report: test-artifacts/coverage/node/unit/index.html"

# Run browser-rendered accessibility checks against deterministic fixtures.
[group('GUI tests')]
test-gui-accessibility:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-accessibility-tests

# Run GUI screenshot regression tests.
[group('GUI tests')]
test-gui-screenshots:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests

# Update intentional GUI screenshot baselines.
[group('GUI tests')]
update-gui-screenshot-baselines:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests --update-snapshots
