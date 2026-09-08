# Static checks
#
# Checks below are read-only. Run `just format` to apply formatting, or
# `just fix` to apply safe lint fixes and then format the affected sources.

PYTHON_FORMAT_PATHS := "scripts protocol core supervisor api executor docker-support provider workbench"
GUI_FORMAT_PATHS := "src tests scripts playwright.config.ts"

[private]
_check-write-hint:
    @echo ">> checks are read-only; run 'just format' to format or 'just fix' to apply safe fixes"

# Require every workspace-wide Just list and aggregate to cover the packages
# declared by pyproject.toml rather than silently drifting when one is added.
[private]
_check-just-workspace:
    python scripts/check_just_workspace.py

# Apply Python, GUI, and Nix formatting.
[group('Formatting')]
format:
    ruff format {{ PYTHON_FORMAT_PATHS }}
    cd gui && npx biome format --write {{ GUI_FORMAT_PATHS }}
    nix fmt

# Apply safe Python and GUI lint fixes, then normalize formatting.
[group('Formatting')]
fix: && format
    ruff check --fix {{ PYTHON_FORMAT_PATHS }}
    cd gui && npx biome check --write {{ GUI_FORMAT_PATHS }}

# Run tests for repository scripts.
[group('Script tests')]
test-scripts:
    pytest scripts/tests

# Statically check shell and Python scripts.
[group('Checks')]
check-scripts: _check-write-hint check-config _check-just-workspace
    @echo "Running shellcheck..."
    find scripts -name '*.sh' -exec shellcheck {} +
    @echo "Checking python scripts..."
    ruff check scripts
    ruff format --check scripts
    mypy scripts

# Check formatting and lint Nix sources without modifying them.
[group('Checks')]
check-nix: _check-write-hint
    @echo "Checking Nix formatting..."
    git ls-files -z --cached --others --exclude-standard -- '*.nix' | xargs -0 -r nixfmt --check
    @echo "Running statix..."
    statix check .
    @echo "Running deadnix..."
    deadnix --fail .

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
    npx biome check src tests scripts playwright.config.ts
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

[private]
_check-python-package package: _check-write-hint
    #!/usr/bin/env bash
    set -euo pipefail
    package={{ quote(package) }}
    echo "Running $package checks..."
    paths=("$package/src")
    if [[ -d "$package/tests" ]]; then paths+=("$package/tests"); fi
    ruff check "${paths[@]}"
    ruff format --check "${paths[@]}"
    mypy "${paths[@]}"

# Run static checks for the protocol package.
[group('Checks')]
check-protocol: (_check-python-package "protocol")

# Run static checks for the core package.
[group('Checks')]
check-core: (_check-python-package "core")

# Run static checks for the supervisor package.
[group('Checks')]
check-supervisor: (_check-python-package "supervisor")

# Run static checks for the API package.
[group('Checks')]
check-api: (_check-python-package "api")

# Run static checks for the executor package.
[group('Checks')]
check-executor: (_check-python-package "executor")

# Run static checks for the workbench package.
[group('Checks')]
check-workbench: (_check-python-package "workbench")

# Run static checks for shared Docker mechanics.
[group('Checks')]
check-docker-support: (_check-python-package "docker-support")

# Run static checks for the Docker provider package.
[group('Checks')]
check-provider: (_check-python-package "provider")

# Check backend import-layer contracts.
[group('Checks')]
check-architecture: _check-write-hint
    @echo "Running import-linter..."
    lint-imports

# Run static checks for every Python workspace package.
[group('Checks')]
check-backend: check-protocol check-core check-supervisor check-api check-executor check-docker-support check-provider check-workbench check-architecture

# Run every static analysis check.
[group('Checks')]
check: check-docs check-scripts check-nix check-gui check-backend

# Run every container-free unit test suite.
[group('Tests')]
test-unit: test-scripts test-gui test-backend-unit
