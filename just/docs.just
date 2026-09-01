DOCS_DEMO_ASSET_DIR := "docs/public/tutorials/assets/create-first-ree"

# Run deterministic, offline documentation checks.
[group('Documentation')]
docs-checks: docs-style docs-links-local docs-site

# Lint documentation prose.
[group('Documentation')]
docs-style:
    @echo "Linting docs with Vale..."
    vale docs README.md

# Download configured Vale styles.
[group('Documentation')]
docs-style-sync:
    @echo "Downloading configured Vale styles..."
    vale sync

# Check local documentation links and fragments.
[group('Documentation')]
docs-links-local:
    @echo "Checking local documentation links and heading fragments..."
    lychee --offline --include-fragments README.md docs

# Check all documentation links, including external URLs.
[group('Documentation')]
docs-links-external:
    @echo "Checking all documentation links, including external URLs..."
    lychee --cache --cache-exclude-status '429, 500..=599' --exclude-all-private --include-fragments --max-retries 3 --timeout 20 --no-progress README.md docs

# Build the curated public documentation site.
[group('Documentation')]
docs-site:
    @echo "Building the public documentation site..."
    zensical build --clean

# Serve a local documentation preview.
[group('Documentation')]
docs-serve:
    @echo "Serving the public documentation preview..."
    zensical serve -a localhost:8001

# Promote one recorded demo's video and screenshots into public docs.
[group('Documentation')]
docs-demo-assets:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    videos=(test-artifacts/playwright/demo-gui/*/video.webm)
    if (( ${#videos[@]} != 1 )); then
      echo "Expected exactly one demo-gui run, found ${#videos[@]}."
      echo "Run 'just demo-gui', then retry this recipe."
      exit 1
    fi
    source_dir="$(dirname "${videos[0]}")"
    mkdir -p '{{ DOCS_DEMO_ASSET_DIR }}'
    cp "$source_dir/video.webm" '{{ DOCS_DEMO_ASSET_DIR }}/demo.webm'
    cp "$source_dir/01-open-ree-creation-flow-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/01-provision.png'
    cp "$source_dir/04-review-workspace-source-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/02-source.png'
    cp "$source_dir/08-evaluate-ree-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/03-evaluate.png'
    cp "$source_dir/09-generate-a-build-script-from-the-repository-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/04-infer-build.png'
    cp "$source_dir/10-build-runtime-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/05-build.png'
    cp "$source_dir/12-cross-check-sbom-against-declared-dependencies-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/06-sbom.png'
    cp "$source_dir/14-test-activation-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/07-activation.png'
    cp "$source_dir/17-run-experiment-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/08-experiment.png'
    cp "$source_dir/19-seal-and-download-after.png" '{{ DOCS_DEMO_ASSET_DIR }}/09-seal.png'
    echo "Published tutorial screenshots and video under {{ DOCS_DEMO_ASSET_DIR }}/"
