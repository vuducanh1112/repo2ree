# Static checks
#
# Checks below are read-only. Run `just format` to apply formatting, or
# `just fix` to apply safe lint fixes and then format the affected sources.

PYTHON_FORMAT_PATHS := "scripts protocol core supervisor api executor docker-support provider workbench"
GUI_FORMAT_PATHS := "src tests scripts playwright.config.ts"

[private]
_checks-write-hint:
    @echo ">> checks are read-only; run 'just format' to format or 'just fix' to apply safe fixes"

# Apply Python, GUI, and Nix formatting.
[group('Formatting')]
format:
    ruff format {{ PYTHON_FORMAT_PATHS }}
    cd gui && npx biome format --write {{ GUI_FORMAT_PATHS }}
    nix fmt

# Apply safe Python and GUI lint fixes, then normalize formatting.
[group('Formatting')]
fix:
    ruff check --fix {{ PYTHON_FORMAT_PATHS }}
    cd gui && npx biome check --write {{ GUI_FORMAT_PATHS }}
    just format

# Check shell and Python scripts.
[group('Checks')]
scripts-checks: _checks-write-hint config-check
    pytest scripts/tests
    @echo "Running shellcheck..."
    find scripts -name '*.sh' -exec shellcheck {} +
    @echo "Checking python scripts..."
    ruff check scripts
    ruff format --check scripts
    mypy scripts

# Check formatting and lint Nix sources without modifying them.
[group('Checks')]
nix-checks: _checks-write-hint
    @echo "Checking Nix formatting..."
    git ls-files -z --cached --others --exclude-standard -- '*.nix' | xargs -0 -r nixfmt --check
    @echo "Running statix..."
    statix check .
    @echo "Running deadnix..."
    deadnix --fail .

# Run all GUI static checks.
[group('Checks')]
gui-checks: _checks-write-hint api-types-check
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
api-types-check: _checks-write-hint
    #!/usr/bin/env bash
    set -euo pipefail
    generated={{ quote(ROOT + "/gui/src/shell/infra/api/generated/openapi.ts") }}
    candidate=$(mktemp)
    trap 'rm -f "$candidate"' EXIT
    cd gui
    npx openapi-typescript ../contracts/openapi.json -o "$candidate"
    diff -u "$generated" "$candidate"

[private]
_python-package-checks package: _checks-write-hint
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
protocol-checks: (_python-package-checks "protocol")

# Run static checks for the core package.
[group('Checks')]
core-checks: (_python-package-checks "core")

# Run static checks for the supervisor package.
[group('Checks')]
supervisor-checks: (_python-package-checks "supervisor")

# Run static checks for the API package.
[group('Checks')]
api-checks: (_python-package-checks "api")

# Run static checks for the executor package.
[group('Checks')]
executor-checks: (_python-package-checks "executor")

# Run static checks for the workbench package.
[group('Checks')]
workbench-checks: (_python-package-checks "workbench")

# Run static checks for shared Docker mechanics.
[group('Checks')]
docker-support-checks: (_python-package-checks "docker-support")

# Run static checks for the Docker provider package.
[group('Checks')]
provider-checks: (_python-package-checks "provider")

# Check backend import-layer contracts.
[group('Checks')]
arch-checks: _checks-write-hint
    @echo "Running import-linter..."
    lint-imports

# Run static checks for every Python workspace package.
[group('Checks')]
be-checks: protocol-checks core-checks supervisor-checks api-checks executor-checks docker-support-checks provider-checks workbench-checks arch-checks
