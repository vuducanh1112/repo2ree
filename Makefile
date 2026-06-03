
.PHONY: fe-checks fe-tests be-checks core-checks api-checks cli-checks test-checks core-tests api-tests cli-tests workbench-image e2e-tests e2e-demo

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


core-checks:
	@echo "Running core checks..."
	@echo "Running ruff check..."
	ruff check core/src core/tests
	@echo "Running ruff format..."
	ruff format core/src core/tests
	@echo "Running mypy..."
	mypy core/src core/tests

api-checks:
	@echo "Running api checks..."
	@echo "Running ruff check..."
	ruff check api/src api/tests
	@echo "Running ruff format..."
	ruff format api/src api/tests
	@echo "Running mypy..."
	mypy api/src api/tests

test-checks:
	@echo "Running test checks..."
	@echo "Running ruff check..."
	ruff check core/tests api/tests
	@echo "Running ruff format..."
	ruff format core/tests api/tests
	@echo "Running mypy..."
	mypy core/tests api/tests

cli-checks:
	@echo "Running cli checks..."
	@echo "Running ruff check..."
	ruff check cli/src cli/tests
	@echo "Running ruff format..."
	ruff format cli/src cli/tests
	@echo "Running mypy..."
	mypy cli/src cli/tests

be-checks: core-checks api-checks cli-checks

workbench-image:
	@echo "Staging untracked envelope sources for nix..."
	git add -N core/src/repo2ree_core/envelope cli/src/repo2ree_cli/cli.py api/src/repo2ree_api/workbench 2>/dev/null || true
	@echo "Building workbench image..."
	nix build .#workbench-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-workbench:latest"

core-tests:
	@echo "Running core tests..."
	pytest core/tests

api-tests:
	@echo "Running api tests..."
	pytest api/tests

cli-tests:
	@echo "Running cli tests..."
	pytest cli/tests

be-tests: core-tests api-tests cli-tests

fe-tests:
	@echo "Running frontend unit tests..."
	cd frontend && npx vitest run

e2e-tests:
	@echo "Running fast end-to-end tests..."
	cd frontend && \
		npm exec -- playwright test -c playwright.config.ts --project=e2e

e2e-demo:
	@echo "Running demo end-to-end walkthrough..."
	cd frontend && \
		npm exec -- playwright test -c playwright.config.ts --project=demo
	
