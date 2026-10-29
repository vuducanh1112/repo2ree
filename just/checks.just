# Static checks
#
# Checks below are read-only. Run `just format` to apply formatting, or
# `just fix` to apply safe lint fixes and then format the affected sources.
# The Python packages come from pyproject.toml (scripts/workspace.py), so a
# package added there is formatted, checked, and tested without a recipe of its own.

GUI_FORMAT_PATHS := "src tests scripts playwright.config.ts vite.config.mjs testArtifacts.cjs testArtifacts.d.cts"

[private]
_check-write-hint:
    @echo ">> checks are read-only; run 'just format' to format or 'just fix' to apply safe fixes"

# Apply Python, GUI, and Nix formatting.
[group('Formatting')]
format:
    ruff format scripts $(python scripts/workspace.py members) conftest.py
    cd gui && npx biome format --write {{ GUI_FORMAT_PATHS }}
    nix fmt

# Apply safe Python and GUI lint fixes, then normalize formatting.
[group('Formatting')]
fix: && format
    ruff check --fix scripts $(python scripts/workspace.py members) conftest.py
    cd gui && npx biome check --write {{ GUI_FORMAT_PATHS }}

# Run tests for repository scripts.
[group('Script tests')]
test-scripts:
    pytest scripts/tests

# Statically check shell and Python scripts.
[group('Checks')]
check-scripts: _check-write-hint check-config
    @echo "Running shellcheck..."
    find scripts -name '*.sh' -exec shellcheck {} +
    @echo "Checking python scripts..."
    ruff check scripts conftest.py
    ruff format --check scripts conftest.py
    mypy scripts
    mypy conftest.py

# Check formatting and lint Nix sources without modifying them.
[group('Checks')]
check-nix: _check-write-hint
    @echo "Checking Nix formatting..."
    git ls-files -z --cached --others --exclude-standard -- '*.nix' | xargs -0 -r nixfmt --check
    @echo "Running statix..."
    statix check .
    @echo "Running deadnix..."
    git ls-files -z --cached --others --exclude-standard -- '*.nix' | xargs -0 -r deadnix --fail

# Run all GUI static checks.
[group('Checks')]
check-gui: _check-write-hint check-api-types
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Running GUI checks..."
    cd gui
    echo "Running TypeScript compiler (app)..."
    npx tsc -p tsconfig.app.json
    echo "Running TypeScript compiler (e2e)..."
    npx tsc -p tsconfig.e2e.json
    echo "Running Biome..."
    npx biome check {{ GUI_FORMAT_PATHS }}
    echo "Running knip..."
    npx knip
    echo "Checking functional-core effects..."
    npm run check:core-purity
    echo "Checking style architecture..."
    npm run check:style-architecture
    echo "Running dependency-cruiser..."
    npx depcruise src tests

# Generate GUI API types into a temporary file and require the checked-in file
# to be current. Comparing content rather than against HEAD also works while an
# API migration is intentionally uncommitted, without modifying the worktree.
[group('Checks')]
check-api-types: _check-write-hint
    #!/usr/bin/env bash
    set -euo pipefail
    generated={{ quote(ROOT + "/gui/src/shell/infra/api/generated/openapi.ts") }}
    candidate=$(mktemp)
    trap 'rm -f "$candidate"' EXIT
    cd gui
    npx openapi-typescript ../contracts/openapi.json -o "$candidate"
    diff -u "$generated" "$candidate"

# A package with import contracts of its own declares them in its pyproject.toml: the
# testbed and the views read what they test as processes and exports, the assurance
# packages stay independent of the product they judge.
# Static checks for workspace packages (e.g. `just check-package core assurance/checker`): ruff, mypy, and its own import contracts.
[group('Checks')]
check-package +packages: _check-write-hint
    #!/usr/bin/env bash
    set -euo pipefail
    for package in {{ packages }}; do
        echo "Running $package checks..."
        paths=("$package/src")
        if [[ -d "$package/tests" ]]; then paths+=("$package/tests"); fi
        ruff check "${paths[@]}"
        ruff format --check "${paths[@]}"
        mypy "${paths[@]}"
        if grep -q '^\[tool\.importlinter\]' "$package/pyproject.toml"; then
            lint-imports --config "$package/pyproject.toml"
        fi
    done

# Check backend import-layer contracts.
[group('Checks')]
check-architecture: _check-write-hint
    @echo "Running import-linter..."
    lint-imports

# Run static checks for backend packages.
[group('Checks')]
check-backend: (check-package `python scripts/workspace.py backend`) check-architecture

# Static checks for the testbed and the repository views.
[group('Checks')]
check-tooling: (check-package `python scripts/workspace.py tooling`)

# Tests for the testbed and the repository views.
[group('Script tests')]
test-tooling:
    for package in $(python scripts/workspace.py tooling); do pytest "$package/tests"; done

# Run every static analysis check.
[group('Checks')]
check: check-docs check-scripts check-nix check-gui check-backend check-assurance check-tooling

# Run every container-free unit test suite.
[group('Tests')]
[parallel]
test-unit: test-scripts test-gui test-backend-unit test-assurance test-tooling
