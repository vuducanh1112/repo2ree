# Static checks

# Check shell and Python scripts.
[group('Checks')]
scripts-checks:
    @echo "Running shellcheck..."
    find scripts -name '*.sh' -exec shellcheck {} +
    @echo "Checking python scripts..."
    ruff check scripts
    ruff format scripts
    mypy scripts

# Format and lint Nix sources.
[group('Checks')]
nix-checks:
    @echo "Formatting nix files (nixfmt via nix fmt)..."
    nix fmt
    @echo "Running statix..."
    statix check .
    @echo "Running deadnix..."
    deadnix --fail .

# Run all GUI static checks.
[group('Checks')]
gui-checks: api-types-check
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Running GUI checks..."
    cd gui
    echo "Running TypeScript compiler (app)..."
    npx tsc -p tsconfig.app.json
    echo "Running TypeScript compiler (e2e)..."
    npx tsc -p tsconfig.e2e.json
    echo "Running Biome..."
    npx biome check --write src tests scripts playwright.config.ts
    echo "Running knip..."
    npx knip
    echo "Checking functional-core effects..."
    npm run check:core-purity
    echo "Checking style architecture..."
    npm run check:style-architecture
    echo "Running dependency-cruiser..."
    npx depcruise src tests

# Regenerate GUI API types and require the checked-in file to be current. Compare
# before/after content rather than against HEAD so this also works while an API
# migration is intentionally uncommitted.
[group('Checks')]
api-types-check:
    #!/usr/bin/env bash
    set -euo pipefail
    generated={{ quote(ROOT + "/gui/src/shell/infra/api/generated/openapi.ts") }}
    before=$(mktemp)
    trap 'rm -f "$before"' EXIT
    cp "$generated" "$before"
    just api-types
    diff -u "$before" "$generated"

[private]
_python-package-checks package:
    #!/usr/bin/env bash
    set -euo pipefail
    package={{ quote(package) }}
    echo "Running $package checks..."
    paths=("$package/src")
    if [[ -d "$package/tests" ]]; then paths+=("$package/tests"); fi
    ruff check "${paths[@]}"
    ruff format "${paths[@]}"
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
arch-checks:
    @echo "Running import-linter..."
    lint-imports

# Run static checks for every Python workspace package.
[group('Checks')]
be-checks: protocol-checks core-checks supervisor-checks api-checks executor-checks docker-support-checks provider-checks workbench-checks arch-checks
