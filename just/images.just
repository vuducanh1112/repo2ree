# Normal image recipes build and load :local images. Archive recipes are an
# explicit credential-free handoff: build tarballs in the development
# container, then load and publish them on a host with registry credentials.
# The archive set is stamped with its clean Git revision so the host cannot
# accidentally publish it under a different candidate name.

# Create archive output directory.
[private]
_image-archive-dir:
    @mkdir -p {{ quote(IMAGE_ARCHIVE_DIR) }}

# Make untracked Python sources visible to Nix source filtering.
# Nix only includes Git-visible sources, so intent-to-add lets local builds see
# new Python files without staging their contents or changing the index state.
[private]
_stage-nix-sources:
    @git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor agent/src 2>/dev/null || true

# Build and load the GUI image.
[group('Images')]
gui-image:
    @echo "Building GUI image..."
    nix build .#gui-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-gui:local"

# Build and load the backend image.
[group('Images')]
backend-image:
    @echo "Building backend image..."
    docker build --provenance=false -f docker/demo/backend.Dockerfile -t repo2ree-backend:local .
    @echo "Done: repo2ree-backend:local"

# Build and load the self-contained agent image.
[group('Images')]
agent-image: _stage-nix-sources
    @echo "Building agent image..."
    nix build .#agent-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-agent:local"

# Build and load all deployable images.
[group('Images')]
images: gui-image backend-image agent-image

# Regenerate the pinned GUI npm dependency hash.
[group('Images')]
gui-npm-hash:
    @echo "Computing npm deps hash from gui/package-lock.json..."
    nix run nixpkgs#prefetch-npm-deps -- gui/package-lock.json > nix/gui-npm-deps.hash
    @echo "Wrote nix/gui-npm-deps.hash: $(cat nix/gui-npm-deps.hash)"

# Build a loadable GUI image archive.
[group('Image archives')]
gui-image-archive: _image-archive-dir
    @echo "Building GUI image archive..."
    nix build .#gui-image
    cp -fL result {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-gui-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-gui-local.tar") }}

# Save the loaded backend image as an archive.
[group('Image archives')]
backend-image-archive: backend-image _image-archive-dir
    docker save repo2ree-backend:local -o {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-backend-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-backend-local.tar") }}

# Build a loadable agent image archive.
[group('Image archives')]
agent-image-archive: _stage-nix-sources _image-archive-dir
    @echo "Building agent image archive..."
    nix build .#agent-image
    cp -fL result {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-agent-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-agent-local.tar") }}

# Build and stamp the complete clean-tree image archive set.
[group('Image archives')]
image-archives: _require-clean-tree gui-image-archive backend-image-archive agent-image-archive
    @git describe --always > {{ quote(IMAGE_ARCHIVE_DIR + "/IMAGE_CANDIDATE_REV") }}
    @echo ">> stamped candidate: $(cat {{ quote(IMAGE_ARCHIVE_DIR + "/IMAGE_CANDIDATE_REV") }})"

# Load every image from an archive set.
[group('Image archives')]
load-image-archives:
    #!/usr/bin/env bash
    set -euo pipefail
    for image in repo2ree-gui repo2ree-backend repo2ree-agent; do
      docker load -i {{ quote(IMAGE_ARCHIVE_DIR) }}/"$image"-local.tar
    done
