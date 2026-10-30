# Normal image recipes build and load :local images. Archives are the
# credential-free handoff from a machine of another platform to the host that
# pushes: the images that machine's publish gate certified, saved by image ID
# with a manifest binding them to the revision, tree, and platform.

# Make untracked Python sources visible to Nix source filtering.
# Nix only includes Git-visible sources, so intent-to-add lets local builds see
# new Python files without staging their contents or changing the index state.
[private]
_stage-nix-sources:
    @git add -N $(python scripts/closures.py stage-paths) core/src executor/src workbench/src nix 2>/dev/null || true

# Build and load the GUI image.
[group('Images')]
build-gui-image:
    @echo "Building GUI image..."
    nix build .#gui-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-gui:local"

# Build and load the backend image.
[group('Images')]
build-backend-image: _stage-nix-sources
    @echo "Building backend image..."
    nix build .#backend-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-backend:local"

# Build and load the self-contained Docker provider image.
[group('Images')]
build-provider-image: _stage-nix-sources
    @echo "Building Docker provider image..."
    nix build .#provider-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-provider-docker:local"

# Build and load all deployable images.
[group('Images')]
build-images: build-gui-image build-backend-image build-provider-image

# Regenerate nix/closures.json, the Python closures nix ships, from uv.lock.
[group('Images')]
generate-closures:
    python scripts/closures.py generate

# List where the bench interpreters' packages differ from uv.lock; informational, the bench closures are not built from it yet.
[group('Images')]
report-bench-drift: _stage-nix-sources
    python scripts/closures.py bench-drift "$(nix build --no-link --print-out-paths .#bench-distributions)"

# Regenerate the pinned GUI npm dependency hash.
[group('Images')]
update-gui-npm-hash:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Computing npm deps hash from gui/package-lock.json..."
    candidate=$(mktemp nix/.gui-npm-deps.hash.XXXXXX)
    trap 'rm -f "$candidate"' EXIT
    nix run nixpkgs#prefetch-npm-deps -- gui/package-lock.json > "$candidate"
    chmod 0644 "$candidate"
    mv "$candidate" nix/gui-npm-deps.hash
    echo "Wrote nix/gui-npm-deps.hash: $(cat nix/gui-npm-deps.hash)"

# Save the images this machine's publish gate certified, by image ID, as its platform's archive set for the pushing host (dist/images/<os>-<arch>/).
[group('Image archives')]
archive-images archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: _require-clean-tree
    python -m scripts.publish.image_archive_set export --receipts .receipts --archive-dir {{ quote(archive_dir) }}
