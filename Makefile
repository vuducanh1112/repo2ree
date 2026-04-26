
.PHONY: fe-checks

fe-checks:
	@echo "Running frontend checks..."
	cd frontend && \
		echo "Running TypeScript compiler..." && \
		npx tsc && \
		echo "Running Biome..." && \
		npx biome check --write src && \
		echo "Running knip..." && \
		npx knip


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
	npm --prefix /repo2ree/frontend exec -- playwright test -c /repo2ree/playwright.config.ts /repo2ree/tests/e2e/ree-create-python-hello-world.spec.ts
	
