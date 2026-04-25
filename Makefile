
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
	cd src/repo2ree && \
		echo "Running ruff check..." && \
		ruff check service && \
		echo "Running ruff format..." && \
		ruff format service && \
		echo "Running mypy..." && \
		mypy service


e2e-tests:
	@echo "Running end-to-end tests..."
	npm --prefix /repo2ree/frontend exec -- playwright test -c /repo2ree/playwright.config.ts /repo2ree/tests/e2e/ree-create-python-hello-world.spec.ts
	
