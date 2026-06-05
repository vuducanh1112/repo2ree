.PHONY: \
	fe-checks fe-tests \
	be-checks protocol-checks core-checks supervisor-checks api-checks executor-checks \
	be-tests core-tests api-tests executor-tests \
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

supervisor-checks:
	@echo "Running supervisor checks..."
	ruff check supervisor/src
	ruff format supervisor/src
	mypy supervisor/src

api-checks:
	@echo "Running api checks..."
	ruff check api/src api/tests
	ruff format api/src api/tests
	mypy api/src api/tests

executor-checks:
	@echo "Running executor checks..."
	ruff check executor/src executor/tests
	ruff format executor/src executor/tests
	mypy executor/src executor/tests

be-checks: protocol-checks core-checks supervisor-checks api-checks executor-checks

# ================================================
# Backend - tests
# ================================================

core-tests:
	pytest core/tests

api-tests:
	pytest api/tests

executor-tests:
	pytest executor/tests

be-tests: core-tests api-tests executor-tests

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
	@echo "Staging untracked executor sources for nix..."
	git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor 2>/dev/null || true
	@echo "Building workbench image..."
	nix build .#workbench-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-workbench:latest"
