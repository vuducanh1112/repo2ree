# Documentation checks that are deterministic and require no network access.
# Updating third-party Vale styles is an explicit setup operation rather than
# part of the gate: a check must not download or mutate its own rules.

.PHONY: docs-checks docs-lint docs-style docs-style-sync \
	docs-links-local docs-links-external docs-site docs-serve docs-demo-assets

DOCS_DEMO_ASSET_DIR = docs/public/tutorials/assets/create-first-ree
PLAYWRIGHT_DEMO_VIDEOS = $(wildcard test-artifacts/playwright/demo-gui/*/video.webm)
PLAYWRIGHT_DEMO_DIR = $(dir $(firstword $(PLAYWRIGHT_DEMO_VIDEOS)))

docs-checks: docs-style docs-links-local docs-site

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

# Build only the explicitly curated end-user tree. Zensical reads the output
# path from zensical.toml and writes disposable static files to sites/docs/.
docs-site:
	@echo "Building the public documentation site..."
	zensical build --clean

docs-serve:
	@echo "Serving the public documentation preview..."
	zensical serve

# Promotion is explicit: `make demo-gui` records the browser walkthrough under
# disposable test-artifacts/, while this target selects the tutorial's video
# and chapter screenshots for publication. The source names come from the demo
# helper and the destination names stay stable for the prose. Refuse zero or
# multiple runs instead of silently mixing missing, stale, or unrelated assets.
docs-demo-assets:
	@if [ "$(words $(PLAYWRIGHT_DEMO_VIDEOS))" -ne 1 ]; then \
		echo "Expected exactly one demo-gui run, found $(words $(PLAYWRIGHT_DEMO_VIDEOS))."; \
		echo "Run 'make demo-gui', then retry this target."; \
		exit 1; \
	fi
	@mkdir -p $(DOCS_DEMO_ASSET_DIR)
	cp "$(PLAYWRIGHT_DEMO_DIR)video.webm" "$(DOCS_DEMO_ASSET_DIR)/demo.webm"
	cp "$(PLAYWRIGHT_DEMO_DIR)01-open-ree-creation-flow-after.png" "$(DOCS_DEMO_ASSET_DIR)/01-provision.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)04-review-workspace-source-after.png" "$(DOCS_DEMO_ASSET_DIR)/02-source.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)08-evaluate-ree-after.png" "$(DOCS_DEMO_ASSET_DIR)/03-evaluate.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)09-generate-a-build-script-from-the-repository-after.png" "$(DOCS_DEMO_ASSET_DIR)/04-infer-build.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)10-build-runtime-after.png" "$(DOCS_DEMO_ASSET_DIR)/05-build.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)12-cross-check-sbom-against-declared-dependencies-after.png" "$(DOCS_DEMO_ASSET_DIR)/06-sbom.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)14-test-activation-after.png" "$(DOCS_DEMO_ASSET_DIR)/07-activation.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)17-run-experiment-after.png" "$(DOCS_DEMO_ASSET_DIR)/08-experiment.png"
	cp "$(PLAYWRIGHT_DEMO_DIR)19-seal-and-download-after.png" "$(DOCS_DEMO_ASSET_DIR)/09-seal.png"
	@echo "Published tutorial screenshots and video under $(DOCS_DEMO_ASSET_DIR)/"
