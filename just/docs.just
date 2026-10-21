DOCS_DEMO_ASSET_DIR := "docs/public/tutorials/assets/create-first-ree"

# Run deterministic, offline documentation static analysis.
[group('Documentation')]
check-docs: lint-docs check-doc-links-local

# Lint documentation prose.
[group('Documentation')]
lint-docs:
    @echo "Linting docs with Vale..."
    vale docs

# Download configured Vale styles.
[group('Documentation')]
sync-doc-styles:
    @echo "Downloading configured Vale styles..."
    vale sync

# Check local documentation links and fragments.
[group('Documentation')]
check-doc-links-local:
    @echo "Checking local documentation links and heading fragments..."
    lychee --offline --include-fragments docs

# Check all documentation links, including external URLs.
[group('Documentation')]
check-doc-links-external:
    @echo "Checking all documentation links, including external URLs..."
    lychee --cache --cache-exclude-status '429, 500..=599' --exclude-all-private --include-fragments --max-retries 3 --timeout 20 --no-progress docs

# Build the curated public documentation site.
[group('Documentation')]
build-docs:
    @echo "Building the public documentation site..."
    zensical build --clean

# Serve a local documentation preview.
[group('Documentation')]
serve-docs:
    @echo "Serving the public documentation preview..."
    zensical serve -a localhost:8001

# Promote one recorded demo's video and screenshots into public docs.
[group('Documentation')]
publish-doc-demo-assets:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    # The newest demo-gui run; Playwright kept its video and screenshots in the run.
    run=$(ls -td {{ quote(REPO2REE_TEST_RUN_DIR + "/e2e") }}/demo-gui-*/ 2>/dev/null | head -n 1 || true)
    videos=(${run:+"$run"tests/suite/artifacts/*/video.webm})
    if (( ${#videos[@]} != 1 )); then
      echo "Expected exactly one demo-gui run, found ${#videos[@]}."
      echo "Run 'just demo-gui', then retry this recipe."
      exit 1
    fi
    source_dir="$(dirname "${videos[0]}")"
    mkdir -p '{{ DOCS_DEMO_ASSET_DIR }}'

    # Playwright prefixes step screenshots with their execution order. Match
    # the stable, human-readable step slug instead so inserting a chapter into
    # the narrated demo does not break publication or silently select the
    # wrong frame.
    copy_step() {
      local step_slug="$1"
      local public_name="$2"
      local screenshots=("$source_dir"/[0-9][0-9]-"$step_slug"-after.png)
      if (( ${#screenshots[@]} != 1 )); then
        echo "Expected exactly one after-screenshot for '$step_slug', found ${#screenshots[@]}."
        exit 1
      fi
      cp "${screenshots[0]}" '{{ DOCS_DEMO_ASSET_DIR }}/'"$public_name"
    }

    cp "$source_dir/video.webm" '{{ DOCS_DEMO_ASSET_DIR }}/demo.webm'
    copy_step open-the-repo2ree-landing-page 01-landing.png
    copy_step choose-a-compute-location 01-compute-location.png
    copy_step open-workbench-setup 01-workbench-setup.png
    copy_step provision-the-workbench 01-provision.png
    copy_step review-workspace-source 02-source.png
    copy_step browse-extracted-files 02-files.png
    copy_step provide-metadata 02-metadata.png
    copy_step provide-hbom-entry 02-hardware.png
    copy_step evaluate-ree 03-evaluate.png
    copy_step generate-a-build-script-from-the-repository 04-infer-build.png
    copy_step build-runtime 05-build.png
    copy_step cross-check-sbom-against-declared-dependencies 06-sbom.png
    copy_step test-activation 07-activation.png
    copy_step run-experiment 08-experiment.png
    copy_step seal-and-download 09-seal.png
    echo "Published tutorial screenshots and video under {{ DOCS_DEMO_ASSET_DIR }}/"
