
.PHONY: fe-checks

fe-checks:
	@echo "Running frontend checks..."
	cd frontend && \
		echo "Running TypeScript compiler..." && \
		npx tsc && \
		echo "Running Biome..." && \
		npx biome check --write src tests playwright.config.ts && \
		echo "Running knip..." && \
		npx knip && \
		echo "Running dependency-cruiser..." && \
		npx depcruise src tests


be-checks:
	@echo "Running backend checks..."

	@echo "Running ruff check..."
	ruff check api/src
	@echo "Running ruff format..."
	ruff format api/src
	@echo "Running mypy..."
	mypy api/src


e2e-tests:
	@echo "Running end-to-end tests..."
	cd frontend && \
		npm exec -- playwright test -c playwright.config.ts tests/e2e/ree-create-python-hello-world.spec.ts
	
