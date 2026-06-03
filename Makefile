.PHONY: \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks api-checks cli-checks \
	be-tests core-tests api-tests cli-tests \
	test-checks \
	workbench-image \
	e2e-tests e2e-demo

# ================================================
# Frontend — checks and tests
# ================================================

fe-checks:
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

fe-tests:
	@echo "Running frontend unit tests..."
	cd frontend && npx vitest run

# ================================================
# Backend - checks
# ================================================

protocol-checks:
	@echo "Running protocol checks..."
	ruff check protocol/src
	ruff format protocol/src
	mypy protocol/src

core-checks:
	@echo "Running core checks..."
	ruff check core/src core/tests
	ruff format core/src core/tests
	mypy core/src core/tests

api-checks:
	@echo "Running api checks..."
	ruff check api/src api/tests
	ruff format api/src api/tests
	mypy api/src api/tests

cli-checks:
	@echo "Running cli checks..."
	ruff check cli/src cli/tests
	ruff format cli/src cli/tests
	mypy cli/src cli/tests

be-checks: protocol-checks core-checks api-checks cli-checks

# ================================================
# Backend - tests
# ================================================

core-tests:
	pytest core/tests

api-tests:
	pytest api/tests

cli-tests:
	pytest cli/tests

be-tests: core-tests api-tests cli-tests

# ================================================
# End-to-end tests
# ================================================

e2e-tests:
	cd frontend && npm exec -- playwright test -c playwright.config.ts --project=e2e

e2e-demo:
	cd frontend && npm exec -- playwright test -c playwright.config.ts --project=demo

# ================================================
# Build
# ================================================

workbench-image:
	@echo "Staging untracked envelope sources for nix..."
	git add -N protocol/src core/src/repo2ree_core/envelope cli/src/repo2ree_cli/cli.py api/src/repo2ree_api/workbench 2>/dev/null || true
	@echo "Building workbench image..."
	nix build .#workbench-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-workbench:latest"
