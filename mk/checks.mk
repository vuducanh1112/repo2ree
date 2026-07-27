# Static checks: prose, shell scripts, nix, frontend, python.

.PHONY: docs-lint scripts-checks nix-checks fe-checks be-checks arch-checks api-types-check

# ================================================
# Docs — prose linting
# ================================================

docs-lint:
	@echo "Linting docs with Vale..."
	vale sync
	vale docs README.md

# ================================================
# Scripts — shell linting
# ================================================

scripts-checks:
	@echo "Running shellcheck..."
	shellcheck scripts/*.sh

# ================================================
# Nix — formatting and linting
# ================================================

# Formats in place (like fe-checks' biome --write), fails on statix or
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
# Frontend — checks
# ================================================

fe-checks: api-types-check
	@echo "Running frontend checks..."
	cd frontend && \
		echo "Running TypeScript compiler (app)..." && \
		npx tsc -p tsconfig.app.json && \
		echo "Running TypeScript compiler (e2e)..." && \
		npx tsc -p tsconfig.e2e.json && \
		echo "Running Biome..." && \
		npx biome check --write src tests playwright.config.ts && \
		echo "Running knip..." && \
		npx knip && \
		echo "Running dependency-cruiser..." && \
		npx depcruise src tests

api-types-check: api-types
	git diff --exit-code -- frontend/src/shell/infra/api/generated/openapi.ts

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
# dependency-cruiser step in fe-checks. Ruff and mypy are per-file and never see
# the graph, so layering and cycles are only caught here. Contracts live in
# pyproject.toml under [tool.importlinter].
arch-checks:
	@echo "Running import-linter..."
	lint-imports

be-checks: $(addsuffix -checks,$(PY_PACKAGES)) arch-checks
