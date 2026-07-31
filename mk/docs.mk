# Documentation prose checks.

.PHONY: docs-lint

docs-lint:
	@echo "Linting docs with Vale..."
	vale sync
	vale docs README.md
