# Static checks: shell scripts, nix, GUI, python. Prose linting and the
# generated architecture diagrams live in docs.mk.

.PHONY: scripts-checks nix-checks gui-checks be-checks arch-checks api-types-check

# ================================================
# Scripts — shell linting
# ================================================

# `scripts/*.sh` would not recurse into the topic directories, so shellcheck is
# handed the files find turns up: a glob that silently stops matching is exactly
# the failure a lint step must not have.
scripts-checks:
	@echo "Running shellcheck..."
	find scripts -name '*.sh' -exec shellcheck {} +
	@echo "Checking python scripts..."
	ruff check scripts
	ruff format scripts
	mypy scripts

# ================================================
# Nix — formatting and linting
# ================================================

# Formats in place (like gui-checks' biome --write), fails on statix or
# deadnix findings. Mark intentionally unused args with a _ prefix to
# silence deadnix.
nix-checks:
	@echo "Formatting nix files (nixfmt via nix fmt)..."
	nix fmt
	@echo "Running statix..."
	statix check .
	@echo "Running deadnix..."
	deadnix --fail .

# ================================================
# GUI — checks
# ================================================

gui-checks: api-types-check
	@echo "Running GUI checks..."
	cd gui && \
		echo "Running TypeScript compiler (app)..." && \
		npx tsc -p tsconfig.app.json && \
		echo "Running TypeScript compiler (e2e)..." && \
		npx tsc -p tsconfig.e2e.json && \
		echo "Running Biome..." && \
		npx biome check --write src tests scripts playwright.config.ts && \
		echo "Running knip..." && \
		npx knip && \
		echo "Checking functional-core effects..." && \
		npm run check:core-purity && \
		echo "Checking style architecture..." && \
		npm run check:style-architecture && \
		echo "Running dependency-cruiser..." && \
		npx depcruise src tests

api-types-check: api-types
	git diff --exit-code -- gui/src/shell/infra/api/generated/openapi.ts

# ================================================
# Backend — checks
# ================================================

# Python workspace packages. <pkg>-checks runs ruff + mypy over the package's
# src (and tests, where the package has them — protocol doesn't).
PY_PACKAGES = protocol core supervisor api executor agent

.PHONY: $(addsuffix -checks,$(PY_PACKAGES))
$(addsuffix -checks,$(PY_PACKAGES)): %-checks:
	@echo "Running $* checks..."
	ruff check $(wildcard $*/src $*/tests)
	ruff format $(wildcard $*/src $*/tests)
	mypy $(wildcard $*/src $*/tests)

# Architecture contracts over the backend import graph — the counterpart of the
# dependency-cruiser step in gui-checks. Ruff and mypy are per-file and never see
# the graph, so layering and cycles are only caught here. Contracts live in
# pyproject.toml under [tool.importlinter].
arch-checks:
	@echo "Running import-linter..."
	lint-imports

be-checks: $(addsuffix -checks,$(PY_PACKAGES)) arch-checks
