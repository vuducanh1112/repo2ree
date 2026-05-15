
.PHONY: fe-checks fe-tests be-checks core-checks api-checks test-checks core-tests api-tests

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

be-checks: core-checks api-checks

core-tests:
	@echo "Running core tests..."
	pytest core/tests

api-tests:
	@echo "Running api tests..."
	pytest api/tests

fe-tests:
	@echo "Running frontend unit tests..."
	cd frontend && npx vitest run

e2e-tests:
	@echo "Running end-to-end tests..."
	cd frontend && \
		npm exec -- playwright test -c playwright.config.ts tests/e2e/ree-create-python-hello-world.spec.ts
	
