# Documentation checks that are deterministic and require no network access.
# Updating third-party Vale styles is an explicit setup operation rather than
# part of the gate: a check must not download or mutate its own rules.

.PHONY: docs-checks docs-lint docs-style docs-style-sync \
	docs-links-local docs-links-external

docs-checks: docs-style docs-links-local

# Compatibility alias for the old public target. New callers should use
# docs-checks, which also validates local links and heading fragments.
docs-lint: docs-style

docs-style:
	@echo "Linting docs with Vale..."
	vale docs README.md

docs-style-sync:
	@echo "Downloading configured Vale styles..."
	vale sync

docs-links-local:
	@echo "Checking local documentation links and heading fragments..."
	lychee --offline --include-fragments README.md docs

# Deliberately excluded from docs-checks and the commit gate: remote services
# can rate-limit, reject bots, or fail transiently. Run this manually when the
# network is available; local paths and fragments are checked again as part of
# the same complete pass.
docs-links-external:
	@echo "Checking all documentation links, including external URLs..."
	lychee --cache \
		--cache-exclude-status '429, 500..=599' \
		--exclude-all-private \
		--include-fragments \
		--max-retries 3 \
		--timeout 20 \
		--no-progress \
		README.md docs
