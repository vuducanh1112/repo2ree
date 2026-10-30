# Run GUI unit tests with coverage.
[group('GUI tests')]
test-gui:
    @echo "Running GUI unit tests..."
    cd gui && npx vitest run --coverage.enabled
    @echo ">> node/unit report: {{REPO2REE_TEST_RUN_DIR}}/node/coverage/unit/index.html"

# Run browser-rendered accessibility checks against deterministic fixtures.
[group('GUI tests')]
test-gui-accessibility:
    python -m repo2ree_testbed record --tier gui-accessibility -- sh -c 'cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-accessibility-tests'
    python -m scripts.gates.tiers certify --tier gui-accessibility --if-eligible

# Run GUI screenshot regression tests.
[group('GUI tests')]
test-gui-screenshots:
    python -m repo2ree_testbed record --tier gui-screenshots -- sh -c 'cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests'
    python -m scripts.gates.tiers certify --tier gui-screenshots --if-eligible

# Update intentional GUI screenshot baselines.
[group('GUI tests')]
update-gui-screenshot-baselines:
    cd gui && npm exec -- playwright test -c playwright.config.ts --project=gui-screenshot-tests --update-snapshots
