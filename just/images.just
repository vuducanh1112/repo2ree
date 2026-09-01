# Create archive output directory.
[group('Images')]
image-archive-dir IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR:
    @mkdir -p {{ quote(IMAGE_ARCHIVE_DIR) }}

# Make untracked Python sources visible to Nix source filtering.
[group('Images')]
stage-nix-sources:
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
agent-image: stage-nix-sources
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
gui-image-archive IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR: (image-archive-dir IMAGE_ARCHIVE_DIR)
    @echo "Building GUI image archive..."
    nix build .#gui-image
    cp -fL result {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-gui-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-gui-local.tar") }}

# Save the loaded backend image as an archive.
[group('Image archives')]
backend-image-archive IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR: backend-image (image-archive-dir IMAGE_ARCHIVE_DIR)
    docker save repo2ree-backend:local -o {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-backend-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-backend-local.tar") }}

# Build a loadable agent image archive.
[group('Image archives')]
agent-image-archive IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR: stage-nix-sources (image-archive-dir IMAGE_ARCHIVE_DIR)
    @echo "Building agent image archive..."
    nix build .#agent-image
    cp -fL result {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-agent-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(IMAGE_ARCHIVE_DIR + "/repo2ree-agent-local.tar") }}

# Build and stamp the complete clean-tree image archive set.
[group('Image archives')]
image-archives IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR: require-clean-tree (gui-image-archive IMAGE_ARCHIVE_DIR) (backend-image-archive IMAGE_ARCHIVE_DIR) (agent-image-archive IMAGE_ARCHIVE_DIR)
    @git describe --always > {{ quote(IMAGE_ARCHIVE_DIR + "/IMAGE_CANDIDATE_REV") }}
    @echo ">> stamped candidate: $(cat {{ quote(IMAGE_ARCHIVE_DIR + "/IMAGE_CANDIDATE_REV") }})"

# Load every image from an archive set.
[group('Image archives')]
load-image-archives IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR:
    #!/usr/bin/env bash
    set -euo pipefail
    for image in repo2ree-gui repo2ree-backend repo2ree-agent; do
      docker load -i {{ quote(IMAGE_ARCHIVE_DIR) }}/"$image"-local.tar
    done
